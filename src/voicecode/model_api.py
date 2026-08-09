"""Model management Flask routes."""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import Future
from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Any

from flask import Blueprint, jsonify
from werkzeug.exceptions import HTTPException

logger = logging.getLogger("voicecode.model_api")


@dataclass(frozen=True)
class ModelContext:
    error: Callable[..., Any]
    json_payload: Callable[..., dict[str, Any]]
    validate_config_patch: Callable[[dict[str, Any]], dict[str, Any]]
    env_flag: Callable[[str], bool]
    load_config: Callable[[], dict[str, Any]]
    update_config: Callable[[dict[str, Any]], dict[str, Any]]
    valid_models: set[str]
    valid_devices: set[str]
    valid_compute_types: set[str]
    model_size: Callable[[], str]
    model_state: Callable[[], dict[str, Any]]
    model_loaded: Callable[[], bool]
    model_info: dict[str, Any]
    device: Callable[[], str]
    compute_type: Callable[[], str]
    cpu_threads: Callable[[], int]
    cuda_device_count: Callable[[], int]
    model_cache_dir: Callable[[], Path]
    model_operation_in_progress: Callable[[], bool]
    model_operation_busy_response: Callable[[str], Any]
    model_failure_details: Callable[[BaseException, str], dict[str, Any]]
    set_model_state: Callable[..., None]
    begin_model_operation: Callable[[str], bool]
    model_runtime: Any
    load_model_sync: Callable[..., Any]
    model_reload_done: Callable[[Future, str], None]
    start_model_download_monitor: Callable[[str, Future], None]
    all_model_cache_statuses: Callable[[], dict[str, dict[str, Any]]]
    model_compatibility: Callable[[], dict[str, dict[str, Any]]]
    delete_model_cache: Callable[..., dict[str, Any]]


def create_model_blueprint(context: ModelContext) -> Blueprint:
    blueprint = Blueprint("model_api", __name__)

    @blueprint.route("/reload_model", methods=["POST"])
    def reload_model():
        try:
            payload = context.json_payload()
            reload_patch = {
                key: payload[key]
                for key in (
                    "model",
                    "device",
                    "compute_type",
                    "beam_size",
                    "vad_filter",
                    "condition_on_previous_text",
                    "decode_preset",
                )
                if key in payload
            }
            validated_patch = context.validate_config_patch(reload_patch)
        except ValueError as exc:
            return context.error(str(exc), 400)

        if context.env_flag("VOICECODE_SKIP_MODEL_LOAD"):
            return context.error(
                "Model reload is disabled while VOICECODE_SKIP_MODEL_LOAD is enabled.",
                409,
            )

        current_cfg = context.load_config()
        size = str(validated_patch.get("model", current_cfg.get("model", context.model_size())))
        if size not in context.valid_models:
            return context.error(f"Unsupported model: {size}", 400)
        if context.model_operation_in_progress():
            return context.model_operation_busy_response(size)

        try:
            context.model_cache_dir().mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            failure = context.model_failure_details(exc, size)
            context.set_model_state(
                "error", str(failure["user_message"]), **failure, phase="failed"
            )
            return context.error(str(failure["user_message"]), 500, **failure)

        if not context.begin_model_operation(size):
            return context.model_operation_busy_response(size)
        try:
            current_cfg = context.update_config(validated_patch) if validated_patch else current_cfg
        except HTTPException:
            raise
        except Exception as exc:
            context.set_model_state(
                "error",
                f"Failed to save model configuration: {exc}",
                error_code="model_config_save_failed",
                target_model=size,
                retryable=True,
                phase="failed",
            )
            logger.exception("Failed to save model configuration.")
            return context.error(f"Failed to save model configuration: {exc}", 500)

        future = context.model_runtime.submit(context.load_model_sync, size)
        future.add_done_callback(lambda f: context.model_reload_done(f, size))
        context.start_model_download_monitor(size, future)
        return jsonify(
            {
                "status": "loading",
                "model": size,
                "device": current_cfg.get("device", "auto"),
                "compute_type": current_cfg.get("compute_type", "auto"),
                "condition_on_previous_text": current_cfg.get("condition_on_previous_text", False),
            }
        )

    @blueprint.route("/models")
    def models():
        model_state = context.model_state()
        model_loaded = context.model_loaded()
        return jsonify(
            {
                "current": context.model_size(),
                "configured": context.load_config().get("model", context.model_size()),
                "device": context.device(),
                "compute_type": context.compute_type(),
                "model_loaded": model_loaded,
                "model_state": model_state,
                "models": context.model_info,
                "cache_dir": str(context.model_cache_dir()),
                "cache": context.all_model_cache_statuses(),
                "compatibility": context.model_compatibility(),
                "device_options": sorted(context.valid_devices),
                "compute_type_options": sorted(context.valid_compute_types),
                "cuda_available": context.cuda_device_count() > 0,
                "cpu_threads": context.cpu_threads(),
            }
        )

    @blueprint.route("/models/cache")
    def models_cache():
        return jsonify(
            {
                "cache_dir": str(context.model_cache_dir()),
                "models": context.all_model_cache_statuses(),
            }
        )

    @blueprint.route("/models/<model_name>/download", methods=["POST"])
    def model_download(model_name: str):
        try:
            context.json_payload()
            if model_name not in context.valid_models:
                return context.error(f"Unsupported model: {model_name}", 400)
        except ValueError as exc:
            return context.error(str(exc), 400)

        if context.env_flag("VOICECODE_SKIP_MODEL_LOAD"):
            return context.error("Model loading is disabled by VOICECODE_SKIP_MODEL_LOAD.", 409)

        if context.model_operation_in_progress():
            return context.model_operation_busy_response(model_name)

        try:
            context.model_cache_dir().mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            failure = context.model_failure_details(exc, model_name)
            context.set_model_state(
                "error", str(failure["user_message"]), **failure, phase="failed"
            )
            return context.error(str(failure["user_message"]), 500, **failure)

        if not context.begin_model_operation(model_name):
            return context.model_operation_busy_response(model_name)
        future = context.model_runtime.submit(context.load_model_sync, model_name)
        future.add_done_callback(lambda f: context.model_reload_done(f, model_name))
        context.start_model_download_monitor(model_name, future)
        return jsonify(
            {"status": "loading", "model": model_name, "cache_dir": str(context.model_cache_dir())}
        ), 202

    @blueprint.route("/models/<model_name>/cache", methods=["DELETE", "POST"])
    def model_cache_delete(model_name: str):
        try:
            payload = context.json_payload()
            result = context.delete_model_cache(model_name, confirm=payload.get("confirm") is True)
            return jsonify(result)
        except ValueError as exc:
            return context.error(str(exc), 400)
        except RuntimeError as exc:
            return context.error(str(exc), 409)
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("Failed to delete model cache: %s", model_name)
            return context.error(f"Failed to delete model cache: {exc}", 500)

    return blueprint
