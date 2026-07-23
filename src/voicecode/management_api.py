"""Flask blueprint for onboarding, extensions, and dependency management."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from flask import Blueprint, jsonify

from . import dependencies as dependency_manager
from . import settings as settings_store
from .extensions import registry as extension_registry

JsonPayload = Callable[..., dict[str, Any]]
ErrorResponse = Callable[[str, int], Any]


@dataclass(frozen=True)
class ManagementContext:
    load_config: Callable[[], dict[str, Any]]
    save_config: Callable[[dict[str, Any]], None]
    json_payload: JsonPayload
    error: ErrorResponse
    reset_dependency_runtime_cache: Callable[[str], None]
    model_summary: Callable[[], dict[str, Any]]
    audio_summary: Callable[[], dict[str, Any]]
    version: str


def _extension_statuses(config: dict[str, Any]) -> list[dict[str, Any]]:
    statuses = extension_registry.statuses(config)
    for status in statuses:
        dependencies = dependency_manager.dependencies_for_feature_status(str(status["id"]))
        status["dependencies"] = dependencies
        required_ids = set(extension_registry.required_dependency_ids(str(status["id"]), config))
        status["required_dependency_ids"] = sorted(required_ids)
        status["missing_dependency_ids"] = [
            str(item["id"])
            for item in dependencies
            if str(item["id"]) in required_ids and not bool(item["installed"])
        ]
        status["config_schema"] = extension_registry.config_schema(str(status["id"]))
        status["ready"] = bool(status.get("operational")) and not status["missing_dependency_ids"]
    return statuses


def create_management_blueprint(context: ManagementContext) -> Blueprint:
    blueprint = Blueprint("management_api", __name__)

    @blueprint.get("/extensions")
    def extensions():
        config = context.load_config()
        return jsonify({"extensions": _extension_statuses(config)})

    @blueprint.post("/extensions/<extension_id>")
    def update_extension(extension_id: str):
        if extension_id not in extension_registry.EXTENSION_BY_ID:
            return context.error(f"Unknown extension: {extension_id}", 404)
        try:
            payload = context.json_payload()
        except ValueError as exc:
            return context.error(str(exc), 400)
        raw_patch = payload.get("config", payload)
        if not isinstance(raw_patch, dict):
            return context.error("Extension config must be an object.", 400)
        try:
            extension_patch = settings_store.validate_extensions_patch({extension_id: raw_patch})
            config = settings_store.merge_config(
                context.load_config(), {"extensions": extension_patch}
            )
            context.save_config(config)
        except ValueError as exc:
            return context.error(str(exc), 400)
        status = next(item for item in _extension_statuses(config) if item["id"] == extension_id)
        return jsonify({"status": "saved", "extension": status})

    @blueprint.post("/extensions/<extension_id>/install")
    def install_extension_dependencies(extension_id: str):
        try:
            context.json_payload()
        except ValueError as exc:
            return context.error(str(exc), 400)
        if extension_id not in extension_registry.EXTENSION_BY_ID:
            return context.error(f"Unknown extension: {extension_id}", 404)
        tasks = []
        try:
            for status in dependency_manager.dependencies_for_feature_status(extension_id):
                if not bool(status["installed_in_voice_dep"]):
                    task = dependency_manager.start_install(str(status["id"]))
                    tasks.append(task.public_dict())
        except (ValueError, RuntimeError) as exc:
            return context.error(str(exc), 409)
        return jsonify({"status": "started", "tasks": tasks}), 202 if tasks else 200

    @blueprint.get("/dependencies")
    def dependencies():
        config = context.load_config()
        enabled_features = {
            str(item["id"])
            for item in _extension_statuses(config)
            if item.get("enabled") and item.get("missing_dependency_ids")
        }
        missing = dependency_manager.missing_dependencies()
        action_required = [
            item
            for item in missing
            if item.get("required")
            or any(str(feature) in enabled_features for feature in item.get("feature_ids", []))
        ]
        return jsonify(
            {
                "install_dir": str(dependency_manager.dependency_dir()),
                "dependencies": dependency_manager.all_dependency_statuses(),
                "missing": missing,
                "action_required_missing": action_required,
            }
        )

    @blueprint.post("/dependencies/install-required")
    def install_required_dependencies():
        try:
            context.json_payload()
        except ValueError as exc:
            return context.error(str(exc), 400)
        tasks = []
        try:
            for status in dependency_manager.missing_dependencies(required_only=True):
                tasks.append(dependency_manager.start_install(str(status["id"])).public_dict())
        except (ValueError, RuntimeError) as exc:
            return context.error(str(exc), 409)
        return jsonify({"status": "started", "tasks": tasks}), 202 if tasks else 200

    @blueprint.post("/dependencies/<dependency_id>/install")
    def dependency_install(dependency_id: str):
        try:
            context.json_payload()
            task = dependency_manager.start_install(dependency_id)
        except ValueError as exc:
            return context.error(str(exc), 400)
        except RuntimeError as exc:
            return context.error(str(exc), 409)
        return jsonify({"task": task.public_dict()}), 200 if task.status == "completed" else 202

    @blueprint.post("/dependencies/<dependency_id>/uninstall")
    def dependency_uninstall(dependency_id: str):
        try:
            payload = context.json_payload()
        except ValueError as exc:
            return context.error(str(exc), 400)
        try:
            result = dependency_manager.uninstall_dependency(
                dependency_id, confirm=payload.get("confirm") is True
            )
            context.reset_dependency_runtime_cache(dependency_id)
        except ValueError as exc:
            status = 404 if str(exc).startswith("Unknown dependency") else 400
            return context.error(str(exc), status)
        except RuntimeError as exc:
            return context.error(str(exc), 409)
        return jsonify(result)

    @blueprint.get("/dependencies/tasks")
    def dependency_tasks():
        return jsonify({"tasks": [task.public_dict() for task in dependency_manager.list_tasks()]})

    @blueprint.post("/dependencies/tasks/<task_id>/cancel")
    def dependency_task_cancel(task_id: str):
        try:
            context.json_payload()
            task = dependency_manager.cancel_task(task_id)
        except ValueError as exc:
            status = 404 if str(exc).startswith("Unknown dependency task") else 400
            return context.error(str(exc), status)
        return jsonify({"task": task.public_dict()})

    @blueprint.get("/dependencies/tasks/<task_id>")
    def dependency_task(task_id: str):
        try:
            return jsonify({"task": dependency_manager.get_task(task_id).public_dict()})
        except ValueError as exc:
            return context.error(str(exc), 404)

    @blueprint.get("/onboarding")
    def onboarding_status():
        config = context.load_config()
        onboarding = config.get("onboarding", {})
        missing_required = dependency_manager.missing_dependencies(required_only=True)
        audio = context.audio_summary()
        model = context.model_summary()
        completed = bool(onboarding.get("completed", False))
        return jsonify(
            {
                "required": not completed,
                "completed": completed,
                "skipped": bool(onboarding.get("skipped", False)),
                "completed_version": str(onboarding.get("completed_version", "")),
                "version": context.version,
                "steps": {
                    "runtime": {
                        "ready": not missing_required,
                        "missing": missing_required,
                    },
                    "audio": audio,
                    "model": model,
                },
                "config": {
                    key: config.get(key)
                    for key in (
                        "ui_language",
                        "language",
                        "model",
                        "device",
                        "compute_type",
                        "audio_device",
                        "hotkey",
                    )
                },
            }
        )

    @blueprint.post("/onboarding/complete")
    def onboarding_complete():
        try:
            payload = context.json_payload()
        except ValueError as exc:
            return context.error(str(exc), 400)
        preferences = payload.get("config", {})
        if not isinstance(preferences, dict):
            return context.error("config must be an object.", 400)
        allowed = {
            "ui_language",
            "language",
            "model",
            "device",
            "compute_type",
            "audio_device",
            "hotkey",
        }
        unknown = set(preferences) - allowed
        if unknown:
            return context.error(
                "Unsupported onboarding config keys: " + ", ".join(sorted(unknown)), 400
            )
        skipped = payload.get("skipped", False)
        if not isinstance(skipped, bool):
            return context.error("skipped must be a boolean.", 400)
        try:
            patch = settings_store.validate_config_patch(dict(preferences))
            patch["onboarding"] = {
                "completed": True,
                "completed_version": context.version,
                "skipped": skipped,
            }
            config = settings_store.merge_config(context.load_config(), patch)
            context.save_config(config)
        except ValueError as exc:
            return context.error(str(exc), 400)
        return jsonify({"status": "completed", "config": config})

    @blueprint.post("/onboarding/reset")
    def onboarding_reset():
        try:
            context.json_payload()
        except ValueError as exc:
            return context.error(str(exc), 400)
        config = settings_store.merge_config(
            context.load_config(),
            {"onboarding": {"completed": False, "completed_version": "", "skipped": False}},
        )
        context.save_config(config)
        return jsonify({"status": "reset", "onboarding": config["onboarding"]})

    return blueprint
