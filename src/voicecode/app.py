import atexit
from pathlib import Path
import logging
import multiprocessing
import platform
import os
import sys
import threading
import time
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from collections.abc import Callable
from typing import Any


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

import ctranslate2  # type: ignore[import-untyped]  # noqa: E402
import numpy as np  # noqa: E402
import sounddevice as sd  # type: ignore[import-untyped]  # noqa: E402
from faster_whisper import WhisperModel  # type: ignore[import-untyped]  # noqa: E402
from flask import Flask, Response, g, jsonify, request, send_from_directory  # noqa: E402
from werkzeug.exceptions import BadRequest, UnsupportedMediaType  # noqa: E402

from . import history as history_store  # noqa: E402
from . import settings as settings_store  # noqa: E402
from .audio import Recorder, normalize_audio_device as _normalize_audio_device  # noqa: E402
from .extensions import audio_io, exporters, hotwords, registry as extension_registry, vad  # noqa: E402
from .extensions import punctuation, zh_normalizer  # noqa: E402
from .text_processing import post_process_text as _post_process_text  # noqa: E402

logging.basicConfig(
    level=os.environ.get("VOICECODE_LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("voicecode.app")

app = Flask(__name__, static_folder="static")


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


def _cuda_device_count() -> int:
    try:
        return int(ctranslate2.get_cuda_device_count())
    except Exception as exc:
        logger.debug("CUDA detection failed: %s", exc)
        return 0


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
    try:
        return {str(item) for item in ctranslate2.get_supported_compute_types(device)}
    except Exception as exc:
        logger.debug("Failed to query supported compute types for %s: %s", device, exc)
        return set()


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
model: WhisperModel | None = None
model_lock = threading.RLock()

_executor = ThreadPoolExecutor(max_workers=1)
atexit.register(lambda: _executor.shutdown(wait=False))
_config_lock = threading.Lock()
_cancel_lock = threading.Lock()
_cancel_token = 0
_model_state_lock = threading.Lock()
_model_state: dict[str, str | None] = {"status": "not_loaded", "error": None}


def _model_error_message(exc: BaseException) -> str:
    return (
        "Whisper model is unavailable. The model may be missing, blocked by the network, "
        f"or rejected by the model host. Details: {exc}"
    )


def _set_model_state(status_value: str, error: str | None = None) -> None:
    with _model_state_lock:
        _model_state["status"] = status_value
        _model_state["error"] = error


def _whisper_model_kwargs(device: str, compute_type: str, cpu_threads: int) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "device": device,
        "compute_type": compute_type,
        "cpu_threads": cpu_threads,
    }
    model_dir = os.environ.get("VOICECODE_MODEL_DIR")
    if model_dir:
        kwargs["download_root"] = str(Path(model_dir).expanduser())
    if _env_flag("VOICECODE_OFFLINE"):
        kwargs["local_files_only"] = True
    return kwargs


def _load_model_sync(size: str | None = None, *, allow_cpu_fallback: bool = True) -> WhisperModel:
    """Load a Whisper model with CUDA auto-detection and safe CPU fallback."""
    global MODEL_SIZE, _compute_type, _cpu_threads, _device, model

    requested_size = size or MODEL_SIZE
    cfg = load_config()
    preferred_device = _normalize_device_preference(cfg.get("device", "auto"))
    preferred_compute = _normalize_compute_type(cfg.get("compute_type", "auto"))
    _device, _compute_type, _cpu_threads = _resolve_device_profile(
        preferred_device, preferred_compute
    )

    logger.info("Loading Whisper model '%s' on %s (%s)...", requested_size, _device, _compute_type)
    try:
        loaded_model = WhisperModel(
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
            loaded_model = WhisperModel(
                requested_size,
                **_whisper_model_kwargs("cpu", "int8", _cpu_threads),
            )
        except Exception as cpu_exc:
            raise RuntimeError(_model_error_message(cpu_exc)) from cpu_exc

    with model_lock:
        model = loaded_model
        MODEL_SIZE = requested_size
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


def _ensure_model_loaded() -> WhisperModel:
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
        _model_state["status"] = "loading"
        _model_state["error"] = None

    future = _executor.submit(_load_model_sync, MODEL_SIZE)
    future.add_done_callback(lambda f: _model_reload_done(f, MODEL_SIZE))


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
            maxBytes=int(os.environ.get("VOICECODE_LOG_MAX_BYTES", "1000000")),
            backupCount=int(os.environ.get("VOICECODE_LOG_BACKUP_COUNT", "5")),
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


STATIC_DIR = os.environ.get("VOICECODE_STATIC_DIR") or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "static"
)


@app.route("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")


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
            "model": MODEL_SIZE,
            "recording": _recorder.is_recording(),
            "model_loaded": model_loaded,
            "model_state": model_state,
        }
    )


