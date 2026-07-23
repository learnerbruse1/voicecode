import atexit
from pathlib import Path
import logging
import multiprocessing
import platform
import os
import secrets
import sys
import threading
import time
import uuid
from concurrent.futures import Future
from logging.handlers import RotatingFileHandler
from collections.abc import Callable
from typing import Any
from urllib.parse import urlsplit


def _configure_console_encoding() -> None:
    """Prefer UTF-8 console I/O so PowerShell/cmd do not garble messages."""
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                # Keep startup resilient; logging is configured below.
                pass


_configure_console_encoding()

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

import importlib  # noqa: E402

import numpy as np  # noqa: E402
from flask import Flask, Response, g, jsonify, request, send_from_directory  # noqa: E402
from werkzeug.exceptions import BadRequest, HTTPException, UnsupportedMediaType  # noqa: E402

from . import dependencies as dependency_manager  # noqa: E402
from . import __version__  # noqa: E402
from .management_api import ManagementContext, create_management_blueprint  # noqa: E402
from .model_cache import ModelCacheService  # noqa: E402
from .model_runtime import ModelRuntime  # noqa: E402
from .recording_api import RecordingContext, create_recording_blueprint  # noqa: E402
from .history_api import HistoryContext, create_history_blueprint  # noqa: E402
from .system_api import SystemContext, create_system_blueprint  # noqa: E402
from . import history as history_store  # noqa: E402
from . import settings as settings_store  # noqa: E402

dependency_manager.ensure_dependency_path()

ctranslate2: Any | None
WhisperModel: Any | None

try:  # noqa: SIM105
    ctranslate2 = importlib.import_module("ctranslate2")
except Exception as exc:  # pragma: no cover - exercised through dependency status
    ctranslate2 = None
    _ctranslate2_import_error: BaseException | None = exc
else:
    _ctranslate2_import_error = None

try:  # noqa: SIM105
    _faster_whisper = importlib.import_module("faster_whisper")
    WhisperModel = _faster_whisper.WhisperModel
except Exception as exc:  # pragma: no cover - exercised through dependency status
    WhisperModel = None
    _faster_whisper_import_error: BaseException | None = exc
else:
    _faster_whisper_import_error = None

from .audio import (  # noqa: E402
    Recorder,
    normalize_audio_device as _normalize_audio_device,
    query_input_devices as _query_input_devices,
    test_input_level as _test_input_level,
)
from .extensions import registry as extension_registry  # noqa: E402
from .text_processing import post_process_text as _post_process_text  # noqa: E402
from .transcription_service import TranscriptionService  # noqa: E402

