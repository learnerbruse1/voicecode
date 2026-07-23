"""Voice activity detection extension configuration and Silero preprocessing."""

from __future__ import annotations

from collections.abc import Mapping
import importlib
import threading
from typing import Any

import numpy as np

from .base import BaseExtension

VALID_VAD_ENGINES = {"faster_whisper", "silero", "off"}
_silero_lock = threading.RLock()
_silero_model: Any | None = None
_silero_error: str | None = None


class VadExtension(BaseExtension):
    id = "vad"
    name = "Voice activity detection"
    description = "Controls silence filtering before/during transcription."
    enabled_by_default = True
    optional_dependencies = ["silero-vad"]

    def default_config(self) -> dict[str, Any]:
        return {
            "enabled": True,
            "engine": "faster_whisper",
            "min_silence_duration_ms": 500,
            "speech_pad_ms": 100,
            "threshold": 0.5,
        }

    def missing_dependencies(self) -> list[str]:
        try:
            importlib.import_module("silero_vad")
        except Exception:
            return ["silero-vad"]
        return []

    def operational_status(self, config: Mapping[str, Any]) -> tuple[bool, str | None]:
        if config.get("engine", "faster_whisper") != "silero":
            return True, None
        missing = self.missing_dependencies()
        if missing:
            return False, "Silero VAD is selected but its dependency is missing."
        if _silero_error:
            return False, _silero_error
        return True, "Silero runs as an audio preprocessing step before Whisper."


def transcribe_options(config: dict[str, Any], legacy_vad_filter: bool = True) -> dict[str, Any]:
    enabled = bool(config.get("enabled", legacy_vad_filter))
    engine = str(config.get("engine", "faster_whisper"))
    if not enabled or engine in {"off", "silero"}:
        return {"vad_filter": False}
    silence = int(config.get("min_silence_duration_ms", 500))
    return {"vad_filter": True, "vad_parameters": {"min_silence_duration_ms": silence}}


def _load_silero_model() -> tuple[Any, Any]:
    global _silero_error, _silero_model
    module = importlib.import_module("silero_vad")
    with _silero_lock:
        if _silero_model is None:
            try:
                _silero_model = module.load_silero_vad()
                _silero_error = None
            except Exception as exc:
                _silero_error = f"Failed to load Silero VAD: {exc}"
                raise RuntimeError(_silero_error) from exc
    return module, _silero_model


def preprocess_audio(
    audio: np.ndarray | str, config: dict[str, Any], *, sample_rate: int = 16000
) -> tuple[np.ndarray | str, dict[str, Any] | None]:
    """Apply Silero VAD when selected and return compacted speech plus metadata."""
    if not bool(config.get("enabled", True)) or config.get("engine") != "silero":
        return audio, None
    module, model = _load_silero_model()
    torch = importlib.import_module("torch")
    if isinstance(audio, str):
        waveform = module.read_audio(audio, sampling_rate=sample_rate)
    else:
        normalized = np.asarray(audio, dtype=np.float32).reshape(-1)
        waveform = torch.from_numpy(normalized)
    timestamps = module.get_speech_timestamps(
        waveform,
        model,
        sampling_rate=sample_rate,
        min_silence_duration_ms=int(config.get("min_silence_duration_ms", 500)),
        speech_pad_ms=int(config.get("speech_pad_ms", 100)),
        threshold=float(config.get("threshold", 0.5)),
    )
    serializable = [{"start": int(item["start"]), "end": int(item["end"])} for item in timestamps]
    if not timestamps:
        return np.empty(0, dtype=np.float32), {
            "engine": "silero",
            "speech_segments": [],
            "speech_seconds": 0.0,
        }
    chunks = module.collect_chunks(timestamps, waveform)
    if hasattr(chunks, "detach"):
        chunks = chunks.detach()
    if hasattr(chunks, "cpu"):
        chunks = chunks.cpu()
    compacted = np.asarray(chunks.numpy() if hasattr(chunks, "numpy") else chunks, dtype=np.float32)
    speech_samples = sum(item["end"] - item["start"] for item in serializable)
    return compacted.reshape(-1), {
        "engine": "silero",
        "speech_segments": serializable,
        "speech_seconds": round(speech_samples / sample_rate, 3),
    }


def reset_runtime_cache() -> None:
    global _silero_error, _silero_model
    with _silero_lock:
        _silero_model = None
        _silero_error = None