@app.route("/config", methods=["GET"])
def get_config():
    return jsonify(load_config())


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
        _model_state["status"] = "loading"
        _model_state["error"] = None

    if validated_patch:
        current_cfg.update(validated_patch)
        save_config(current_cfg)

    future = _executor.submit(_load_model_sync, size)
    future.add_done_callback(lambda f: _model_reload_done(f, size))
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


def _read_history(limit: int = 50) -> list[dict[str, Any]]:
    return history_store.read_history(_history_file(), limit)


_recorder = Recorder()

# Hook set by main.py.
on_transcription: Callable[[str], None] | None = None


@app.route("/record/start", methods=["POST"])
def record_start():
    try:
        reason = _model_unavailable_reason()
        if reason:
            return _error(
                f"Cannot start recording because Whisper model is unavailable: {reason}", 503
            )
        payload = _json_payload()
        _normalize_language(payload.get("language", "zh"))
        cfg = load_config()
        device = _normalize_audio_device(payload.get("audio_device", cfg.get("audio_device", "")))
        started = _recorder.start(device=device)
        return jsonify({"status": "recording", "started": started})
    except ValueError as exc:
        return _error(str(exc), 400)
    except Exception as exc:
        return _error(f"Failed to start recording: {exc}", 503)


@app.route("/record/stop", methods=["POST"])
def record_stop():
    request_cancel_token = _get_cancel_token()
    try:
        payload = _json_payload()
        lang = _normalize_language(payload.get("language"))
    except ValueError as exc:
        return _error(str(exc), 400)

    audio = _recorder.stop_and_get()
    if len(audio) == 0:
        logger.info("Recording stopped with no audio samples.")
        return jsonify({"text": "", "language": lang or "auto"})

    try:
        result = _transcribe_audio(audio, lang)
        cfg = load_config()
        result = _finalize_transcription_result(result, cfg)
        if cfg.get("history_enabled", True) and result["text"]:
            _append_history(
                {
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "language": result.get("language"),
                    "model": MODEL_SIZE,
                    "text": result["text"],
                }
            )
    except RuntimeError as exc:
        logger.warning("Transcription is unavailable: %s", exc)
        return _error(f"Transcription is unavailable: {exc}", 503)
    except Exception as exc:
        logger.exception("Transcription failed.")
        return _error(f"Transcription failed: {exc}", 500)

    logger.info(
        "Transcription completed: language=%s chars=%d",
        result.get("language"),
        len(result.get("text", "")),
    )
    if on_transcription and result["text"]:
        if request_cancel_token == _get_cancel_token():
            on_transcription(result["text"])
        else:
            logger.info("Transcription result suppressed because the request was cancelled.")
    return jsonify(result)


@app.route("/record/cancel", methods=["POST"])
def record_cancel():
    _bump_cancel_token()
    _recorder.stop_and_get()
    logger.info("Recording/transcription cancellation requested.")
    return jsonify({"status": "cancelled"})


def _language_prompt(language: str | None) -> str | None:
    if language == "zh":
        return "Transcribe the speech as Simplified Chinese text."
    if language == "ja":
        return "Transcribe the speech as Japanese text."
    return None


def _is_cuda_runtime_error(exc: BaseException) -> bool:
    message = str(exc).lower()
    return any(token in message for token in ("cuda", "cublas", "cudnn", "gpu"))


def _transcribe_kwargs(language: str | None) -> dict[str, Any]:
    cfg = load_config()
    beam_size = int(cfg.get("beam_size", 5))
    vad_config = extension_registry.extension_config(cfg, "vad")
    hotwords_config = extension_registry.extension_config(cfg, "hotwords")
    initial_prompt = _language_prompt(language)
    if extension_registry.is_enabled(cfg, "hotwords"):
        initial_prompt = hotwords.build_prompt(initial_prompt, hotwords_config)
    kwargs: dict[str, Any] = {
        "language": language,
        "task": "transcribe",
        "beam_size": beam_size,
        "best_of": 1,
        "condition_on_previous_text": False,
        "initial_prompt": initial_prompt,
        "temperature": 0.0,
    }
    kwargs.update(vad.transcribe_options(vad_config, bool(cfg.get("vad_filter", True))))
    return kwargs


def _fallback_to_cpu_model() -> WhisperModel:
    global _compute_type, _cpu_threads, _device, model

    _device, _compute_type, _cpu_threads = "cpu", "int8", _default_cpu_threads()
    try:
        loaded_model = WhisperModel(
            MODEL_SIZE,
            **_whisper_model_kwargs("cpu", "int8", _cpu_threads),
        )
    except Exception as load_exc:
        raise RuntimeError(_model_error_message(load_exc)) from load_exc
    model = loaded_model
    _set_model_state("ready", "GPU inference failed; VoiceCode fell back to CPU int8.")
    return loaded_model


