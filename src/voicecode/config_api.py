"""Configuration, status, health, and client-logging Flask routes."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
import os
from typing import Any

from flask import Blueprint, jsonify
from werkzeug.exceptions import HTTPException

logger = logging.getLogger("voicecode.config_api")


@dataclass(frozen=True)
class ConfigContext:
    error: Callable[..., Any]
    json_payload: Callable[..., dict[str, Any]]
    load_config: Callable[[], dict[str, Any]]
    save_config: Callable[[dict[str, Any]], None]
    update_config: Callable[[dict[str, Any]], dict[str, Any]]
    validate_config_patch: Callable[[dict[str, Any]], dict[str, Any]]
    request_id: Callable[[], str]
    config_schema: Callable[[], dict[str, Any]]
    default_config: Callable[[], dict[str, Any]]
    model_state: Callable[[], dict[str, Any]]
    model_loaded: Callable[[], bool]
    model_size: Callable[[], str]
    recording: Callable[[], bool]
    partial_text: Callable[[], str]
    partial_active: Callable[[], bool]
    missing_required_dependencies: Callable[[], list[dict[str, object]]]
    version: str


def create_config_blueprint(context: ConfigContext) -> Blueprint:
    blueprint = Blueprint("config_api", __name__)

    @blueprint.route("/health")
    def health():
        return jsonify({"status": "ok", "pid": os.getpid()})

    @blueprint.route("/status")
    def status():
        model_state = context.model_state()
        model_loaded = context.model_loaded()
        return jsonify(
            {
                "status": "ok",
                "version": context.version,
                "model": context.model_size(),
                "configured_model": context.load_config().get("model", context.model_size()),
                "recording": context.recording(),
                "partial_text": context.partial_text(),
                "partial_active": context.partial_active(),
                "model_loaded": model_loaded,
                "model_state": model_state,
                "missing_required_dependencies": context.missing_required_dependencies(),
            }
        )

    @blueprint.route("/config")
    def get_config():
        return jsonify(context.load_config())

    @blueprint.route("/config/schema")
    def get_config_schema():
        return jsonify(context.config_schema())

    @blueprint.route("/config/reset", methods=["POST"])
    def reset_config():
        try:
            context.json_payload()
            cfg = context.default_config()
            context.save_config(cfg)
            logger.info("Configuration reset to defaults: id=%s", context.request_id())
            return jsonify(cfg)
        except ValueError as exc:
            return context.error(str(exc), 400)
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("Failed to reset config.")
            return context.error(f"Failed to reset config: {exc}", 500)

    @blueprint.route("/config", methods=["POST"])
    def post_config():
        try:
            patch = context.validate_config_patch(context.json_payload())
            cfg = context.update_config(patch)
            return jsonify(cfg)
        except ValueError as exc:
            return context.error(str(exc), 400)
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("Failed to save config.")
            return context.error(f"Failed to save config: {exc}", 500)

    @blueprint.route("/log", methods=["POST"])
    def client_log():
        try:
            payload = context.json_payload()
        except ValueError as exc:
            return context.error(str(exc), 400)
        msg = str(payload.get("msg", ""))
        component = str(payload.get("component", "frontend"))
        level = str(payload.get("level", "info")).lower()
        log_method = (
            getattr(logger, level, logger.info)
            if level in {"debug", "info", "warning", "error"}
            else logger.info
        )
        log_method("Frontend log: component=%s message=%s", component, msg)
        return "", 204

    return blueprint
