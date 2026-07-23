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


_CONFIG_CHOICES: dict[str, dict[str, list[str]]] = {
    "exporters": {"formats": ["json", "txt", "srt", "vtt"]},
    "vad": {"engine": ["faster_whisper", "silero", "off"]},
    "zh_normalizer": {"script": ["none", "simplified", "traditional"]},
    "quality": {"metrics": ["wer", "cer"]},
    "diarization": {"engine": ["pyannote"]},
    "punctuation": {"engine": ["nemo"]},
}


def config_schema(extension_id: str) -> list[dict[str, Any]]:
    """Return a small UI-oriented schema derived from the authoritative defaults."""
    defaults = EXTENSION_BY_ID[extension_id].default_config()
    choices = _CONFIG_CHOICES.get(extension_id, {})
    fields: list[dict[str, Any]] = []
    for name, default in defaults.items():
        field: dict[str, Any] = {"name": name, "default": default}
        if name in choices:
            field["type"] = "multiselect" if isinstance(default, list) else "select"
            field["choices"] = choices[name]
        elif isinstance(default, bool):
            field["type"] = "boolean"
        elif isinstance(default, int):
            field["type"] = "integer"
        elif isinstance(default, list):
            field["type"] = "string_list"
        else:
            field["type"] = "string"
        fields.append(field)
    return fields


_REQUIRED_DEPENDENCY_IDS: dict[str, tuple[str, ...]] = {
    "quality": ("jiwer",),
    "diarization": ("pyannote-audio",),
    "punctuation": ("nemo-toolkit",),
}


def required_dependency_ids(extension_id: str, config: Mapping[str, Any]) -> tuple[str, ...]:
    ext_config = extension_config(config, extension_id)
    if not bool(ext_config.get("enabled", False)):
        return ()
    if extension_id == "vad":
        return ("silero-vad",) if ext_config.get("engine") == "silero" else ()
    if extension_id == "zh_normalizer":
        return (
            ("opencc-python-reimplemented",)
            if ext_config.get("script") in {"simplified", "traditional"}
            else ()
        )
    return _REQUIRED_DEPENDENCY_IDS.get(extension_id, ())


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