logging.basicConfig(
    level=os.environ.get("VOICECODE_LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("voicecode.app")


def _env_int(name: str, default: int, minimum: int = 1) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return max(minimum, int(raw))
    except ValueError:
        logger.warning("Ignoring invalid integer environment variable %s=%s", name, raw)
        return default


app = Flask(__name__, static_folder="static")
app.config["MAX_CONTENT_LENGTH"] = _env_int("VOICECODE_MAX_UPLOAD_MB", 512) * 1024 * 1024

_API_TOKEN = os.environ.get("VOICECODE_API_TOKEN") or secrets.token_urlsafe(32)
_API_TOKEN_HEADER = "X-VoiceCode-Token"
_MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _token_protection_disabled() -> bool:
    if app.config.get("VOICECODE_DISABLE_API_TOKEN") is True:
        return True
    if app.config.get("TESTING") and not app.config.get("VOICECODE_FORCE_API_TOKEN"):
        return True
    return os.environ.get("VOICECODE_DISABLE_API_TOKEN", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _token_is_valid(value: str | None) -> bool:
    if value is None:
        return False
    return secrets.compare_digest(value, _API_TOKEN)


def _loopback_hostname(value: str) -> bool:
    return value.lower().rstrip(".") in {"127.0.0.1", "localhost", "::1"}


def _request_host_is_allowed() -> bool:
    hostname = urlsplit(f"//{request.host}").hostname
    return bool(hostname and _loopback_hostname(hostname))


def _request_origin_is_allowed() -> bool:
    origin = request.headers.get("Origin")
    if not origin:
        return True
    parsed = urlsplit(origin)
    request_port = urlsplit(f"//{request.host}").port or (443 if request.scheme == "https" else 80)
    origin_port = parsed.port or (443 if parsed.scheme == "https" else 80)
    return (
        parsed.scheme in {"http", "https"}
        and bool(parsed.hostname and _loopback_hostname(parsed.hostname))
        and origin_port == request_port
    )


@app.before_request
def _log_request_start() -> None:
    g.request_id = uuid.uuid4().hex[:12]
    g.request_started_at = time.perf_counter()
    logger.debug(
        "Request started: id=%s method=%s path=%s remote=%s content_type=%s",
        g.request_id,
        request.method,
        request.path,
        request.remote_addr,
        request.content_type,
    )
    if not _request_host_is_allowed():
        return _error("Invalid local Host header.", 421)
    if request.method in _MUTATING_METHODS and not _request_origin_is_allowed():
        return _error("Cross-origin mutation requests are not allowed.", 403)
    if (
        request.method in _MUTATING_METHODS
        and not _token_protection_disabled()
        and not _token_is_valid(request.headers.get(_API_TOKEN_HEADER))
    ):
        return _error("Invalid or missing local API token.", 403)
    return None


@app.after_request
def _log_request_done(response):  # noqa: ANN001
    elapsed_ms = (
        time.perf_counter() - getattr(g, "request_started_at", time.perf_counter())
    ) * 1000
    logger.info(
        "Request completed: id=%s method=%s path=%s status=%s duration_ms=%.1f",
        getattr(g, "request_id", "unknown"),
        request.method,
        request.path,
        response.status_code,
        elapsed_ms,
    )
    response.headers.setdefault("X-VoiceCode-Request-ID", getattr(g, "request_id", "unknown"))
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault(
        "Permissions-Policy", "camera=(), geolocation=(), payment=(), usb=()"
    )
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; connect-src 'self'; font-src 'self'; "
        "object-src 'none'; base-uri 'none'; frame-ancestors 'none'",
    )
    if request.path.startswith(("/static/", "/css/", "/js/")):
        response.headers.setdefault("Cache-Control", "no-cache")
    if request.method in _MUTATING_METHODS:
        logger.info(
            "AUDIT mutation: id=%s method=%s path=%s status=%s remote=%s",
            getattr(g, "request_id", "unknown"),
            request.method,
            request.path,
            response.status_code,
            request.remote_addr,
        )
    return response


PORT = int(os.environ.get("PORT", 7788))
MODEL_SIZE = os.environ.get("WHISPER_MODEL", "base")
VALID_MODELS = settings_store.VALID_MODELS
VALID_DEVICES = settings_store.VALID_DEVICES
VALID_COMPUTE_TYPES = settings_store.VALID_COMPUTE_TYPES
MODEL_INFO = settings_store.MODEL_INFO
DEFAULT_CONFIG = settings_store.DEFAULT_CONFIG
ALLOWED_CONFIG_KEYS = settings_store.ALLOWED_CONFIG_KEYS
CONFIG_FILE = settings_store.CONFIG_FILE


def _load_ctranslate2_runtime():  # noqa: ANN202
    global ctranslate2, _ctranslate2_import_error
    if ctranslate2 is not None:
        return ctranslate2
    dependency_manager.ensure_dependency_path()
    try:
        ctranslate2 = importlib.import_module("ctranslate2")
    except Exception as exc:
        _ctranslate2_import_error = exc
        raise RuntimeError(
            "Missing dependency 'ctranslate2'. Open Dependencies in the left sidebar and "
            "install the Whisper runtime into VOICE_DEP."
        ) from exc
    _ctranslate2_import_error = None
    return ctranslate2


def _load_whisper_model_class():  # noqa: ANN202
    global WhisperModel, _faster_whisper_import_error
    if WhisperModel is not None:
        return WhisperModel
    dependency_manager.ensure_dependency_path()
    try:
        module = importlib.import_module("faster_whisper")
        WhisperModel = module.WhisperModel
    except Exception as exc:
        _faster_whisper_import_error = exc
        raise RuntimeError(
            "Missing dependency 'faster-whisper'. Open Dependencies in the left sidebar and "
            "install the Whisper runtime into VOICE_DEP."
        ) from exc
    _faster_whisper_import_error = None
    return WhisperModel


def _cuda_device_count() -> int:
    try:
        runtime = _load_ctranslate2_runtime()
        return int(runtime.get_cuda_device_count())
    except Exception as exc:
        logger.debug("CUDA detection failed: %s", exc)
        return 0


def _gpu_memory_total_mb() -> int | None:
    try:
        if _cuda_device_count() <= 0:
            return None
        try:
            import pynvml
        except Exception:
            return None
        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        gpu_mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
        return round(gpu_mem_info.total / 1024**2)
    except Exception as exc:
        logger.debug("Failed to query GPU total memory: %s", exc)
        return None


def _metadata_float(info: dict[str, Any], key: str, default: float = 0.0) -> float:
    value = info.get(key, default)
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float, str)):
        try:
            return float(value)
        except ValueError:
            return default
    return default


def _model_vram_requirement_gb(size: str) -> float:
    return _metadata_float(MODEL_INFO.get(size, {}), "vram_min_gb")


def _gpu_has_enough_vram(size: str) -> tuple[bool, int | None, float]:
    total_mb = _gpu_memory_total_mb()
    required_gb = _model_vram_requirement_gb(size)
    if total_mb is None or required_gb <= 0:
        return True, total_mb, required_gb
    return total_mb / 1024 >= required_gb, total_mb, required_gb


