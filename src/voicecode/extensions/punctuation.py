"""Optional punctuation restoration extension placeholder."""

from __future__ import annotations

from typing import Any
import importlib

from .base import BaseExtension


class PunctuationExtension(BaseExtension):
    id = "punctuation"
    name = "Punctuation restoration"
    description = "Optional punctuation/capitalization restoration for post-processing."
    enabled_by_default = False
    optional_dependencies = ["nemo-toolkit"]

    def default_config(self) -> dict[str, Any]:
        return {"enabled": False, "engine": "nemo"}

    def missing_dependencies(self) -> list[str]:
        try:
            importlib.import_module("nemo")
        except Exception:
            return ["nemo-toolkit"]
        return []


def restore(text: str, language: str | None, config: dict[str, Any]) -> str:
    # Placeholder adapter: keep behavior unchanged unless a lightweight/restorable model is added.
    return text
