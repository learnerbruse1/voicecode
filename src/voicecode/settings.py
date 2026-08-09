"""Configuration schema, validation, and persistence for VoiceCode."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import copy
import json
import logging
import os

from .extensions.registry import default_extension_config

logger = logging.getLogger("voicecode.settings")

CONFIG_VERSION = 2

VALID_MODELS = {"tiny", "base", "small", "medium", "large-v3", "large-v3-turbo", "distil-large-v3"}
VALID_LANGUAGES = {"", "auto", "zh", "en", "ja", None}
VALID_UI_LANGUAGES = {"en", "zh", "ja"}
VALID_TEXT_MODES = {"plain", "coding", "markdown", "prompt"}
VALID_DEVICES = {"auto", "cpu", "cuda"}
VALID_COMPUTE_TYPES = {"auto", "default", "int8", "int8_float16", "int16", "float16", "float32"}
VALID_TYPING_MODES = {"clipboard", "keystrokes"}
TYPING_DELAY_DEFAULT_MS = 150
TYPING_DELAY_MIN_MS = 0
TYPING_DELAY_MAX_MS = 5000
MODEL_INFO = {
    "tiny": {
        "size": "~75 MB",
        "description": "Fastest, lowest resource usage.",
        "vram_min_gb": 1,
        "vram_recommended_gb": 2,
        "recommendation": "Best for very old CPUs/GPUs and quick tests.",
    },
    "base": {
        "size": "~150 MB",
        "description": "Recommended CPU default.",
        "vram_min_gb": 1,
        "vram_recommended_gb": 2,
        "recommendation": "Good default for dictation on CPU or low VRAM GPUs.",
    },
    "small": {
        "size": "~500 MB",
        "description": "Better accuracy on modern CPUs/GPUs.",
        "vram_min_gb": 2,
        "vram_recommended_gb": 4,
        "recommendation": "Balanced option for most laptops and entry GPUs.",
    },
    "medium": {
        "size": "~1.5 GB",
        "description": "High accuracy, slower on CPU.",
        "vram_min_gb": 5,
        "vram_recommended_gb": 6,
        "recommendation": "Use with 6GB+ VRAM or strong CPUs.",
    },
    "large-v3": {
        "size": "~3 GB",
        "description": "Best multilingual accuracy; GPU recommended.",
        "vram_min_gb": 10,
        "vram_recommended_gb": 12,
        "recommendation": "Use on high VRAM GPUs when maximum accuracy matters.",
    },
    "large-v3-turbo": {
        "size": "~3 GB",
        "description": "Newest Whisper model; faster than large-v3 with similar accuracy.",
        "vram_min_gb": 6,
        "vram_recommended_gb": 8,
        "recommendation": "Best speed/quality choice for 8GB+ NVIDIA GPUs.",
    },
    "distil-large-v3": {
        "size": "~1.5 GB",
        "description": "Fast large-v3 distilled model; NVIDIA GPU recommended.",
        "vram_min_gb": 6,
        "vram_recommended_gb": 8,
        "recommendation": "Fast large-style model for 8GB+ GPUs.",
    },
}
DEFAULT_EXTENSIONS = default_extension_config()

DEFAULT_CONFIG: dict[str, Any] = {
    "config_version": CONFIG_VERSION,
    "hotkey": {"modifiers": ["alt"], "key": "z"},
    "model": "base",
    "device": "auto",
    "compute_type": "auto",
    "condition_on_previous_text": False,
    "beam_size": 5,
    "vad_filter": True,
    "language": "zh",
    "ui_language": "en",
    "audio_device": "",
    "text_mode": "plain",
    "history_enabled": True,
    "history_limit": 50,
    "font_size": "1rem",
    "theme": "system",
    "append_mode": "append",
    "typing_delay_ms": TYPING_DELAY_DEFAULT_MS,
    "typing_mode": "clipboard",
    "on_top": False,
    "onboarding": {"completed": False, "completed_version": "", "skipped": False},
    "extensions": copy.deepcopy(DEFAULT_EXTENSIONS),
}
ALLOWED_CONFIG_KEYS = set(DEFAULT_CONFIG)


def default_config() -> dict[str, Any]:
    return copy.deepcopy(DEFAULT_CONFIG)


def env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def default_config_file() -> str:
    if os.name == "nt":
        base_dir = os.environ.get("APPDATA") or os.path.join(Path.home(), "AppData", "Roaming")
        return os.path.join(base_dir, "VoiceCode", "config.json")
    base_dir = os.environ.get("XDG_CONFIG_HOME") or os.path.join(Path.home(), ".config")
    return os.path.join(base_dir, "voicecode", "config.json")


CONFIG_FILE = os.environ.get("VOICECODE_CONFIG_FILE") or default_config_file()


def config_dir(config_file: str | None = None) -> Path:
    return Path(config_file or CONFIG_FILE).expanduser().resolve().parent


def log_file(config_file: str | None = None) -> Path:
    override = os.environ.get("VOICECODE_LOG_FILE")
    if override:
        return Path(override).expanduser().resolve()
    return config_dir(config_file) / "logs" / "voicecode.log"


def history_file(config_file: str | None = None) -> Path:
    override = os.environ.get("VOICECODE_HISTORY_FILE")
    if override:
        return Path(override).expanduser().resolve()
    return config_dir(config_file) / "history.jsonl"


def normalize_language(language: Any) -> str | None:
    if language in (None, "", "auto"):
        return None
    if language in {"zh", "en", "ja"}:
        return str(language)
    raise ValueError("Unsupported language. Use one of: auto, zh, en, ja.")


def normalize_device_preference(value: Any) -> str:
    if value in (None, ""):
        return "auto"
    if not isinstance(value, str):
        raise ValueError("device must be one of: auto, cpu, cuda.")
    normalized = value.strip().lower()
    if normalized not in VALID_DEVICES:
        raise ValueError("device must be one of: auto, cpu, cuda.")
    return normalized


def normalize_compute_type(value: Any) -> str:
    if value in (None, ""):
        return "auto"
    if not isinstance(value, str):
        raise ValueError(
            "compute_type must be one of: auto, default, int8, int8_float16, int16, float16, float32."
        )
    normalized = value.strip().lower()
    if normalized not in VALID_COMPUTE_TYPES:
        raise ValueError(
            "compute_type must be one of: auto, default, int8, int8_float16, int16, float16, float32."
        )
    return normalized


def _validate_bool(value: Any, name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be a boolean.")
    return value


def _validate_positive_int(value: Any, name: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ValueError(f"{name} must be an integer between {minimum} and {maximum}.")
    return value


def _validate_number(value: Any, name: str, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number between {minimum} and {maximum}.")
    normalized = float(value)
    if not minimum <= normalized <= maximum:
        raise ValueError(f"{name} must be a number between {minimum} and {maximum}.")
    return normalized


def _validate_short_string(value: Any, name: str, maximum: int = 200) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > maximum:
        raise ValueError(f"{name} must be a non-empty string up to {maximum} characters.")
    return value.strip()


def validate_extensions_patch(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("extensions must be an object.")
    unknown = set(value) - set(DEFAULT_EXTENSIONS)
    if unknown:
        raise ValueError("Unknown extension ids: " + ", ".join(sorted(unknown)))

    validated: dict[str, Any] = {}
    for extension_id, patch in value.items():
        if not isinstance(patch, dict):
            raise ValueError(f"extensions.{extension_id} must be an object.")
        allowed_keys = set(DEFAULT_EXTENSIONS[extension_id])
        unknown_keys = set(patch) - allowed_keys
        if unknown_keys:
            raise ValueError(
                f"Unknown config keys for extension '{extension_id}': "
                + ", ".join(sorted(unknown_keys))
            )
        item = dict(patch)
        if "enabled" in item:
            item["enabled"] = _validate_bool(item["enabled"], f"extensions.{extension_id}.enabled")

        if extension_id == "audio_io":
            if "max_upload_mb" in item:
                item["max_upload_mb"] = _validate_positive_int(
                    item["max_upload_mb"], "extensions.audio_io.max_upload_mb", 1, 2048
                )
            if "max_json_seconds" in item:
                item["max_json_seconds"] = _validate_positive_int(
                    item["max_json_seconds"], "extensions.audio_io.max_json_seconds", 1, 7200
                )
            if "sample_rate" in item:
                item["sample_rate"] = _validate_positive_int(
                    item["sample_rate"], "extensions.audio_io.sample_rate", 8000, 192000
                )
            if "allowed_suffixes" in item:
                suffixes = item["allowed_suffixes"]
                if not isinstance(suffixes, list) or not all(isinstance(s, str) for s in suffixes):
                    raise ValueError("extensions.audio_io.allowed_suffixes must be a string array.")
                item["allowed_suffixes"] = [s.strip().lower() for s in suffixes if s.strip()]
        elif extension_id == "exporters":
            if "formats" in item:
                formats = item["formats"]
                allowed_formats = {"json", "txt", "srt", "vtt"}
                if not isinstance(formats, list) or not all(isinstance(f, str) for f in formats):
                    raise ValueError("extensions.exporters.formats must be a string array.")
                normalized = [f.strip().lower() for f in formats]
                unsupported = sorted(set(normalized) - allowed_formats)
                if unsupported:
                    raise ValueError("Unsupported exporter formats: " + ", ".join(unsupported))
                item["formats"] = normalized
        elif extension_id == "hotwords":
            if "phrases" in item:
                phrases = item["phrases"]
                if not isinstance(phrases, list) or not all(isinstance(p, str) for p in phrases):
                    raise ValueError("extensions.hotwords.phrases must be a string array.")
                item["phrases"] = [phrase.strip() for phrase in phrases if phrase.strip()]
        elif extension_id == "vad":
            if "engine" in item:
                engine = item["engine"]
                if engine not in {"faster_whisper", "silero", "off"}:
                    raise ValueError(
                        "extensions.vad.engine must be faster_whisper, silero, or off."
                    )
            if "min_silence_duration_ms" in item:
                item["min_silence_duration_ms"] = _validate_positive_int(
                    item["min_silence_duration_ms"],
                    "extensions.vad.min_silence_duration_ms",
                    100,
                    5000,
                )
            if "speech_pad_ms" in item:
                item["speech_pad_ms"] = _validate_positive_int(
                    item["speech_pad_ms"], "extensions.vad.speech_pad_ms", 0, 2000
                )
            if "threshold" in item:
                item["threshold"] = _validate_number(
                    item["threshold"], "extensions.vad.threshold", 0.0, 1.0
                )
        elif extension_id == "zh_normalizer":
            if "script" in item and item["script"] not in {"none", "simplified", "traditional"}:
                raise ValueError(
                    "extensions.zh_normalizer.script must be none, simplified, or traditional."
                )
            if "normalize_spacing" in item:
                item["normalize_spacing"] = _validate_bool(
                    item["normalize_spacing"], "extensions.zh_normalizer.normalize_spacing"
                )
            if "normalize_punctuation" in item:
                item["normalize_punctuation"] = _validate_bool(
                    item["normalize_punctuation"], "extensions.zh_normalizer.normalize_punctuation"
                )
        elif extension_id == "quality":
            if "metrics" in item:
                metrics = item["metrics"]
                if not isinstance(metrics, list) or not all(isinstance(m, str) for m in metrics):
                    raise ValueError("extensions.quality.metrics must be a string array.")
                normalized = [metric.strip().lower() for metric in metrics]
                unsupported = sorted(set(normalized) - {"wer", "cer"})
                if unsupported:
                    raise ValueError("Unsupported quality metrics: " + ", ".join(unsupported))
                item["metrics"] = normalized
        elif extension_id == "diarization":
            if "engine" in item and item["engine"] != "pyannote":
                raise ValueError("extensions.diarization.engine must be pyannote.")
            for key in ("model_name", "token_env"):
                if key in item:
                    item[key] = _validate_short_string(item[key], f"extensions.diarization.{key}")
            if "device" in item and item["device"] not in {"auto", "cpu", "cuda"}:
                raise ValueError("extensions.diarization.device must be auto, cpu, or cuda.")
            for key in ("min_speakers", "max_speakers"):
                if key in item:
                    item[key] = _validate_positive_int(
                        item[key], f"extensions.diarization.{key}", 1, 32
                    )
            if "exclusive" in item:
                item["exclusive"] = _validate_bool(
                    item["exclusive"], "extensions.diarization.exclusive"
                )
            effective = {**DEFAULT_EXTENSIONS[extension_id], **item}
            if effective["min_speakers"] > effective["max_speakers"]:
                raise ValueError(
                    "extensions.diarization.min_speakers must not exceed max_speakers."
                )
        elif extension_id == "punctuation":
            if "engine" in item and item["engine"] != "nemo":
                raise ValueError("extensions.punctuation.engine must be nemo.")
            if "model_name" in item:
                item["model_name"] = _validate_short_string(
                    item["model_name"], "extensions.punctuation.model_name"
                )
            if "device" in item and item["device"] not in {"auto", "cpu", "cuda"}:
                raise ValueError("extensions.punctuation.device must be auto, cpu, or cuda.")
            if "supported_languages" in item:
                languages = item["supported_languages"]
                if not isinstance(languages, list) or not all(
                    isinstance(language, str) for language in languages
                ):
                    raise ValueError(
                        "extensions.punctuation.supported_languages must be a string array."
                    )
                item["supported_languages"] = [
                    language.strip().lower() for language in languages if language.strip()
                ]
        validated[extension_id] = item
    return validated


def merge_config(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in patch.items():
        if key == "extensions" and isinstance(value, dict):
            current_extensions = copy.deepcopy(merged.get("extensions", DEFAULT_EXTENSIONS))
            for extension_id, extension_patch in value.items():
                current = current_extensions.get(extension_id, {})
                if isinstance(extension_patch, dict):
                    current_extensions[extension_id] = {**current, **extension_patch}
                else:
                    current_extensions[extension_id] = extension_patch
            merged["extensions"] = current_extensions
        else:
            merged[key] = value
    return merged


def validate_config_patch(patch: dict[str, Any]) -> dict[str, Any]:
    unknown = set(patch) - ALLOWED_CONFIG_KEYS
    if unknown:
        raise ValueError(f"Unknown config keys: {', '.join(sorted(unknown))}")

    if "config_version" in patch:
        version = patch["config_version"]
        if isinstance(version, bool) or not isinstance(version, int):
            raise ValueError("config_version must be an integer.")
        if version != CONFIG_VERSION:
            raise ValueError(f"Unsupported config_version: {version}")
    if "model" in patch and patch["model"] not in VALID_MODELS:
        raise ValueError(f"Unsupported model: {patch['model']}")
    if "extensions" in patch:
        patch["extensions"] = validate_extensions_patch(patch["extensions"])
    if "device" in patch:
        patch["device"] = normalize_device_preference(patch["device"])
    if "compute_type" in patch:
        patch["compute_type"] = normalize_compute_type(patch["compute_type"])
    if "beam_size" in patch:
        beam_size = patch["beam_size"]
        if (
            isinstance(beam_size, bool)
            or not isinstance(beam_size, int)
            or not 1 <= beam_size <= 10
        ):
            raise ValueError("beam_size must be an integer between 1 and 10.")
    if "vad_filter" in patch and not isinstance(patch["vad_filter"], bool):
        raise ValueError("vad_filter must be a boolean.")
    if "condition_on_previous_text" in patch and not isinstance(
        patch["condition_on_previous_text"], bool
    ):
        raise ValueError("condition_on_previous_text must be a boolean.")
    if "language" in patch and patch["language"] not in VALID_LANGUAGES:
        raise ValueError("Unsupported language. Use one of: auto, zh, en, ja.")
    if "ui_language" in patch and patch["ui_language"] not in VALID_UI_LANGUAGES:
        raise ValueError("Unsupported UI language. Use one of: en, zh, ja.")
    if "audio_device" in patch and patch["audio_device"] is not None:
        if isinstance(patch["audio_device"], bool) or not isinstance(
            patch["audio_device"], (str, int)
        ):
            raise ValueError("audio_device must be an empty string, device index, or device name.")
    if "text_mode" in patch and patch["text_mode"] not in VALID_TEXT_MODES:
        raise ValueError("Unsupported text mode. Use one of: plain, coding, markdown, prompt.")
    if "history_enabled" in patch and not isinstance(patch["history_enabled"], bool):
        raise ValueError("history_enabled must be a boolean.")
    if "history_limit" in patch:
        limit = patch["history_limit"]
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 500:
            raise ValueError("history_limit must be an integer between 1 and 500.")
    if "append_mode" in patch and patch["append_mode"] not in {"append", "replace"}:
        raise ValueError("Unsupported append mode. Use append or replace.")
    if "typing_mode" in patch and patch["typing_mode"] not in VALID_TYPING_MODES:
        raise ValueError("Unsupported typing mode. Use clipboard or keystrokes.")
    if "typing_delay_ms" in patch:
        patch["typing_delay_ms"] = _validate_positive_int(
            patch["typing_delay_ms"], "typing_delay_ms", TYPING_DELAY_MIN_MS, TYPING_DELAY_MAX_MS
        )
    if "font_size" in patch and patch["font_size"] not in {"0.85rem", "1rem", "1.2rem", "1.5rem"}:
        raise ValueError("Unsupported font size.")
    if "theme" in patch and patch["theme"] not in {"dark", "light", "system"}:
        raise ValueError("Unsupported theme. Use dark, light, or system.")
    if "on_top" in patch and not isinstance(patch["on_top"], bool):
        raise ValueError("on_top must be a boolean.")
    if "onboarding" in patch:
        onboarding = patch["onboarding"]
        if not isinstance(onboarding, dict):
            raise ValueError("onboarding must be an object.")
        allowed_onboarding = {"completed", "completed_version", "skipped"}
        unknown_onboarding = set(onboarding) - allowed_onboarding
        if unknown_onboarding:
            raise ValueError("Unknown onboarding keys: " + ", ".join(sorted(unknown_onboarding)))
        normalized_onboarding = dict(onboarding)
        for bool_key in ("completed", "skipped"):
            if bool_key in normalized_onboarding:
                normalized_onboarding[bool_key] = _validate_bool(
                    normalized_onboarding[bool_key], f"onboarding.{bool_key}"
                )
        if "completed_version" in normalized_onboarding:
            version = normalized_onboarding["completed_version"]
            if not isinstance(version, str) or len(version) > 64:
                raise ValueError("onboarding.completed_version must be a short string.")
            normalized_onboarding["completed_version"] = version.strip()
        patch["onboarding"] = normalized_onboarding
    if "hotkey" in patch:
        hotkey = patch["hotkey"]
        if not isinstance(hotkey, dict):
            raise ValueError("hotkey must be an object.")
        modifiers = hotkey.get("modifiers", [])
        key = hotkey.get("key", "")
        allowed_modifiers = {"alt", "ctrl", "shift"}
        if not isinstance(modifiers, list) or not all(isinstance(m, str) for m in modifiers):
            raise ValueError("hotkey.modifiers must be a string array.")
        normalized_modifiers = [m.strip().lower() for m in modifiers]
        unsupported_modifiers = sorted(set(normalized_modifiers) - allowed_modifiers)
        if unsupported_modifiers:
            raise ValueError("Unsupported hotkey modifiers: " + ", ".join(unsupported_modifiers))
        if not isinstance(key, str) or not key.strip():
            raise ValueError("hotkey.key must be a non-empty string.")
        patch["hotkey"] = {
            "modifiers": normalized_modifiers,
            "key": key.strip().lower(),
        }
    return patch


def migrate_config(data: dict[str, Any]) -> dict[str, Any]:
    migrated = copy.deepcopy(data)
    raw_version = migrated.get("config_version", 1)
    if isinstance(raw_version, bool) or not isinstance(raw_version, int):
        raise ValueError("config_version must be an integer.")
    if raw_version > CONFIG_VERSION:
        raise ValueError(
            f"Config version {raw_version} is newer than supported version {CONFIG_VERSION}."
        )
    version = raw_version
    if version == 1:
        migrated.setdefault(
            "onboarding", {"completed": False, "completed_version": "", "skipped": False}
        )
        migrated["extensions"] = merge_config(
            {"extensions": copy.deepcopy(DEFAULT_EXTENSIONS)},
            {"extensions": migrated.get("extensions", {})},
        )["extensions"]
        version = 2
    migrated["config_version"] = version
    return migrated


def config_schema() -> dict[str, Any]:
    return {
        "version": CONFIG_VERSION,
        "fields": {
            "model": {"type": "select", "choices": sorted(VALID_MODELS)},
            "device": {"type": "select", "choices": sorted(VALID_DEVICES)},
            "compute_type": {"type": "select", "choices": sorted(VALID_COMPUTE_TYPES)},
            "beam_size": {"type": "integer", "minimum": 1, "maximum": 10},
            "condition_on_previous_text": {"type": "boolean"},
            "language": {"type": "select", "choices": ["auto", "zh", "en", "ja"]},
            "ui_language": {"type": "select", "choices": sorted(VALID_UI_LANGUAGES)},
            "typing_delay_ms": {
                "type": "integer",
                "minimum": TYPING_DELAY_MIN_MS,
                "maximum": TYPING_DELAY_MAX_MS,
            },
            "typing_mode": {"type": "select", "choices": sorted(VALID_TYPING_MODES)},
            "history_limit": {"type": "integer", "minimum": 1, "maximum": 500},
        },
    }


def load_config(config_file: str | None = None) -> dict[str, Any]:
    resolved = config_file or CONFIG_FILE
    if os.path.exists(resolved):
        try:
            with open(resolved, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                data = migrate_config(data)
                known_data = {k: v for k, v in data.items() if k in ALLOWED_CONFIG_KEYS}
                cfg = merge_config(copy.deepcopy(DEFAULT_CONFIG), known_data)
                try:
                    return validate_config_patch(cfg)
                except ValueError as exc:
                    logger.warning("Ignoring invalid config file '%s': %s", resolved, exc)
                    return default_config()
            logger.warning("Ignoring config file because it does not contain a JSON object.")
        except Exception as exc:
            logger.warning("Failed to read config file '%s': %s", resolved, exc)
    return default_config()


def save_config(cfg: dict[str, Any], config_file: str | None = None) -> None:
    cfg = {**dict(cfg), "config_version": CONFIG_VERSION}
    cfg = validate_config_patch(cfg)
    config_path = Path(config_file or CONFIG_FILE).expanduser()
    config_dir(config_file or CONFIG_FILE).mkdir(parents=True, exist_ok=True)
    tmp = config_path.with_name(f"{config_path.name}.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    os.replace(tmp, config_path)
