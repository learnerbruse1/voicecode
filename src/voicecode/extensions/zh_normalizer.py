"""Chinese transcript normalization extension."""

from __future__ import annotations

import importlib
import re
from typing import Any

from .base import BaseExtension


class ZhNormalizerExtension(BaseExtension):
    id = "zh_normalizer"
    name = "Chinese normalizer"
    description = "Optional Chinese spacing, punctuation, and script normalization."
    enabled_by_default = False
    optional_dependencies = ["opencc-python-reimplemented"]

    def default_config(self) -> dict[str, Any]:
        return {
            "enabled": False,
            "script": "none",
            "normalize_spacing": True,
            "normalize_punctuation": True,
        }

    def missing_dependencies(self) -> list[str]:
        # OpenCC is only required when script conversion is enabled. The status endpoint does not
        # know current config here, so registry adds config-aware availability.
        try:
            importlib.import_module("opencc")
        except Exception:
            return ["opencc-python-reimplemented"]
        return []


def _convert_script(text: str, script: str) -> str:
    if script == "none":
        return text
    try:
        opencc = importlib.import_module("opencc")
        config_name = "t2s" if script == "simplified" else "s2t"
        converter = opencc.OpenCC(config_name)
        return str(converter.convert(text))
    except Exception:
        return text


def normalize(text: str, language: str | None, config: dict[str, Any]) -> str:
    if language not in {"zh", "zh-cn", "zh-tw", "auto", None}:
        return text
    normalized = text
    if bool(config.get("normalize_spacing", True)):
        normalized = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", normalized)
        normalized = re.sub(r"\s+([，。！？；：、])", r"\1", normalized)
    if bool(config.get("normalize_punctuation", True)):
        table = str.maketrans({",": "，", "?": "？", "!": "！", ";": "；", ":": "："})
        normalized = normalized.translate(table)
    script = str(config.get("script", "none"))
    if script in {"simplified", "traditional"}:
        normalized = _convert_script(normalized, script)
    return normalized.strip()