def _default_cpu_threads() -> int:
    configured = os.environ.get("WHISPER_CPU_THREADS")
    if configured:
        try:
            return max(1, int(configured))
        except ValueError:
            logger.warning("Ignoring invalid WHISPER_CPU_THREADS value: %s", configured)
    return max(2, multiprocessing.cpu_count() // 2)


def _normalize_device_preference(value: Any) -> str:
    return settings_store.normalize_device_preference(value)


def _normalize_compute_type(value: Any) -> str:
    return settings_store.normalize_compute_type(value)


def _supported_compute_types(device: str) -> set[str]:
    if device == "cpu":
        return {"auto", "int8", "float32"}
    try:
        runtime = _load_ctranslate2_runtime()
        return {str(item) for item in runtime.get_supported_compute_types(device)}
    except Exception as exc:
        logger.debug("Failed to query supported compute types for %s: %s", device, exc)
        return {"auto", "float16", "int8_float16"}


def _auto_compute_type(device: str) -> str:
    supported = _supported_compute_types(device)
    preferences = (
        ("float16", "int8_float16", "int8", "float32")
        if device == "cuda"
        else ("int8", "int16", "float32")
    )
    for candidate in preferences:
        if not supported or candidate in supported:
            return candidate
    return "float16" if device == "cuda" else "int8"


def _resolve_device_profile(
    device: str = "auto", compute_type: str = "auto"
) -> tuple[str, str, int]:
    requested_device = _normalize_device_preference(os.environ.get("WHISPER_DEVICE", device))
    requested_compute = _normalize_compute_type(
        os.environ.get("WHISPER_COMPUTE_TYPE", compute_type)
    )
    cuda_available = _cuda_device_count() > 0
    actual_device = "cuda" if requested_device in {"auto", "cuda"} and cuda_available else "cpu"
    if requested_compute in {"auto", "default"}:
        actual_compute = _auto_compute_type(actual_device)
    else:
        actual_compute = requested_compute
    return actual_device, actual_compute, _default_cpu_threads()


def _best_device() -> tuple[str, str, int]:
    return _resolve_device_profile("auto", "auto")


_device, _compute_type, _cpu_threads = _best_device()
_model_runtime = ModelRuntime(
    model_name=MODEL_SIZE,
    device=_device,
    compute_type=_compute_type,
    cpu_threads=_cpu_threads,
)
model: Any | None = None
model_lock = _model_runtime.model_lock
_executor = _model_runtime.executor
atexit.register(_model_runtime.shutdown)
atexit.register(dependency_manager.shutdown_tasks)
_config_lock = threading.Lock()
_cancel_lock = threading.Lock()
_cancel_token = 0
_model_state_lock = _model_runtime.state_lock
_model_state = _model_runtime.state


def _model_error_message(exc: BaseException) -> str:
    return (
        "Whisper model is unavailable. The model may be missing, blocked by the network, "
        f"or rejected by the model host. Details: {exc}"
    )


def _set_model_state(status_value: str, error: str | None = None) -> None:
    _model_runtime.set_state(status_value, error)


def _sync_model_runtime() -> None:
    _model_runtime.set_profile(_device, _compute_type, _cpu_threads)
    _model_runtime.set_model(model, MODEL_SIZE)


def _estimated_model_bytes(model_name: str) -> int:
    estimates = {
        "tiny": 75,
        "base": 150,
        "small": 500,
        "medium": 1500,
        "large-v3": 3000,
        "large-v3-turbo": 3000,
        "distil-large-v3": 1500,
    }
    return estimates.get(model_name, 500) * 1024 * 1024


def _monitor_model_download(model_name: str, future: Future) -> None:
    estimated = _estimated_model_bytes(model_name)
    previous_bytes = 0
    previous_time = time.monotonic()
    while not future.done():
        try:
            current = int(_model_cache_service.status(model_name, force=True)["size_bytes"])
        except Exception:
            current = previous_bytes
        now = time.monotonic()
        elapsed = max(0.001, now - previous_time)
        speed = max(0, round((current - previous_bytes) / elapsed))
        with _model_state_lock:
            if _model_state.get("status") == "loading":
                _model_state.update(
                    {
                        "downloaded_bytes": current,
                        "estimated_bytes": estimated,
                        "download_speed_bps": speed,
                        "progress": min(99, round(current / estimated * 100)) if estimated else 0,
                    }
                )
        previous_bytes = current
        previous_time = now
        time.sleep(0.5)


def _start_model_download_monitor(model_name: str, future: Future) -> None:
    threading.Thread(target=_monitor_model_download, args=(model_name, future), daemon=True).start()


def _model_cache_dir() -> Path:
    configured = os.environ.get("VOICECODE_MODEL_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    runtime_dir = os.environ.get("VOICECODE_RUNTIME_DIR")
    if runtime_dir:
        return (Path(runtime_dir).expanduser().resolve() / "models").resolve()
    return (dependency_manager.project_root() / "models").resolve()


def _whisper_model_kwargs(device: str, compute_type: str, cpu_threads: int) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "device": device,
        "compute_type": compute_type,
        "cpu_threads": cpu_threads,
        "download_root": str(_model_cache_dir()),
    }
    if _env_flag("VOICECODE_OFFLINE"):
        kwargs["local_files_only"] = True
    return kwargs


def _load_model_sync(size: str | None = None, *, allow_cpu_fallback: bool = True) -> Any:
    """Load a Whisper model with CUDA auto-detection and safe CPU fallback."""
    global MODEL_SIZE, _compute_type, _cpu_threads, _device, model

    requested_size = size or MODEL_SIZE
    cfg = load_config()
    preferred_device = _normalize_device_preference(cfg.get("device", "auto"))
    preferred_compute = _normalize_compute_type(cfg.get("compute_type", "auto"))
    _device, _compute_type, _cpu_threads = _resolve_device_profile(
        preferred_device, preferred_compute
    )
    if _device == "cuda":
        enough_vram, total_vram_mb, required_vram_gb = _gpu_has_enough_vram(requested_size)
        if not enough_vram:
            detected_gb = round((total_vram_mb or 0) / 1024, 1)
            message = (
                f"Model '{requested_size}' requires at least {required_vram_gb:g}GB VRAM for CUDA; "
                f"detected {detected_gb:g}GB."
            )
            if preferred_device == "auto":
                logger.warning("%s Falling back to CPU int8 because device is auto.", message)
                _device, _compute_type, _cpu_threads = "cpu", "int8", _default_cpu_threads()
            else:
                raise RuntimeError(message)

    logger.info("Loading Whisper model '%s' on %s (%s)...", requested_size, _device, _compute_type)
    whisper_model_class = _load_whisper_model_class()
    try:
        loaded_model = whisper_model_class(
            requested_size,
            **_whisper_model_kwargs(_device, _compute_type, _cpu_threads),
        )
    except Exception as exc:
        if not allow_cpu_fallback or _device == "cpu":
            raise RuntimeError(_model_error_message(exc)) from exc
        logger.warning(
            "Failed to initialize %s inference (%s). Falling back to CPU int8.",
            _device,
            exc,
        )
        _device, _compute_type, _cpu_threads = "cpu", "int8", _default_cpu_threads()
        try:
            loaded_model = whisper_model_class(
                requested_size,
                **_whisper_model_kwargs("cpu", "int8", _cpu_threads),
            )
        except Exception as cpu_exc:
            raise RuntimeError(_model_error_message(cpu_exc)) from cpu_exc

    with model_lock:
        model = loaded_model
        MODEL_SIZE = requested_size
    _sync_model_runtime()
    logger.info("Whisper model is ready: %s/%s", _device, _compute_type)
    return loaded_model


def _model_unavailable_reason() -> str | None:
    with model_lock:
        current_model = model
    if current_model is not None:
        return None

    with _model_state_lock:
        status_value = _model_state["status"]
        error = _model_state["error"]
    if status_value == "loading":
        return "Whisper model is still loading. Please try again in a moment."
    if error:
        return error
    return "Whisper model is not loaded yet. Please reload the model and try again."


def _ensure_model_loaded() -> Any:
    reason = _model_unavailable_reason()
    if reason:
        raise RuntimeError(reason)
    with model_lock:
        if model is None:
            raise RuntimeError(
                "Whisper model is not loaded yet. Please reload the model and try again."
            )
        return model


def _env_flag(name: str) -> bool:
    return settings_store.env_flag(name)


def _start_initial_model_load() -> None:
    if _env_flag("VOICECODE_SKIP_MODEL_LOAD"):
        _set_model_state(
            "skipped", "Whisper model loading is disabled by VOICECODE_SKIP_MODEL_LOAD."
        )
        logger.info(
            "Skipping initial Whisper model load because VOICECODE_SKIP_MODEL_LOAD is enabled."
        )
        return

    with _model_state_lock:
        if _model_state["status"] == "loading":
            return
        _model_state.update(
            {"status": "loading", "error": None, "progress": 0, "downloaded_bytes": 0}
        )

    future = _model_runtime.submit(_load_model_sync, MODEL_SIZE)
    future.add_done_callback(lambda f: _model_reload_done(f, MODEL_SIZE))
    _start_model_download_monitor(MODEL_SIZE, future)


def _sync_config_file() -> None:
    settings_store.CONFIG_FILE = CONFIG_FILE


def _default_config_file() -> str:
    return settings_store.default_config_file()


def _config_dir() -> Path:
    _sync_config_file()
    return settings_store.config_dir(CONFIG_FILE)


def _log_file() -> Path:
    _sync_config_file()
    return settings_store.log_file(CONFIG_FILE)


def _history_file() -> Path:
    _sync_config_file()
    return settings_store.history_file(CONFIG_FILE)


def _configure_file_logging() -> None:
    if _env_flag("VOICECODE_DISABLE_FILE_LOG"):
        return
    log_file = _log_file()
    try:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        root_logger = logging.getLogger()
        log_file_text = str(log_file)
        for handler in root_logger.handlers:
            if getattr(handler, "baseFilename", None) == log_file_text:
                return
        handler = RotatingFileHandler(
            log_file,
            maxBytes=_env_int("VOICECODE_LOG_MAX_BYTES", 1_000_000),
            backupCount=_env_int("VOICECODE_LOG_BACKUP_COUNT", 5, minimum=0),
            encoding="utf-8",
        )
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s"))
        root_logger.addHandler(handler)
    except Exception as exc:
        logger.warning("Failed to configure file logging: %s", exc)


def _json_payload() -> dict[str, Any]:
    raw_body = request.get_data(cache=True)
    if not raw_body or not raw_body.strip():
        return {}
    try:
        payload = request.get_json(silent=False)
    except (BadRequest, UnsupportedMediaType) as exc:
        raise ValueError("JSON payload must be a valid object.") from exc
    if not isinstance(payload, dict):
        raise ValueError("JSON payload must be an object.")
    return payload


def _error(message: str, status_code: int):
    logger.warning(
        "Request failed: id=%s status=%s error=%s",
        getattr(g, "request_id", "unknown"),
        status_code,
        message,
    )
    return jsonify(
        {"error": message, "request_id": getattr(g, "request_id", "unknown")}
    ), status_code


@app.errorhandler(HTTPException)
def _handle_http_exception(exc: HTTPException):
    description = exc.description if isinstance(exc.description, str) else exc.name
    return _error(description or exc.name, exc.code or 500)


@app.errorhandler(Exception)
def _handle_unexpected_exception(exc: Exception):
    logger.exception(
        "Unhandled request exception: id=%s method=%s path=%s",
        getattr(g, "request_id", "unknown"),
        request.method if request else "unknown",
        request.path if request else "unknown",
    )
    return _error("Internal server error. Check VoiceCode logs with the request_id.", 500)


def _normalize_language(language: Any) -> str | None:
    return settings_store.normalize_language(language)


def _validate_config_patch(patch: dict[str, Any]) -> dict[str, Any]:
    return settings_store.validate_config_patch(patch)


def _get_cancel_token() -> int:
    with _cancel_lock:
        return _cancel_token


def _bump_cancel_token() -> int:
    global _cancel_token
    with _cancel_lock:
        _cancel_token += 1
        return _cancel_token


def load_config() -> dict[str, Any]:
    _sync_config_file()
    with _config_lock:
        return settings_store.load_config(CONFIG_FILE)


def save_config(cfg: dict[str, Any]) -> None:
    _sync_config_file()
    with _config_lock:
        settings_store.save_config(cfg, CONFIG_FILE)


_transcription_service = TranscriptionService(load_config, _post_process_text)


STATIC_DIR = os.environ.get("VOICECODE_STATIC_DIR") or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "static"
)


