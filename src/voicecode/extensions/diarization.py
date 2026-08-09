"""Optional speaker diarization using pyannote.audio."""

from __future__ import annotations

import importlib
import os
import threading
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np

from .base import BaseExtension

_pipeline_lock = threading.RLock()
_pipeline: Any | None = None
_pipeline_key: tuple[str, str, str] | None = None
_runtime_error: str | None = None


class DiarizationExtension(BaseExtension):
    id = "diarization"
    name = "Speaker diarization"
    description = "Optional speaker labeling for longer uploaded recordings."
    enabled_by_default = False
    optional_dependencies = ["pyannote.audio"]
    maturity = "experimental"
    restart_required_after_install = True

    def default_config(self) -> dict[str, Any]:
        return {
            "enabled": False,
            "engine": "pyannote",
            "model_name": "pyannote/speaker-diarization-community-1",
            "token_env": "HF_TOKEN",
            "device": "auto",
            "min_speakers": 1,
            "max_speakers": 8,
            "exclusive": True,
        }

    def missing_dependencies(self) -> list[str]:
        try:
            importlib.import_module("pyannote.audio")
            importlib.import_module("torch")
        except Exception:
            return ["pyannote.audio"]
        return []

    def operational_status(self, config: Mapping[str, Any]) -> tuple[bool, str | None]:
        if self.missing_dependencies():
            return False, "pyannote.audio is not installed."
        token_env = str(config.get("token_env", "HF_TOKEN"))
        model_name = str(config.get("model_name", ""))
        if model_name.startswith("pyannote/") and not os.environ.get(token_env):
            return False, f"Set the {token_env} environment variable for the pyannote model."
        if _runtime_error:
            return False, _runtime_error
        return (
            True,
            "The pyannote pipeline is loaded lazily when timestamped segments are available.",
        )


def _resolve_device(value: str) -> str:
    if value in {"cpu", "cuda"}:
        return value
    torch = importlib.import_module("torch")
    return "cuda" if bool(torch.cuda.is_available()) else "cpu"


def _load_pipeline(config: dict[str, Any]) -> Any:
    global _pipeline, _pipeline_key, _runtime_error
    model_name = str(config.get("model_name", "pyannote/speaker-diarization-community-1"))
    token_env = str(config.get("token_env", "HF_TOKEN"))
    token = os.environ.get(token_env, "")
    device = _resolve_device(str(config.get("device", "auto")))
    key = (model_name, token_env, device)
    with _pipeline_lock:
        if _pipeline is not None and _pipeline_key == key:
            return _pipeline
        try:
            pyannote_audio = importlib.import_module("pyannote.audio")
            torch = importlib.import_module("torch")
            kwargs: dict[str, Any] = {}
            if token:
                kwargs["token"] = token
            pipeline = pyannote_audio.Pipeline.from_pretrained(model_name, **kwargs)
            if pipeline is None:
                raise RuntimeError("Pipeline.from_pretrained returned no pipeline.")
            pipeline.to(torch.device(device))
            _pipeline = pipeline
            _pipeline_key = key
            _runtime_error = None
            return pipeline
        except Exception as exc:
            _runtime_error = f"Failed to load pyannote diarization pipeline: {exc}"
            raise RuntimeError(_runtime_error) from exc


def _audio_input(audio: np.ndarray | str | Path, sample_rate: int) -> Any:
    if isinstance(audio, (str, Path)):
        return str(audio)
    torch = importlib.import_module("torch")
    waveform = torch.from_numpy(np.asarray(audio, dtype=np.float32).reshape(1, -1))
    return {"waveform": waveform, "sample_rate": sample_rate}


def _turns(output: Any, exclusive: bool) -> list[tuple[float, float, str]]:
    annotation = None
    if exclusive:
        annotation = getattr(output, "exclusive_speaker_diarization", None)
    if annotation is None:
        annotation = getattr(output, "speaker_diarization", output)
    turns: list[tuple[float, float, str]] = []
    itertracks = getattr(annotation, "itertracks", None)
    if callable(itertracks):
        for segment, _, speaker in itertracks(yield_label=True):
            turns.append((float(segment.start), float(segment.end), str(speaker)))
        return turns
    try:
        for segment, speaker in annotation:
            turns.append((float(segment.start), float(segment.end), str(speaker)))
    except TypeError as exc:
        raise RuntimeError("Unsupported pyannote diarization result format.") from exc
    return turns


def assign_speakers(
    segments: list[dict[str, Any]],
    audio: np.ndarray | str | Path,
    config: dict[str, Any],
    *,
    sample_rate: int = 16000,
) -> list[dict[str, Any]]:
    if not segments:
        return segments
    pipeline = _load_pipeline(config)
    kwargs: dict[str, int] = {}
    minimum = int(config.get("min_speakers", 1))
    maximum = int(config.get("max_speakers", 8))
    if minimum == maximum:
        kwargs["num_speakers"] = minimum
    else:
        kwargs["min_speakers"] = minimum
        kwargs["max_speakers"] = maximum
    try:
        output = pipeline(_audio_input(audio, sample_rate), **kwargs)
        diarized_turns = _turns(output, bool(config.get("exclusive", True)))
    except Exception as exc:
        global _runtime_error
        _runtime_error = f"pyannote diarization failed: {exc}"
        raise RuntimeError(_runtime_error) from exc
    labeled: list[dict[str, Any]] = []
    for item in segments:
        start = float(item.get("start", 0.0))
        end = float(item.get("end", start))
        speaker = None
        best_overlap = 0.0
        for turn_start, turn_end, label in diarized_turns:
            overlap = max(0.0, min(end, turn_end) - max(start, turn_start))
            if overlap > best_overlap:
                best_overlap = overlap
                speaker = label
        labeled.append({**item, "speaker": speaker or "UNKNOWN"})
    return labeled


def reset_runtime_cache() -> None:
    global _pipeline, _pipeline_key, _runtime_error
    with _pipeline_lock:
        _pipeline = None
        _pipeline_key = None
        _runtime_error = None
