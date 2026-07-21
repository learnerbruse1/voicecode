import atexit
from pathlib import Path
import json
import logging
import multiprocessing
import platform
import re
import os
import sys
import threading
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

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

import ctranslate2  # type: ignore[import-untyped]  # noqa: E402
import numpy as np  # noqa: E402
import sounddevice as sd  # type: ignore[import-untyped]  # noqa: E402
from faster_whisper import WhisperModel  # type: ignore[import-untyped]  # noqa: E402
from flask import Flask, jsonify, request, send_from_directory  # noqa: E402

logging.basicConfig(
    level=os.environ.get("VOICECODE_LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("voicecode.app")

app = Flask(__name__, static_folder="static")

PORT = int(os.environ.get("PORT", 7788))
MODEL_SIZE = os.environ.get("WHISPER_MODEL", "base")
VALID_MODELS = {"tiny", "base", "small", "medium"}
VALID_LANGUAGES = {"", "auto", "zh", "en", "ja", None}
VALID_UI_LANGUAGES = {"en", "zh", "ja"}
VALID_TEXT_MODES = {"plain", "coding", "markdown", "prompt"}
MODEL_INFO = {
    "tiny": {"size": "~75 MB", "description": "Fastest, lowest resource usage."},
    "base": {"size": "~150 MB", "description": "Recommended default for most users."},
    "small": {"size": "~500 MB", "description": "More accurate, slower."},
    "medium": {"size": "~1.5 GB", "description": "Most accurate supported option."},
}


def _best_device() -> tuple[str, str, int]:
    if ctranslate2.get_cuda_device_count() > 0:
        return "cuda", "float16", 4
    return "cpu", "int8", max(2, multiprocessing.cpu_count() // 2)


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


def _load_model_sync(size: str | None = None, *, allow_cpu_fallback: bool = True) -> WhisperModel:
    """Load a Whisper model without making application startup depend on success."""
    global MODEL_SIZE, _compute_type, _device, model

    requested_size = size or MODEL_SIZE
    logger.info("Loading Whisper model '%s' on %s (%s)...", requested_size, _device, _compute_type)
    try:
        loaded_model = WhisperModel(
            requested_size,
            device=_device,
            compute_type=_compute_type,
            cpu_threads=_cpu_threads,
        )
    except Exception as exc:
        if not allow_cpu_fallback or _device == "cpu":
            raise RuntimeError(_model_error_message(exc)) from exc
        logger.warning(
            "Failed to initialize %s inference (%s). Falling back to CPU int8.",
            _device,
            exc,
        )
        _device, _compute_type = "cpu", "int8"
        try:
            loaded_model = WhisperModel(
                requested_size,
                device="cpu",
                compute_type="int8",
                cpu_threads=_cpu_threads,
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
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


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


def _default_config_file() -> str:
    if os.name == "nt":
        base_dir = os.environ.get("APPDATA") or os.path.join(Path.home(), "AppData", "Roaming")
        return os.path.join(base_dir, "VoiceCode", "config.json")
    base_dir = os.environ.get("XDG_CONFIG_HOME") or os.path.join(Path.home(), ".config")
    return os.path.join(base_dir, "voicecode", "config.json")


CONFIG_FILE = os.environ.get("VOICECODE_CONFIG_FILE") or _default_config_file()


def _config_dir() -> Path:
    return Path(CONFIG_FILE).expanduser().resolve().parent


def _log_file() -> Path:
    override = os.environ.get("VOICECODE_LOG_FILE")
    if override:
        return Path(override).expanduser().resolve()
    return _config_dir() / "logs" / "voicecode.log"


def _history_file() -> Path:
    override = os.environ.get("VOICECODE_HISTORY_FILE")
    if override:
        return Path(override).expanduser().resolve()
    return _config_dir() / "history.jsonl"


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
        handler = RotatingFileHandler(log_file, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s"))
        root_logger.addHandler(handler)
    except Exception as exc:
        logger.warning("Failed to configure file logging: %s", exc)


DEFAULT_CONFIG: dict[str, Any] = {
    "hotkey": {"modifiers": ["alt"], "key": "z"},
    "model": "base",
    "language": "zh",
    "ui_language": "en",
    "audio_device": "",
    "text_mode": "plain",
    "history_enabled": True,
    "history_limit": 50,
    "font_size": "1rem",
    "append_mode": "append",
    "on_top": False,
}
ALLOWED_CONFIG_KEYS = set(DEFAULT_CONFIG)


def _json_payload() -> dict[str, Any]:
    payload = request.get_json(silent=True)
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise ValueError("JSON payload must be an object.")
    return payload


def _error(message: str, status_code: int):
    logger.warning("Request failed: %s", message)
    return jsonify({"error": message}), status_code


def _normalize_language(language: Any) -> str | None:
    if language in (None, "", "auto"):
        return None
    if language in {"zh", "en", "ja"}:
        return str(language)
    raise ValueError("Unsupported language. Use one of: auto, zh, en, ja.")


def _validate_config_patch(patch: dict[str, Any]) -> dict[str, Any]:
    unknown = set(patch) - ALLOWED_CONFIG_KEYS
    if unknown:
        raise ValueError(f"Unknown config keys: {', '.join(sorted(unknown))}")

    if "model" in patch and patch["model"] not in VALID_MODELS:
        raise ValueError(f"Unsupported model: {patch['model']}")
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
        if not isinstance(limit, int) or not 1 <= limit <= 500:
            raise ValueError("history_limit must be an integer between 1 and 500.")
    if "append_mode" in patch and patch["append_mode"] not in {"append", "replace"}:
        raise ValueError("Unsupported append mode. Use append or replace.")
    if "font_size" in patch and patch["font_size"] not in {"0.85rem", "1rem", "1.2rem", "1.5rem"}:
        raise ValueError("Unsupported font size.")
    if "on_top" in patch and not isinstance(patch["on_top"], bool):
        raise ValueError("on_top must be a boolean.")
    if "hotkey" in patch:
        hotkey = patch["hotkey"]
        if not isinstance(hotkey, dict):
            raise ValueError("hotkey must be an object.")
        modifiers = hotkey.get("modifiers", [])
        key = hotkey.get("key", "")
        if not isinstance(modifiers, list) or not all(isinstance(m, str) for m in modifiers):
            raise ValueError("hotkey.modifiers must be a string array.")
        if not isinstance(key, str) or not key:
            raise ValueError("hotkey.key must be a non-empty string.")
        patch["hotkey"] = {
            "modifiers": [m.lower() for m in modifiers if m.lower() in {"alt", "ctrl", "shift"}],
            "key": key.lower(),
        }
    return patch


def _get_cancel_token() -> int:
    with _cancel_lock:
        return _cancel_token


def _bump_cancel_token() -> int:
    global _cancel_token
    with _cancel_lock:
        _cancel_token += 1
        return _cancel_token


def load_config() -> dict[str, Any]:
    with _config_lock:
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    known_data = {k: v for k, v in data.items() if k in ALLOWED_CONFIG_KEYS}
                    cfg = {**DEFAULT_CONFIG, **known_data}
                    try:
                        return _validate_config_patch(cfg)
                    except ValueError as exc:
                        logger.warning("Ignoring invalid config file '%s': %s", CONFIG_FILE, exc)
                        return dict(DEFAULT_CONFIG)
                logger.warning("Ignoring config file because it does not contain a JSON object.")
            except Exception as exc:
                logger.warning("Failed to read config file '%s': %s", CONFIG_FILE, exc)
        return dict(DEFAULT_CONFIG)


def save_config(cfg: dict[str, Any]) -> None:
    cfg = _validate_config_patch(dict(cfg))
    with _config_lock:
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        tmp = f"{CONFIG_FILE}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        os.replace(tmp, CONFIG_FILE)


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
        cfg = load_config()
        cfg.update(patch)
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
        size = payload.get("model", "base")
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

    future = _executor.submit(_load_model_sync, size)
    future.add_done_callback(lambda f: _model_reload_done(f, size))
    return jsonify({"status": "loading", "model": size})


@app.route("/log", methods=["POST"])
def client_log():
    try:
        payload = _json_payload()
    except ValueError:
        payload = {}
    msg = str(payload.get("msg", ""))
    logger.info("Frontend: %s", msg)
    return "", 204


def _normalize_audio_device(value: Any) -> int | str | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        raise ValueError("audio_device must be an empty string, device index, or device name.")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        if stripped.lstrip("-").isdigit():
            return int(stripped)
        return stripped
    raise ValueError("audio_device must be an empty string, device index, or device name.")


def _post_process_text(text: str, mode: str) -> str:
    processed = " ".join(text.split()) if mode != "plain" else text.strip()
    if mode == "coding":
        replacements = [
            (r"\bnew line\b", "\n"),
            (r"\btab\b", "    "),
            (r"\bopen parenthesis\b", "("),
            (r"\bclose parenthesis\b", ")"),
            (r"\bopen bracket\b", "["),
            (r"\bclose bracket\b", "]"),
            (r"\bopen brace\b", "{"),
            (r"\bclose brace\b", "}"),
            (r"\bequals\b", "="),
            (r"\bcomma\b", ","),
            (r"\bsemicolon\b", ";"),
            (r"\bcolon\b", ":"),
            (r"\bdot\b", "."),
            (r"\barrow\b", "=>"),
        ]
        for pattern, replacement in replacements:
            processed = re.sub(pattern, replacement, processed, flags=re.IGNORECASE)
    elif mode == "markdown":
        processed = re.sub(r"^heading one\s+", "# ", processed, flags=re.IGNORECASE)
        processed = re.sub(r"^heading two\s+", "## ", processed, flags=re.IGNORECASE)
        processed = re.sub(r"^bullet point\s+", "- ", processed, flags=re.IGNORECASE)
    elif mode == "prompt":
        processed = processed.strip()
        if processed and processed[-1] not in ".!????":
            processed += "."
    return processed.strip()


def _append_history(entry: dict[str, Any]) -> None:
    try:
        history_file = _history_file()
        history_file.parent.mkdir(parents=True, exist_ok=True)
        with history_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as exc:
        logger.warning("Failed to append transcript history: %s", exc)


def _read_history(limit: int = 50) -> list[dict[str, Any]]:
    history_file = _history_file()
    if not history_file.is_file():
        return []
    entries: list[dict[str, Any]] = []
    try:
        with history_file.open("r", encoding="utf-8") as f:
            for line in f:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except Exception as exc:
        logger.warning("Failed to read transcript history: %s", exc)
        return []
    return entries[-limit:]


class Recorder:
    RATE = 16000

    def __init__(self) -> None:
        self._buf: list[np.ndarray] = []
        self._lock = threading.RLock()
        self._active = False
        self._stream: Any | None = None

    def is_recording(self) -> bool:
        with self._lock:
            return self._active

    def start(self, device: int | str | None = None) -> bool:
        with self._lock:
            if self._active:
                return False
            self._buf = []
            try:
                stream_kwargs: dict[str, Any] = {
                    "samplerate": self.RATE,
                    "channels": 1,
                    "dtype": "float32",
                    "blocksize": 1024,
                    "callback": self._cb,
                }
                if device is not None:
                    stream_kwargs["device"] = device
                self._stream = sd.InputStream(**stream_kwargs)
                self._active = True
                self._stream.start()
            except Exception:
                logger.exception("Failed to start audio recorder.")
                self._active = False
                if self._stream:
                    try:
                        self._stream.close()
                    except Exception:
                        logger.debug(
                            "Failed to close audio stream after startup error.", exc_info=True
                        )
                self._stream = None
                self._buf = []
                raise
        logger.info("Audio recorder started.")
        return True

    def _cb(self, indata, frames, time_info, status) -> None:  # noqa: ANN001
        if status:
            logger.warning("Audio recorder status: %s", status)
        with self._lock:
            if self._active:
                self._buf.append(indata[:, 0].copy())

    def stop_and_get(self) -> np.ndarray:
        with self._lock:
            if not self._active:
                return np.array([], dtype=np.float32)
            self._active = False
            stream = self._stream
            self._stream = None

        if stream:
            try:
                stream.stop()
            finally:
                stream.close()

        with self._lock:
            if not self._buf:
                return np.array([], dtype=np.float32)
            audio = np.concatenate(self._buf)
            self._buf = []

        logger.info(
            "Audio recorder stopped: %s samples (%.1fs)", len(audio), len(audio) / self.RATE
        )
        return audio


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
        result["text"] = _post_process_text(result["text"], str(cfg.get("text_mode", "plain")))
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


def _transcribe_audio(audio: np.ndarray, language: str | None = None) -> dict[str, str]:
    global _compute_type, _device, model
    prompt = (
        "Please transcribe in Simplified Chinese."
        if language == "zh"
        else "Please transcribe in Japanese."
        if language == "ja"
        else None
    )
    with model_lock:
        active_model = model
        if active_model is None:
            raise RuntimeError(_model_unavailable_reason() or "Whisper model is not available.")
        try:
            segments, info = active_model.transcribe(
                audio,
                language=language,
                task="transcribe",
                beam_size=1,
                best_of=1,
                condition_on_previous_text=False,
                initial_prompt=prompt,
                vad_filter=True,
                vad_parameters={"min_silence_duration_ms": 500},
                temperature=0.0,
            )
            text = " ".join(s.text for s in segments).strip()
        except RuntimeError as exc:
            if "cublas" in str(exc).lower() or "cuda" in str(exc).lower():
                logger.warning("GPU inference failed (%s). Reloading model on CPU int8.", exc)
                _device, _compute_type = "cpu", "int8"
                try:
                    model = WhisperModel(
                        MODEL_SIZE,
                        device="cpu",
                        compute_type="int8",
                        cpu_threads=_cpu_threads,
                    )
                except Exception as load_exc:
                    raise RuntimeError(_model_error_message(load_exc)) from load_exc
                segments, info = model.transcribe(
                    audio,
                    language=language,
                    task="transcribe",
                    beam_size=1,
                    best_of=1,
                    condition_on_previous_text=False,
                    initial_prompt=prompt,
                    vad_filter=True,
                    vad_parameters={"min_silence_duration_ms": 500},
                    temperature=0.0,
                )
                text = " ".join(s.text for s in segments).strip()
            else:
                raise
    return {"text": text, "language": info.language}


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
    limit = int(request.args.get("limit", cfg.get("history_limit", 50)))
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
    try:
        import psutil  # type: ignore[import-untyped]

        proc = psutil.Process(os.getpid())
        cpu = round(psutil.cpu_percent(interval=0.2), 1)
        ram = round(proc.memory_info().rss / 1024**2, 1)
    except Exception as exc:
        logger.warning("Failed to collect CPU/RAM stats: %s", exc)
        cpu = -1
        ram = -1

    gpu_info = None
    try:
        if ctranslate2.get_cuda_device_count() > 0 and _device == "cuda":
            try:
                import pynvml  # type: ignore[import-not-found]
            except Exception:
                pynvml = None
            if pynvml is not None:
                try:
                    pynvml.nvmlInit()
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
                        "name": gpu_name,
                    }
                except Exception as exc:
                    logger.debug("GPU stats unavailable: %s", exc)
                    gpu_info = {"util": -1, "name": "GPU"}
    except Exception as exc:
        logger.debug("CUDA device check failed: %s", exc)

    return jsonify(
        {
            "device": _device,
            "compute_type": _compute_type,
            "model": MODEL_SIZE,
            "cpu_percent": cpu,
            "ram_mb": ram,
            "gpu": gpu_info,
        }
    )