@app.route("/")
def index():
    index_path = Path(STATIC_DIR) / "index.html"
    try:
        html = index_path.read_text(encoding="utf-8")
    except OSError:
        return send_from_directory(STATIC_DIR, "index.html")
    token_meta = f'<meta name="voicecode-api-token" content="{_API_TOKEN}">'
    version_meta = f'<meta name="voicecode-version" content="{__version__}">'
    injected_meta = "\n".join((token_meta, version_meta))
    if "voicecode-api-token" not in html:
        html = html.replace("<head>", f"<head>\n{injected_meta}", 1)
    response = Response(html, mimetype="text/html")
    response.headers["Cache-Control"] = "no-store"
    return response


@app.route("/css/<path:filename>")
def css_asset(filename: str):
    return send_from_directory(os.path.join(STATIC_DIR, "css"), filename)


@app.route("/js/<path:filename>")
def js_asset(filename: str):
    return send_from_directory(os.path.join(STATIC_DIR, "js"), filename)


@app.route("/health")
def health():
    return jsonify({"status": "ok", "pid": os.getpid()})


@app.route("/status")
def status():
    with _model_state_lock:
        model_state = dict(_model_state)
    with model_lock:
        model_loaded = model is not None
    return jsonify(
        {
            "status": "ok",
            "version": __version__,
            "model": MODEL_SIZE,
            "recording": _recorder.is_recording(),
            "model_loaded": model_loaded,
            "model_state": model_state,
            "missing_required_dependencies": dependency_manager.missing_dependencies(
                required_only=True
            ),
        }
    )


