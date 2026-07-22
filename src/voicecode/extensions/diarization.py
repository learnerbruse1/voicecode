"""Optional speaker diarization extension placeholder."""

from __future__ import annotations

from typing import Any
import importlib

from .base import BaseExtension


class DiarizationExtension(BaseExtension):
    id = "diarization"
    name = "Speaker diarization"
    description = "Optional speaker labeling for longer uploaded recordings."
    enabled_by_default = False
    optional_dependencies = ["pyannote.audio"]

    def default_config(self) -> dict[str, Any]:
        return {"enabled": False, "engine": "pyannote"}

    def missing_dependencies(self) -> list[str]:
        try:
            importlib.import_module("pyannote.audio")
        except Exception:
            return ["pyannote.audio"]
        return []


def assign_speakers(segments: list[dict[str, Any]], config: dict[str, Any]) -> list[dict[str, Any]]:
    # Heavy diarization model loading is intentionally not part of the default runtime path.
    # This extension point keeps the API stable for a future optional adapter.
    return segments
