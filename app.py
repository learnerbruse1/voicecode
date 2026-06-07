import os
import threading
import json
import atexit
from concurrent.futures import ThreadPoolExecutor

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
import numpy as np
import ctranslate2
from flask import Flask, send_from_directory, jsonify, request
from faster_whisper import WhisperModel

app = Flask(__name__, static_folder="static")

PORT = int(os.environ.get("PORT", 7788))
MODEL_SIZE = os.environ.get("WHISPER_MODEL", "base")

def _best_device():
    if ctranslate2.get_cuda_device_count() > 0:
        return "cuda", "float16", 4
    import multiprocessing
    return "cpu", "int8", max(2, multiprocessing.cpu_count() // 2)

_device, _compute_type, _cpu_threads = _best_device()

print(f"Device: {_device} ({_compute_type})")
print(f"Loading Whisper '{MODEL_SIZE}' model...")
model = WhisperModel(MODEL_SIZE, device=_device, compute_type=_compute_type,
                     cpu_threads=_cpu_threads)
model_lock = threading.Lock()
print("Model ready.")

_executor = ThreadPoolExecutor(max_workers=1)
atexit.register(lambda: _executor.shutdown(wait=False))
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
                    return {**DEFAULT_CONFIG, **json.load(f)}
            except Exception:
                pass
        return dict(DEFAULT_CONFIG)

def save_config(cfg):
    with _config_lock:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

@app.route("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")

@app.route("/status")
def status():
    return jsonify({"status": "ok", "model": MODEL_SIZE})

@app.route("/config", methods=["GET"])
def get_config():
    return jsonify(load_config())

@app.route("/config", methods=["POST"])
def post_config():
    cfg = load_config()
    cfg.update(request.json)
    save_config(cfg)
    return jsonify(cfg)

@app.route("/reload_model", methods=["POST"])
def reload_model():
    size = request.json.get("model", "base")
    def _do():
        # Build model outside lock (slow), then swap atomically
        new = WhisperModel(size, device=_device, compute_type=_compute_type,
                           cpu_threads=_cpu_threads)
        with model_lock:
            global model, MODEL_SIZE
            model = new
            MODEL_SIZE = size
    # Submit via executor so it serialises with in-flight transcriptions
    # and the last submitted wins (cancel any queued reload)
    _executor.submit(_do)
    return jsonify({"status": "loading", "model": size})

# Hook set by main.py — called after each transcription
on_transcription = None

@app.route("/log", methods=["POST"])
def client_log():
    print("[JS]", request.json.get("msg",""), flush=True)
    return "", 204

@app.route("/transcribe", methods=["POST"])
def transcribe():
    lang = request.args.get("language") or None
    pcm = request.data
    print(f"[transcribe] lang={lang} bytes={len(pcm)}", flush=True)
    if not pcm:
        return jsonify({"text": "", "language": lang or "zh"})
    result = _transcribe(pcm, lang)
    print(f"[transcribe] result={result}", flush=True)
    if on_transcription and result["text"]:
        on_transcription(result["text"])
    return jsonify(result)

def _transcribe(pcm_bytes: bytes, language=None) -> dict:
    audio = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    prompt = "以下是普通话的语音识别结果。" if language == "zh" else None
    with model_lock:
        segments, info = model.transcribe(
            audio, language=language, task="transcribe",
            beam_size=1, best_of=1, condition_on_previous_text=False,
            initial_prompt=prompt, vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 500}, temperature=0.0,
        )
        text = " ".join(s.text for s in segments).strip()
    return {"text": text, "language": info.language}

def start_server():
    app.run(host="127.0.0.1", port=PORT, use_reloader=False, threaded=True)
