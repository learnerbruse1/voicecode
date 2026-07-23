"""System, audio-device, diagnostics, and performance routes."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
import io
import json
import importlib
import logging
import threading
from typing import Any
import zipfile

from flask import Blueprint, Response, jsonify

from . import dependencies as dependency_manager

logger = logging.getLogger("voicecode.system_api")
_nvml_lock = threading.RLock()
_nvml_initialized = False


@dataclass(frozen=True)
class SystemContext:
    json_payload: Callable[..., dict[str, Any]]
    error: Callable[[str, int], Any]
    load_config: Callable[[], dict[str, Any]]
    query_input_devices: Callable[[], tuple[list[dict[str, Any]], Any]]
    normalize_audio_device: Callable[[Any], Any]
    test_input_level: Callable[..., dict[str, Any]]
    recorder_is_recording: Callable[[], bool]
    runtime_snapshot: Callable[[], dict[str, Any]]
    diagnostics_snapshot: Callable[[], dict[str, Any]]


def _performance_stats(runtime: dict[str, Any]) -> dict[str, Any]:
    cpu = -1.0
    process_cpu = -1.0
    process_memory_mb = -1.0
    system_memory_total_mb = -1.0
    system_memory_available_mb = -1.0
    system_memory_percent = -1.0
    cpu_info: dict[str, Any] = {}
    try:
        psutil = importlib.import_module("psutil")
        process = psutil.Process()
        cpu = psutil.cpu_percent(interval=None)
        process_cpu = process.cpu_percent(interval=None)
        process_memory_mb = round(process.memory_info().rss / 1024**2, 1)
        virtual_memory = psutil.virtual_memory()
        system_memory_total_mb = round(virtual_memory.total / 1024**2, 1)
        system_memory_available_mb = round(virtual_memory.available / 1024**2, 1)
        system_memory_percent = float(virtual_memory.percent)
        cpu_info = {
            "logical_cores": psutil.cpu_count(logical=True),
            "physical_cores": psutil.cpu_count(logical=False),
        }
        cpu_freq = psutil.cpu_freq()
        if cpu_freq:
            cpu_info["current_mhz"] = round(cpu_freq.current, 1)
            cpu_info["max_mhz"] = round(cpu_freq.max, 1)
    except Exception as exc:
        logger.warning("Failed to collect CPU/RAM stats: %s", exc)

    gpu_info = None
    try:
        if int(runtime.get("cuda_device_count", 0)) > 0:
            try:
                pynvml = importlib.import_module("pynvml")
            except Exception:
                pynvml = None
            if pynvml is not None:
                try:
                    global _nvml_initialized
                    with _nvml_lock:
                        if not _nvml_initialized:
                            pynvml.nvmlInit()
                            _nvml_initialized = True
                    driver_version = pynvml.nvmlSystemGetDriverVersion()
                    if isinstance(driver_version, bytes):
                        driver_version = driver_version.decode("utf-8", errors="replace")
                    handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                    gpu_util = pynvml.nvmlDeviceGetUtilizationRates(handle).gpu
                    gpu_mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                    gpu_mem_used = round(gpu_mem_info.used / 1024**2)
                    gpu_mem_total = round(gpu_mem_info.total / 1024**2)
                    gpu_name = pynvml.nvmlDeviceGetName(handle)
                    if isinstance(gpu_name, bytes):
                        gpu_name = gpu_name.decode("utf-8", errors="replace")
                    gpu_info = {
                        "util": gpu_util,
                        "mem_used": gpu_mem_used,
                        "mem_total": gpu_mem_total,
                        "mem_percent": round((gpu_mem_used / gpu_mem_total) * 100, 1)
                        if gpu_mem_total
                        else -1,
                        "name": gpu_name,
                        "driver": driver_version,
                    }
                except Exception as exc:
                    logger.debug("GPU stats unavailable: %s", exc)
                    gpu_info = {"util": -1, "name": "NVIDIA GPU", "driver": None}
            else:
                gpu_info = {"util": -1, "name": "NVIDIA GPU", "driver": None}
    except Exception as exc:
        logger.debug("CUDA device check failed: %s", exc)

    return {
        "device": runtime.get("active_device"),
        "compute_type": runtime.get("active_compute_type"),
        "model": runtime.get("model"),
        "cpu_percent": cpu,
        "process_cpu_percent": process_cpu,
        "ram_mb": process_memory_mb,
        "process_memory_mb": process_memory_mb,
        "system_memory_total_mb": system_memory_total_mb,
        "system_memory_available_mb": system_memory_available_mb,
        "system_memory_percent": system_memory_percent,
        "cpu": cpu_info,
        "gpu": gpu_info,
    }


def _redact_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _redact_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    if not isinstance(value, str):
        return value
    home = str(__import__("pathlib").Path.home())
    return value.replace(home, "~")


def _redacted_config(config: dict[str, Any]) -> dict[str, Any]:
    redacted = json.loads(json.dumps(config))
    hotkey = redacted.get("hotkey")
    if isinstance(hotkey, dict):
        hotkey["key"] = "<redacted>"
    return redacted


def _diagnostics_archive(context: SystemContext) -> bytes:
    diagnostics = context.diagnostics_snapshot()
    diagnostics = _redact_value(
        {key: value for key, value in diagnostics.items() if key not in {"history_entries"}}
    )
    tasks = [task.public_dict() for task in dependency_manager.list_tasks()[:20]]
    for task in tasks:
        log_value = task.get("log", [])
        log_lines = log_value if isinstance(log_value, list) else []
        task["log"] = [_redact_value(str(line)[-500:]) for line in log_lines[-40:]]
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("diagnostics.json", json.dumps(diagnostics, ensure_ascii=False, indent=2))
        archive.writestr(
            "config-redacted.json",
            json.dumps(_redacted_config(context.load_config()), ensure_ascii=False, indent=2),
        )
        archive.writestr("dependency-tasks.json", json.dumps(tasks, ensure_ascii=False, indent=2))
        log_path_value = diagnostics.get("log_file") if isinstance(diagnostics, dict) else None
        if isinstance(log_path_value, str):
            original_log = context.diagnostics_snapshot().get("log_file")
            if isinstance(original_log, str):
                try:
                    lines = (
                        __import__("pathlib")
                        .Path(original_log)
                        .read_text(encoding="utf-8", errors="replace")
                        .splitlines()[-200:]
                    )
                    archive.writestr(
                        "voicecode-log-tail.txt",
                        "\n".join(str(_redact_value(line)) for line in lines),
                    )
                except OSError:
                    pass
    return buffer.getvalue()


def create_system_blueprint(context: SystemContext) -> Blueprint:
    blueprint = Blueprint("system_api", __name__)

    @blueprint.get("/hardware")
    def hardware():
        runtime = context.runtime_snapshot()
        return jsonify(
            {
                "cpu_threads": runtime["cpu_threads"],
                "cuda_available": runtime["cuda_device_count"] > 0,
                "cuda_device_count": runtime["cuda_device_count"],
                "active_device": runtime["active_device"],
                "active_compute_type": runtime["active_compute_type"],
                "supported_devices": runtime["supported_devices"],
                "supported_compute_types": runtime["supported_compute_types"],
                "runtime_supported_compute_types": runtime["runtime_supported_compute_types"],
            }
        )

    @blueprint.get("/audio/devices")
    def audio_devices():
        try:
            devices, default_input = context.query_input_devices()
            return jsonify({"devices": devices, "default_input": default_input})
        except Exception as exc:
            logger.exception("Failed to enumerate audio input devices.")
            return context.error(f"Failed to enumerate audio input devices: {exc}", 503)

    @blueprint.post("/audio/test")
    def audio_test():
        try:
            payload = context.json_payload()
            if context.recorder_is_recording():
                return context.error("Cannot test microphone while recording is active.", 409)
            config = context.load_config()
            device = context.normalize_audio_device(
                payload.get("audio_device", config.get("audio_device", ""))
            )
            duration = payload.get("duration_ms", 1000)
            if isinstance(duration, bool) or not isinstance(duration, int):
                raise ValueError("duration_ms must be an integer between 50 and 5000.")
            result = context.test_input_level(device=device, duration_ms=duration)
            result["device"] = device
            return jsonify(result)
        except ValueError as exc:
            return context.error(str(exc), 400)
        except Exception as exc:
            logger.exception("Failed to test audio input level.")
            return context.error(f"Failed to test audio input level: {exc}", 503)

    @blueprint.get("/diagnostics")
    def diagnostics():
        return jsonify(context.diagnostics_snapshot())

    @blueprint.get("/diagnostics/export")
    def diagnostics_export():
        content = _diagnostics_archive(context)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        response = Response(content, mimetype="application/zip")
        response.headers["Content-Disposition"] = (
            f'attachment; filename="voicecode-diagnostics-{stamp}.zip"'
        )
        response.headers["Cache-Control"] = "no-store"
        return response

    @blueprint.get("/stats")
    def stats():
        return jsonify(_performance_stats(context.runtime_snapshot()))

    return blueprint
