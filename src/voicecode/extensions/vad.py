"""Voice activity detection extension configuration."""

from __future__ import annotations

from typing import Any

from .base import BaseExtension

VALID_VAD_ENGINES = {"faster_whisper", "silero", "off"}


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
        }

    def missing_dependencies(self) -> list[str]:
        return []


def transcribe_options(config: dict[str, Any], legacy_vad_filter: bool = True) -> dict[str, Any]:
    enabled = bool(config.get("enabled", legacy_vad_filter))
    engine = str(config.get("engine", "faster_whisper"))
    if not enabled or engine == "off":
        return {"vad_filter": False}
    if engine != "faster_whisper":
        # Non-core VAD engines are intentionally not run by default. They can preprocess audio in
        # a future adapter while faster-whisper remains the stable built-in path.
        return {"vad_filter": False}
    silence = int(config.get("min_silence_duration_ms", 500))
    return {"vad_filter": True, "vad_parameters": {"min_silence_duration_ms": silence}}
