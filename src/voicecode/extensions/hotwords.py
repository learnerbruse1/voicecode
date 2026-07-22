"""Hotword prompt extension."""

from __future__ import annotations

from typing import Any

from .base import BaseExtension


class HotwordsExtension(BaseExtension):
    id = "hotwords"
    name = "Hotwords"
    description = "Adds user-defined project terms to the Whisper initial prompt."
    enabled_by_default = True

    def default_config(self) -> dict[str, Any]:
        return {"enabled": True, "phrases": []}


def phrases(config: dict[str, Any]) -> list[str]:
    raw = config.get("phrases", [])
    if not isinstance(raw, list):
        return []
    return [item.strip() for item in raw if isinstance(item, str) and item.strip()]


def build_prompt(base_prompt: str | None, config: dict[str, Any]) -> str | None:
    terms = phrases(config)
    if not terms:
        return base_prompt
    hotword_prompt = "Prefer these exact terms when heard: " + ", ".join(terms) + "."
    if base_prompt:
        return f"{base_prompt} {hotword_prompt}"
    return hotword_prompt
