"""Optional punctuation and capitalization restoration using NVIDIA NeMo."""

from __future__ import annotations

import importlib
import threading
from collections.abc import Mapping
from typing import Any

from .base import BaseExtension

_model_lock = threading.RLock()
_model: Any | None = None
_model_key: tuple[str, str] | None = None
_runtime_error: str | None = None


class PunctuationExtension(BaseExtension):
    id = "punctuation"
    name = "Punctuation restoration"
    description = "Optional punctuation/capitalization restoration for post-processing."
    enabled_by_default = False
    optional_dependencies = ["nemo-toolkit"]
    maturity = "experimental"
    restart_required_after_install = True

    def default_config(self) -> dict[str, Any]:
        return {
            "enabled": False,
            "engine": "nemo",
            "model_name": "punctuation_en_bert",
            "device": "auto",
            "supported_languages": ["en"],
        }

    def missing_dependencies(self) -> list[str]:
        try:
            importlib.import_module("nemo.collections.nlp.models")
        except Exception:
            return ["nemo-toolkit"]
        return []

    def operational_status(self, config: Mapping[str, Any]) -> tuple[bool, str | None]:
        if self.missing_dependencies():
            return False, "NeMo is not installed."
        if _runtime_error:
            return False, _runtime_error
        return True, "NeMo is loaded lazily on the first supported-language transcript."


def _resolve_device(value: str) -> str:
    if value in {"cpu", "cuda"}:
        return value
    try:
        torch = importlib.import_module("torch")
        return "cuda" if bool(torch.cuda.is_available()) else "cpu"
    except Exception:
        return "cpu"


def _load_model(config: dict[str, Any]) -> Any:
    global _model, _model_key, _runtime_error
    model_name = str(config.get("model_name", "punctuation_en_bert"))
    device = _resolve_device(str(config.get("device", "auto")))
    key = (model_name, device)
    with _model_lock:
        if _model is not None and _model_key == key:
            return _model
        try:
            models = importlib.import_module("nemo.collections.nlp.models")
            model_class = models.PunctuationCapitalizationModel
            loaded = model_class.from_pretrained(model_name=model_name)
            move = getattr(loaded, "to", None)
            if callable(move):
                loaded = move(device)
            eval_method = getattr(loaded, "eval", None)
            if callable(eval_method):
                eval_method()
            _model = loaded
            _model_key = key
            _runtime_error = None
            return loaded
        except Exception as exc:
            _runtime_error = f"Failed to load NeMo punctuation model: {exc}"
            raise RuntimeError(_runtime_error) from exc


def restore(text: str, language: str | None, config: dict[str, Any]) -> str:
    supported = {str(item).lower() for item in config.get("supported_languages", ["en"])}
    normalized_language = str(language or "auto").lower().split("-", 1)[0]
    if normalized_language not in supported or not text.strip():
        return text
    model = _load_model(config)
    try:
        restored = model.add_punctuation_capitalization([text])
    except Exception as exc:
        global _runtime_error
        _runtime_error = f"NeMo punctuation inference failed: {exc}"
        raise RuntimeError(_runtime_error) from exc
    if isinstance(restored, list) and restored:
        return str(restored[0]).strip()
    return text


def reset_runtime_cache() -> None:
    global _model, _model_key, _runtime_error
    with _model_lock:
        _model = None
        _model_key = None
        _runtime_error = None
