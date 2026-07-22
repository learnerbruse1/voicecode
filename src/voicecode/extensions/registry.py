"""Extension registry for optional VoiceCode features."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .audio_io import AudioIOExtension
from .diarization import DiarizationExtension
from .exporters import ExportersExtension
from .hotwords import HotwordsExtension
from .punctuation import PunctuationExtension
from .quality import QualityExtension
from .vad import VadExtension
from .zh_normalizer import ZhNormalizerExtension

EXTENSIONS = [
    AudioIOExtension(),
    ExportersExtension(),
    HotwordsExtension(),
    VadExtension(),
    ZhNormalizerExtension(),
    QualityExtension(),
    DiarizationExtension(),
    PunctuationExtension(),
]
EXTENSION_BY_ID = {extension.id: extension for extension in EXTENSIONS}


def default_extension_config() -> dict[str, dict[str, Any]]:
    return {extension.id: extension.default_config() for extension in EXTENSIONS}


def extension_config(config: Mapping[str, Any], extension_id: str) -> dict[str, Any]:
    extensions = config.get("extensions", {})
    configured = extensions.get(extension_id, {}) if isinstance(extensions, Mapping) else {}
    defaults = EXTENSION_BY_ID[extension_id].default_config()
    if isinstance(configured, Mapping):
        return {**defaults, **dict(configured)}
    return defaults


def is_enabled(config: Mapping[str, Any], extension_id: str) -> bool:
    return bool(extension_config(config, extension_id).get("enabled", False))


def statuses(config: Mapping[str, Any]) -> list[dict[str, Any]]:
    results = []
    for extension in EXTENSIONS:
        ext_config = extension_config(config, extension.id)
        status = extension.status(ext_config)
        missing = list(status.missing_dependencies)
        available = status.available
        if extension.id == "zh_normalizer":
            if ext_config.get("script") in {"simplified", "traditional"}:
                missing = extension.missing_dependencies()
                available = not missing
            else:
                missing = []
                available = True
        results.append(
            {
                "id": status.id,
                "name": status.name,
                "description": status.description,
                "enabled": status.enabled,
                "available": available,
                "optional_dependencies": status.optional_dependencies,
                "missing_dependencies": missing,
                "config": ext_config,
            }
        )
    return results