@app.route("/config", methods=["GET"])
def get_config():
    return jsonify(load_config())


@app.route("/config/schema")
def get_config_schema():
    return jsonify(settings_store.config_schema())


@app.route("/config/reset", methods=["POST"])
def reset_config():
    try:
        cfg = settings_store.default_config()
        save_config(cfg)
        logger.info("Configuration reset to defaults: id=%s", getattr(g, "request_id", "unknown"))
        return jsonify(cfg)
    except Exception as exc:
        logger.exception("Failed to reset config.")
        return _error(f"Failed to reset config: {exc}", 500)


@app.route("/config", methods=["POST"])
def post_config():
    try:
        patch = _validate_config_patch(_json_payload())
        cfg = settings_store.merge_config(load_config(), patch)
        save_config(cfg)
        return jsonify(cfg)
    except ValueError as exc:
        return _error(str(exc), 400)
    except Exception as exc:
        logger.exception("Failed to save config.")
        return _error(f"Failed to save config: {exc}", 500)


def _model_reload_done(future: Future, size: str) -> None:
    try:
        future.result()
    except Exception as exc:
        logger.exception("Failed to reload Whisper model '%s'.", size)
        with model_lock:
            has_active_model = model is not None
        if has_active_model:
            _set_model_state(
                "ready",
                f"Failed to reload Whisper model '{size}'. The previous model remains active. Details: {exc}",
            )
        else:
            _set_model_state("error", str(exc))
    else:
        logger.info("Whisper model reloaded: %s", size)
        _set_model_state("ready")


@app.route("/reload_model", methods=["POST"])
def reload_model():
    try:
        payload = _json_payload()
        current_cfg = load_config()
        reload_patch = {
            key: payload[key]
            for key in ("model", "device", "compute_type", "beam_size", "vad_filter")
            if key in payload
        }
        validated_patch = _validate_config_patch(reload_patch)
        size = str(validated_patch.get("model", current_cfg.get("model", MODEL_SIZE)))
        if size not in VALID_MODELS:
            return _error(f"Unsupported model: {size}", 400)
    except ValueError as exc:
        return _error(str(exc), 400)

    if _env_flag("VOICECODE_SKIP_MODEL_LOAD"):
        return _error(
            "Model reload is disabled while VOICECODE_SKIP_MODEL_LOAD is enabled.",
            409,
        )

    with _model_state_lock:
        if _model_state["status"] == "loading":
            return _error("A model reload is already in progress.", 409)
        _model_state.update(
            {"status": "loading", "error": None, "progress": 0, "downloaded_bytes": 0}
        )

    if validated_patch:
        current_cfg.update(validated_patch)
        save_config(current_cfg)

    future = _model_runtime.submit(_load_model_sync, size)
    future.add_done_callback(lambda f: _model_reload_done(f, size))
    _start_model_download_monitor(size, future)
    return jsonify(
        {
            "status": "loading",
            "model": size,
            "device": current_cfg.get("device", "auto"),
            "compute_type": current_cfg.get("compute_type", "auto"),
        }
    )