def _transcribe_audio(audio: np.ndarray | str, language: str | None = None) -> dict[str, Any]:
    global model

    kwargs = _transcribe_kwargs(language)
    with model_lock:
        active_model = model
        if active_model is None:
            raise RuntimeError(_model_unavailable_reason() or "Whisper model is not available.")
        try:
            segments, info = active_model.transcribe(audio, **kwargs)
            segment_list = list(segments)
            text = " ".join(s.text for s in segment_list).strip()
        except RuntimeError as exc:
            if not _is_cuda_runtime_error(exc):
                raise
            logger.warning("GPU inference failed (%s). Reloading model on CPU int8.", exc)
            active_model = _fallback_to_cpu_model()
            segments, info = active_model.transcribe(audio, **kwargs)
            segment_list = list(segments)
            text = " ".join(s.text for s in segment_list).strip()
    language_name = getattr(info, "language", language or "auto")
    probability = getattr(info, "language_probability", None)
    result: dict[str, Any] = {"text": text, "language": language_name}
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
    if probability is not None:
        result["language_probability"] = probability
    return result


def _coerce_audio_samples(value: Any) -> np.ndarray:
    cfg = load_config()
    audio_config = extension_registry.extension_config(cfg, "audio_io")
    if not extension_registry.is_enabled(cfg, "audio_io"):
        raise ValueError("audio_io extension is disabled.")
    return audio_io.coerce_audio_samples(value, audio_config)


def _finalize_transcription_result(result: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    result["text"] = _post_process_text(result["text"], str(cfg.get("text_mode", "plain")))
    if extension_registry.is_enabled(cfg, "zh_normalizer"):
        zh_config = extension_registry.extension_config(cfg, "zh_normalizer")
        result["text"] = zh_normalizer.normalize(
            result["text"], str(result.get("language", "auto")), zh_config
        )
    if extension_registry.is_enabled(cfg, "punctuation"):
        punctuation_config = extension_registry.extension_config(cfg, "punctuation")
        result["text"] = punctuation.restore(
            result["text"], str(result.get("language", "auto")), punctuation_config
        )
    return result


@app.route("/transcribe", methods=["POST"])
def transcribe_upload():
    """Transcribe uploaded audio files or JSON float samples without using the recorder."""
    tmp_path: Path | None = None
    try:
        lang: str | None
        output_format = "json"
        cfg = load_config()
        if request.files:
            if not extension_registry.is_enabled(cfg, "audio_io"):
                return _error("audio_io extension is disabled.", 409)
            uploaded = request.files.get("file")
            if uploaded is None or not uploaded.filename:
                return _error("Missing uploaded audio file field named 'file'.", 400)
            lang = _normalize_language(request.form.get("language"))
            output_format = str(request.form.get("output_format", "json"))
            audio_config = extension_registry.extension_config(cfg, "audio_io")
            tmp_path = audio_io.save_upload_to_temp(uploaded, audio_config)
            result = _transcribe_audio(str(tmp_path), lang)
        else:
            payload = _json_payload()
            lang = _normalize_language(payload.get("language"))
            output_format = str(payload.get("output_format", "json"))
            audio = _coerce_audio_samples(payload.get("audio"))
            result = _transcribe_audio(audio, lang)
        result = _finalize_transcription_result(result, cfg)
        if output_format.lower().strip() in {"", "json"}:
            return jsonify(result)
        if not extension_registry.is_enabled(cfg, "exporters"):
            return _error("exporters extension is disabled.", 409)
        exporter_config = extension_registry.extension_config(cfg, "exporters")
        allowed_formats = set(exporter_config.get("formats", ["json", "txt", "srt", "vtt"]))
        if output_format.lower().strip() not in allowed_formats:
            return _error("Requested output_format is disabled by configuration.", 400)
        body, mimetype = exporters.export_result(result, output_format)
        return Response(body, mimetype=mimetype)
    except ValueError as exc:
        return _error(str(exc), 400)
    except RuntimeError as exc:
        logger.warning("Transcription is unavailable: %s", exc)
        return _error(f"Transcription is unavailable: {exc}", 503)
    except Exception as exc:
        logger.exception("Transcription failed.")
        return _error(f"Transcription failed: {exc}", 500)
    finally:
        if tmp_path is not None:
            try:
                tmp_path.unlink()
            except OSError:
                logger.debug("Failed to delete temporary upload: %s", tmp_path)


@app.route("/extensions")
def extensions():
    return jsonify({"extensions": extension_registry.statuses(load_config())})


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
            "device_options": sorted(VALID_DEVICES),
            "compute_type_options": sorted(VALID_COMPUTE_TYPES),
            "cuda_available": _cuda_device_count() > 0,
            "cpu_threads": _cpu_threads,
        }
    )


