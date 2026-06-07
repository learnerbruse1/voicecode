import os
import threading
import json
import atexit
from concurrent.futures import ThreadPoolExecutor

# Use HF mirror for users in China, suppress symlink warning
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
import numpy as np
import ctranslate2
from flask import Flask, send_from_directory, jsonify, request
from flask_sock import Sock
from faster_whisper import WhisperModel

app = Flask(__name__, static_folder="static")
sock = Sock(app)

PORT = int(os.environ.get("PORT", 7788))
MODEL_SIZE = os.environ.get("WHISPER_MODEL", "base")

# Auto-select best device and precision
def _best_device_and_precision():
    if ctranslate2.get_cuda_device_count() > 0:
        return "cuda", "float16"
    import multiprocessing
    # Use half the CPU cores, minimum 2
    cpu_threads = max(2, multiprocessing.cpu_count() // 2)
    return "cpu", "int8", cpu_threads

_dev_cfg = _best_device_and_precision()
_device       = _dev_cfg[0]
_compute_type = _dev_cfg[1]
_cpu_threads  = _dev_cfg[2] if len(_dev_cfg) > 2 else 4

print(f"Device: {_device} ({_compute_type})")
print(f"Loading Whisper '{MODEL_SIZE}' model...")
model = WhisperModel(MODEL_SIZE, device=_device, compute_type=_compute_type,
                     cpu_threads=_cpu_threads)
model_lock = threading.Lock()
print("Model ready.")

# Executor: serialises transcription jobs off the WS thread
_executor = ThreadPoolExecutor(max_workers=1)
atexit.register(lambda: _executor.shutdown(wait=False))

# Config file lock: prevents concurrent read/write corruption
_config_lock = threading.Lock()

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")
DEFAULT_CONFIG = {
    "hotkey": {"modifiers": ["alt"], "key": "z"},
    "model": "base",
    "language": "zh",
    "font_size": "1rem",
    "append_mode": "append",
    "on_top": False,
}

def load_config():
    with _config_lock:
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, encoding="utf-8") as f:
                    data = json.load(f)
                return {**DEFAULT_CONFIG, **data}
            except Exception:
                pass
        return dict(DEFAULT_CONFIG)

def save_config(cfg):
    with _config_lock:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)


@app.route("/config", methods=["GET"])
def get_config():
    return jsonify(load_config())


@app.route("/config", methods=["POST"])
def post_config():
    cfg = load_config()
    cfg.update(request.json)
    save_config(cfg)
    return jsonify(cfg)

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

@app.route("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")


@app.route("/status")
def status():
    return jsonify({"status": "ok", "model": MODEL_SIZE})


@app.route("/reload_model", methods=["POST"])
def reload_model():
    """Queue model reload through the executor so it serialises with transcriptions."""
    size = request.json.get("model", "base")

    def _do():
        global model, MODEL_SIZE
        new_model = WhisperModel(size, device=_device, compute_type=_compute_type,
                                  cpu_threads=_cpu_threads)
        with model_lock:
            model = new_model
            MODEL_SIZE = size

    _executor.submit(_do)
    return jsonify({"status": "loading", "model": size})


# Hook called after each transcription — set by main.py
on_transcription: callable = None

@sock.route("/ws")
def ws_handler(ws):
    audio_buf = bytearray()
    language = None
    recording = False

    while True:
        try:
            msg = ws.receive(timeout=60)
        except Exception:
            break
        if msg is None:
            break

        if isinstance(msg, str):
            try:
                data = json.loads(msg)
                t = data.get("type")
                if t in ("start", "config"):
                    lang = data.get("language", "auto")
                    language = None if lang == "auto" else lang
                    if t == "start":
                        audio_buf.clear()
                        recording = True
                elif t == "stop":
                    recording = False
                    if audio_buf:
                        ws.send(json.dumps({"type": "processing"}))
                        pcm = bytes(audio_buf)
                        audio_buf.clear()
                        lang_snap = language

                        fut = _executor.submit(_transcribe, pcm, lang_snap)
                        try:
                            result = fut.result(timeout=30)
                        except Exception as e:
                            ws.send(json.dumps({"type": "error", "message": str(e)}))
                            continue
                        ws.send(json.dumps({"type": "final", "text": result["text"], "language": result["language"]}))
                        if on_transcription and result["text"]:
                            on_transcription(result["text"])
            except Exception as e:
                try:
                    ws.send(json.dumps({"type": "error", "message": str(e)}))
                except Exception:
                    pass

        elif isinstance(msg, bytes) and recording:
            if len(audio_buf) < 16_000_000:
                # Only append 2-byte-aligned (int16) data to avoid sample corruption
                avail = len(msg) - (len(msg) % 2)
                if avail > 0:
                    audio_buf.extend(msg[:avail])


def _transcribe(pcm_bytes: bytes, language=None) -> dict:
    audio = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    # Prompt guides Whisper to output Simplified Chinese instead of Traditional
    prompt = "以下是普通话的语音识别结果。" if language == "zh" else None
    with model_lock:
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
    return {"text": text, "language": info.language}


def start_server():
    app.run(host="127.0.0.1", port=PORT, use_reloader=False)