@app.route("/log", methods=["POST"])
def client_log():
    try:
        payload = _json_payload()
    except ValueError:
        payload = {}
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


def _append_history(entry: dict[str, Any]) -> None:
    history_store.append_history(_history_file(), entry)


def _read_history(
    limit: int = 50, *, query: str = "", language: str = "", model_name: str = ""
) -> list[dict[str, Any]]:
    return history_store.read_history(
        _history_file(), limit, query=query, language=language, model=model_name
    )


def _read_all_history() -> list[dict[str, Any]]:
    return history_store.read_all_history(_history_file())


_recorder = Recorder()

# Hook set by main.py.
on_transcription: Callable[[str], None] | None = None


def _language_prompt(language: str | None) -> str | None:
    return _transcription_service.language_prompt(language)


def _is_cuda_runtime_error(exc: BaseException) -> bool:
    message = str(exc).lower()
    return any(token in message for token in ("cuda", "cublas", "cudnn", "gpu"))


def _transcribe_kwargs(language: str | None, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    return _transcription_service.transcribe_kwargs(language, cfg)


def _fallback_to_cpu_model() -> Any:
    global _compute_type, _cpu_threads, _device, model

    _device, _compute_type, _cpu_threads = "cpu", "int8", _default_cpu_threads()
    whisper_model_class = _load_whisper_model_class()
    try:
        loaded_model = whisper_model_class(
            MODEL_SIZE,
            **_whisper_model_kwargs("cpu", "int8", _cpu_threads),
        )
    except Exception as load_exc:
        raise RuntimeError(_model_error_message(load_exc)) from load_exc
    model = loaded_model
    _sync_model_runtime()
    _set_model_state("ready", "GPU inference failed; VoiceCode fell back to CPU int8.")
    return loaded_model


def _transcribe_audio(audio: np.ndarray | str, language: str | None = None) -> dict[str, Any]:
    global model

    cfg = load_config()
    prepared_audio, vad_metadata = _transcription_service.prepare_audio(audio, cfg)
    if isinstance(prepared_audio, np.ndarray) and prepared_audio.size == 0:
        return {
            "text": "",
            "language": language or "auto",
            "segments": [],
            "vad": vad_metadata,
            "_audio_context": prepared_audio,
        }
    kwargs = _transcribe_kwargs(language, cfg)
    with model_lock:
        active_model = model
        if active_model is None:
            raise RuntimeError(_model_unavailable_reason() or "Whisper model is not available.")
        try:
            segments, info = active_model.transcribe(prepared_audio, **kwargs)
            segment_list = list(segments)
            text = " ".join(s.text for s in segment_list).strip()
        except RuntimeError as exc:
            if not _is_cuda_runtime_error(exc):
                raise
            logger.warning("GPU inference failed (%s). Reloading model on CPU int8.", exc)
            active_model = _fallback_to_cpu_model()
            segments, info = active_model.transcribe(prepared_audio, **kwargs)
            segment_list = list(segments)
            text = " ".join(s.text for s in segment_list).strip()
    language_name = getattr(info, "language", language or "auto")
    probability = getattr(info, "language_probability", None)
    result: dict[str, Any] = {
        "text": text,
        "language": language_name,
        "_audio_context": prepared_audio,
    }
    serializable_segments = []
    for segment in segment_list:
        start = getattr(segment, "start", None)
        end = getattr(segment, "end", None)
        if start is not None or end is not None:
            serializable_segments.append(
                {"start": float(start or 0.0), "end": float(end or 0.0), "text": segment.text}
            )
    if serializable_segments:
        result["segments"] = serializable_segments
    if vad_metadata is not None:
        result["vad"] = vad_metadata
    if probability is not None:
        result["language_probability"] = probability
    return result


def _coerce_audio_samples(value: Any) -> np.ndarray:
    return _transcription_service.coerce_audio_samples(value)


def _finalize_transcription_result(result: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    return _transcription_service.finalize(result, cfg)


def _model_operation_in_progress() -> bool:
    return _model_runtime.operation_in_progress()


def _model_is_loaded() -> bool:
    with model_lock:
        return model is not None


_model_cache_service = ModelCacheService(
    cache_dir=_model_cache_dir,
    model_info=MODEL_INFO,
    active_model=lambda: MODEL_SIZE,
    model_loaded=_model_is_loaded,
    operation_in_progress=_model_operation_in_progress,
)


def _model_cache_status(model_name: str, *, force: bool = False) -> dict[str, Any]:
    return _model_cache_service.status(model_name, force=force)


def _all_model_cache_statuses() -> dict[str, dict[str, Any]]:
    return _model_cache_service.all_statuses()


def _delete_model_cache(model_name: str, *, confirm: bool = False) -> dict[str, Any]:
    result = _model_cache_service.delete(model_name, confirm=confirm)
    result["cache"] = _model_cache_status(model_name)
    return result


def _model_compatibility() -> dict[str, dict[str, Any]]:
    cfg = load_config()
    configured_device = str(cfg.get("device", "auto"))
    total_vram_mb = _gpu_memory_total_mb()
    total_vram_gb = round(total_vram_mb / 1024, 1) if total_vram_mb is not None else None
    compatibility: dict[str, dict[str, Any]] = {}
    for model_name, info in MODEL_INFO.items():
        min_vram_gb = _metadata_float(info, "vram_min_gb")
        recommended_vram_gb = _metadata_float(info, "vram_recommended_gb", min_vram_gb)
        cuda_selectable = True
        reason = None
        if (
            configured_device == "cuda"
            and total_vram_gb is not None
            and total_vram_gb < min_vram_gb
        ):
            cuda_selectable = False
            reason = (
                f"Current NVIDIA GPU has {total_vram_gb:g}GB VRAM; "
                f"{model_name} requires at least {min_vram_gb:g}GB."
            )
        compatibility[model_name] = {
            "configured_device": configured_device,
            "detected_vram_gb": total_vram_gb,
            "vram_min_gb": min_vram_gb,
            "vram_recommended_gb": recommended_vram_gb,
            "selectable": cuda_selectable,
            "reason": reason,
        }
    return compatibility


def _action_required_dependencies() -> list[dict[str, object]]:
    enabled_missing_features = {
        str(item.get("id"))
        for item in extension_registry.statuses(load_config())
        if item.get("enabled") and item.get("missing_dependencies")
    }
    results: list[dict[str, object]] = []
    for item in dependency_manager.missing_dependencies():
        feature_ids = item.get("feature_ids", [])
        if item.get("required") or (
            isinstance(feature_ids, list)
            and any(str(feature_id) in enabled_missing_features for feature_id in feature_ids)
        ):
            results.append(item)
    return results


def _reset_dependency_runtime_cache(dependency_id: str) -> None:
    """Drop module-level runtime handles that may point at removed VOICE_DEP files."""
    global WhisperModel, ctranslate2, model
    if dependency_id == "whisper-runtime":
        WhisperModel = None
        ctranslate2 = None
        with model_lock:
            model = None
        _sync_model_runtime()
        _set_model_state(
            "error",
            "Whisper runtime was uninstalled. Install it from Dependencies and reload the model.",
        )
    elif dependency_id == "audio-capture":
        # The audio module lazy-loads sounddevice, so clearing its cache lets an
        # immediately reinstalled package become usable without restarting Python.
        try:
            from . import audio as audio_module

            audio_module.sd = None
        except Exception as exc:  # pragma: no cover - defensive cache refresh
            logger.debug("Failed to reset audio dependency cache: %s", exc)
    elif dependency_id in {"silero-vad", "pyannote-audio", "nemo-toolkit"}:
        try:
            module_names = {
                "silero-vad": "voicecode.extensions.vad",
                "pyannote-audio": "voicecode.extensions.diarization",
                "nemo-toolkit": "voicecode.extensions.punctuation",
            }
            extension_runtime = importlib.import_module(module_names[dependency_id])
            extension_runtime.reset_runtime_cache()
        except Exception as exc:  # pragma: no cover - defensive cache refresh
            logger.debug("Failed to reset extension dependency cache: %s", exc)


@app.route("/models")
def models():
    with _model_state_lock:
        model_state = dict(_model_state)
    with model_lock:
        model_loaded = model is not None
    return jsonify(
        {
            "current": MODEL_SIZE,
            "device": _device,
            "compute_type": _compute_type,
            "model_loaded": model_loaded,
            "model_state": model_state,
            "models": MODEL_INFO,
            "cache_dir": str(_model_cache_dir()),
            "cache": _all_model_cache_statuses(),
            "compatibility": _model_compatibility(),
            "device_options": sorted(VALID_DEVICES),
            "compute_type_options": sorted(VALID_COMPUTE_TYPES),
            "cuda_available": _cuda_device_count() > 0,
            "cpu_threads": _cpu_threads,
        }
    )


@app.route("/models/cache")
def models_cache():
    return jsonify({"cache_dir": str(_model_cache_dir()), "models": _all_model_cache_statuses()})


@app.route("/models/<model_name>/download", methods=["POST"])
def model_download(model_name: str):
    try:
        _json_payload()
        if model_name not in VALID_MODELS:
            return _error(f"Unsupported model: {model_name}", 400)
    except ValueError as exc:
        return _error(str(exc), 400)

    if _env_flag("VOICECODE_SKIP_MODEL_LOAD"):
        return _error("Model loading is disabled by VOICECODE_SKIP_MODEL_LOAD.", 409)

    with _model_state_lock:
        if _model_state["status"] == "loading":
            return _error("A model load is already in progress.", 409)
        _model_state.update(
            {"status": "loading", "error": None, "progress": 0, "downloaded_bytes": 0}
        )

    try:
        _model_cache_dir().mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        _set_model_state("error", str(exc))
        return _error(f"Failed to create model cache directory: {exc}", 500)

    future = _model_runtime.submit(_load_model_sync, model_name)
    future.add_done_callback(lambda f: _model_reload_done(f, model_name))
    _start_model_download_monitor(model_name, future)
    return jsonify(
        {"status": "loading", "model": model_name, "cache_dir": str(_model_cache_dir())}
    ), 202


@app.route("/models/<model_name>/cache", methods=["DELETE", "POST"])
def model_cache_delete(model_name: str):
    try:
        payload = _json_payload()
        result = _delete_model_cache(model_name, confirm=payload.get("confirm") is True)
        return jsonify(result)
    except ValueError as exc:
        return _error(str(exc), 400)
    except RuntimeError as exc:
        return _error(str(exc), 409)
    except Exception as exc:
        logger.exception("Failed to delete model cache: %s", model_name)
        return _error(f"Failed to delete model cache: {exc}", 500)


def start_server() -> None:
    from waitress import serve  # type: ignore[import-untyped]

    _configure_file_logging()
    _start_initial_model_load()
    logger.info("Starting HTTP server on 127.0.0.1:%s", PORT)
    serve(app, host="127.0.0.1", port=PORT, threads=4)


def _deliver_transcription(text_value: str, request_cancel_token: int) -> None:
    if on_transcription is None:
        return
    if request_cancel_token == _get_cancel_token():
        on_transcription(text_value)
    else:
        logger.info("Transcription result suppressed because the request was cancelled.")


def _system_runtime_snapshot() -> dict[str, Any]:
    cuda_count = _cuda_device_count()
    return {
        "cpu_threads": _default_cpu_threads(),
        "cuda_device_count": cuda_count,
        "active_device": _device,
        "active_compute_type": _compute_type,
        "model": MODEL_SIZE,
        "supported_devices": sorted(VALID_DEVICES),
        "supported_compute_types": sorted(VALID_COMPUTE_TYPES),
        "runtime_supported_compute_types": {
            "cpu": sorted(_supported_compute_types("cpu")),
            "cuda": sorted(_supported_compute_types("cuda")) if cuda_count > 0 else [],
        },
    }


def _system_diagnostics_snapshot() -> dict[str, Any]:
    with _model_state_lock:
        model_state = dict(_model_state)
    with model_lock:
        model_loaded = model is not None
    return {
        "app": "VoiceCode",
        "version": __version__,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "port": PORT,
        "config_file": CONFIG_FILE,
        "log_file": str(_log_file()),
        "history_file": str(_history_file()),
        "static_dir": STATIC_DIR,
        "model": MODEL_SIZE,
        "model_loaded": model_loaded,
        "model_state": model_state,
        "device": _device,
        "compute_type": _compute_type,
        "cuda_device_count": _cuda_device_count(),
        "cpu_threads": _cpu_threads,
        "runtime_dir": os.environ.get("VOICECODE_RUNTIME_DIR"),
        "model_dir": os.environ.get("VOICECODE_MODEL_DIR"),
        "extensions": extension_registry.statuses(load_config()),
        "dependencies": {
            "install_dir": str(dependency_manager.dependency_dir()),
            "missing": dependency_manager.missing_dependencies(),
        },
    }


def _management_model_summary() -> dict[str, Any]:
    with _model_state_lock:
        state = dict(_model_state)
    with model_lock:
        loaded = model is not None
    config = load_config()
    recommended_model = "small" if _cuda_device_count() > 0 else "base"
    return {
        "ready": loaded and state.get("status") == "ready",
        "loaded": loaded,
        "state": state,
        "configured_model": config.get("model", "base"),
        "recommended_model": recommended_model,
        "device": _device,
        "compute_type": _compute_type,
    }


def _management_audio_summary() -> dict[str, Any]:
    try:
        devices, default_input = _query_input_devices()
    except Exception as exc:
        return {"ready": False, "devices": [], "default_input": None, "error": str(exc)}
    return {
        "ready": bool(devices),
        "devices": devices,
        "default_input": default_input,
        "error": None,
    }


app.register_blueprint(
    create_recording_blueprint(
        RecordingContext(
            error=_error,
            json_payload=_json_payload,
            load_config=load_config,
            normalize_language=_normalize_language,
            normalize_audio_device=_normalize_audio_device,
            model_unavailable_reason=_model_unavailable_reason,
            recorder=_recorder,
            transcribe_audio=_transcribe_audio,
            finalize_result=_finalize_transcription_result,
            coerce_audio_samples=_coerce_audio_samples,
            append_history=_append_history,
            model_name=lambda: MODEL_SIZE,
            get_cancel_token=_get_cancel_token,
            bump_cancel_token=_bump_cancel_token,
            deliver_transcription=_deliver_transcription,
        )
    )
)


app.register_blueprint(
    create_system_blueprint(
        SystemContext(
            json_payload=_json_payload,
            error=_error,
            load_config=load_config,
            query_input_devices=_query_input_devices,
            normalize_audio_device=_normalize_audio_device,
            test_input_level=_test_input_level,
            recorder_is_recording=_recorder.is_recording,
            runtime_snapshot=_system_runtime_snapshot,
            diagnostics_snapshot=_system_diagnostics_snapshot,
        )
    )
)


app.register_blueprint(
    create_history_blueprint(
        HistoryContext(history_file=_history_file, json_payload=_json_payload, error=_error)
    )
)


app.register_blueprint(
    create_management_blueprint(
        ManagementContext(
            load_config=load_config,
            save_config=save_config,
            json_payload=_json_payload,
            error=_error,
            reset_dependency_runtime_cache=_reset_dependency_runtime_cache,
            model_summary=_management_model_summary,
            audio_summary=_management_audio_summary,
            version=__version__,
        )
    )
)