@app.route("/hardware")
def hardware():
    cuda_count = _cuda_device_count()
    return jsonify(
        {
            "cpu_threads": _default_cpu_threads(),
            "cuda_available": cuda_count > 0,
            "cuda_device_count": cuda_count,
            "active_device": _device,
            "active_compute_type": _compute_type,
            "supported_devices": sorted(VALID_DEVICES),
            "supported_compute_types": sorted(VALID_COMPUTE_TYPES),
            "runtime_supported_compute_types": {
                "cpu": sorted(_supported_compute_types("cpu")),
                "cuda": sorted(_supported_compute_types("cuda")) if cuda_count > 0 else [],
            },
        }
    )


@app.route("/audio/devices")
def audio_devices():
    try:
        devices = sd.query_devices()
        default_input = None
        try:
            default_input = sd.default.device[0]
        except Exception:
            default_input = None
        result = []
        for index, device in enumerate(devices):
            max_inputs = int(device.get("max_input_channels", 0))
            if max_inputs <= 0:
                continue
            result.append(
                {
                    "index": index,
                    "name": str(device.get("name", f"Device {index}")),
                    "max_input_channels": max_inputs,
                    "default_samplerate": device.get("default_samplerate"),
                    "is_default": index == default_input,
                }
            )
        return jsonify({"devices": result, "default_input": default_input})
    except Exception as exc:
        logger.exception("Failed to enumerate audio input devices.")
        return _error(f"Failed to enumerate audio input devices: {exc}", 503)


@app.route("/history", methods=["GET"])
def get_history():
    cfg = load_config()
    try:
        limit = int(request.args.get("limit", cfg.get("history_limit", 50)))
    except (TypeError, ValueError):
        return _error("limit must be an integer between 1 and 500.", 400)
    limit = max(1, min(limit, 500))
    return jsonify({"entries": _read_history(limit)})


@app.route("/history/clear", methods=["POST"])
def clear_history():
    history_file = _history_file()
    try:
        if history_file.exists():
            history_file.unlink()
        return jsonify({"status": "cleared"})
    except Exception as exc:
        logger.exception("Failed to clear transcript history.")
        return _error(f"Failed to clear transcript history: {exc}", 500)


@app.route("/diagnostics")
def diagnostics():
    with _model_state_lock:
        model_state = dict(_model_state)
    with model_lock:
        model_loaded = model is not None
    return jsonify(
        {
            "app": "VoiceCode",
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
        }
    )


def start_server() -> None:
    from waitress import serve  # type: ignore[import-untyped]

    _configure_file_logging()
    _start_initial_model_load()
    logger.info("Starting HTTP server on 127.0.0.1:%s", PORT)
    serve(app, host="127.0.0.1", port=PORT, threads=4)


@app.route("/stats")
def stats():
    cpu = -1.0
    process_cpu = -1.0
    process_memory_mb = -1.0
    system_memory_total_mb = -1.0
    system_memory_available_mb = -1.0
    system_memory_percent = -1.0
    cpu_info = {
        "name": platform.processor() or platform.machine() or "CPU",
        "logical_cores": os.cpu_count(),
        "physical_cores": None,
    }
    try:
        import psutil

        proc = psutil.Process(os.getpid())
        cpu = round(psutil.cpu_percent(interval=0.2), 1)
        process_cpu = round(proc.cpu_percent(interval=None), 1)
        process_memory_mb = round(proc.memory_info().rss / 1024**2, 1)
        virtual_memory = psutil.virtual_memory()
        system_memory_total_mb = round(virtual_memory.total / 1024**2, 1)
        system_memory_available_mb = round(virtual_memory.available / 1024**2, 1)
        system_memory_percent = round(virtual_memory.percent, 1)
        cpu_info["logical_cores"] = psutil.cpu_count(logical=True)
        cpu_info["physical_cores"] = psutil.cpu_count(logical=False)
        cpu_freq = psutil.cpu_freq()
        if cpu_freq:
            cpu_info["current_mhz"] = round(cpu_freq.current, 1)
            cpu_info["max_mhz"] = round(cpu_freq.max, 1)
    except Exception as exc:
        logger.warning("Failed to collect CPU/RAM stats: %s", exc)

    gpu_info = None
    try:
        if _cuda_device_count() > 0:
            try:
                import pynvml  # type: ignore[import-not-found]
            except Exception:
                pynvml = None
            if pynvml is not None:
                try:
                    pynvml.nvmlInit()
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

    return jsonify(
        {
            "device": _device,
            "compute_type": _compute_type,
            "model": MODEL_SIZE,
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
    )
