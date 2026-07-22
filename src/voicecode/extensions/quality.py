"""Optional transcription quality metrics extension."""

from __future__ import annotations

from typing import Any
import importlib

from .base import BaseExtension


class QualityExtension(BaseExtension):
    id = "quality"
    name = "Quality metrics"
    description = "Optional WER/CER helpers for transcription regression tests."
    enabled_by_default = False
    optional_dependencies = ["jiwer"]

    def default_config(self) -> dict[str, Any]:
        return {"enabled": False, "metrics": ["wer", "cer"]}

    def missing_dependencies(self) -> list[str]:
        try:
            importlib.import_module("jiwer")
        except Exception:
            return ["jiwer"]
        return []


def compute_metrics(reference: str, hypothesis: str) -> dict[str, float]:
    jiwer = importlib.import_module("jiwer")
    return {
        "wer": float(jiwer.wer(reference, hypothesis)),
        "cer": float(jiwer.cer(reference, hypothesis)),
    }
