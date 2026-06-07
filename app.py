import os
import threading
import json
import atexit
import queue
from concurrent.futures import ThreadPoolExecutor

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
import numpy as np
import ctranslate2
import sounddevice as sd
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
try:
    model = WhisperModel(MODEL_SIZE, device=_device, compute_type=_compute_type,
                         cpu_threads=_cpu_threads)
except Exception as e:
    print(f"WARNING: {_device} failed ({e}), falling back to CPU int8")
    _device, _compute_type = "cpu", "int8"
    model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8",
                         cpu_threads=_cpu_threads)
model_lock = threading.Lock()
print(f"Model ready. ({_device}/{_compute_type})")

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
    return jsonify({"status": "ok", "model": MODEL_SIZE,
                    "recording": _recorder.is_recording()})

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
        new = WhisperModel(size, device=_device, compute_type=_compute_type,
                           cpu_threads=_cpu_threads)
        with model_lock:
            global model, MODEL_SIZE
            model = new
            MODEL_SIZE = size
    _executor.submit(_do)
    return jsonify({"status": "loading", "model": size})

@app.route("/log", methods=["POST"])
def client_log():
    print("[JS]", (request.json or {}).get("msg", ""), flush=True)
    return "", 204

# ---- Recorder ----
class Recorder:
    RATE = 16000

    def __init__(self):
        self._buf = []
        self._lock = threading.Lock()
        self._active = False
        self._stream = None

    def is_recording(self):
        return self._active

    def start(self):
        if self._active:
            return
        with self._lock:
            self._buf = []
            self._active = True
        self._stream = sd.InputStream(
            samplerate=self.RATE, channels=1, dtype="float32",
            blocksize=1024, callback=self._cb)
        self._stream.start()
        print("[recorder] started", flush=True)

    def _cb(self, indata, frames, time_info, status):
        if status:
            print("[recorder] status:", status, flush=True)
        with self._lock:
            if self._active:
                self._buf.append(indata[:, 0].copy())

    def stop_and_get(self):
        if not self._active:
            return np.array([], dtype=np.float32)
        self._active = False
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        with self._lock:
            if not self._buf:
                return np.array([], dtype=np.float32)
            audio = np.concatenate(self._buf)
            self._buf = []
        print(f"[recorder] stopped, {len(audio)} samples ({len(audio)/self.RATE:.1f}s)", flush=True)
        return audio

_recorder = Recorder()

# Hook set by main.py
on_transcription = None

@app.route("/record/start", methods=["POST"])
def record_start():
    lang = (request.json or {}).get("language", "zh")
    _recorder.start()
    return jsonify({"status": "recording"})

@app.route("/record/stop", methods=["POST"])
def record_stop():
    audio = _recorder.stop_and_get()
    if len(audio) == 0:
        print("[record/stop] empty audio", flush=True)
        return jsonify({"text": "", "language": "zh"})
    cfg = request.json or {}
    lang = cfg.get("language") or None
    result = _transcribe_audio(audio, lang)
    print(f"[record/stop] result={result}", flush=True)
    if on_transcription and result["text"]:
        on_transcription(result["text"])
    return jsonify(result)

@app.route("/record/cancel", methods=["POST"])
def record_cancel():
    _recorder.stop_and_get()  # discard audio
    return jsonify({"status": "cancelled"})

def _transcribe_audio(audio: np.ndarray, language=None) -> dict:
    global model, _device, _compute_type
    prompt = "以下是普通话的语音识别结果。" if language == "zh" else None
    with model_lock:
        try:
            segments, info = model.transcribe(
                audio, language=language, task="transcribe",
                beam_size=1, best_of=1, condition_on_previous_text=False,
                initial_prompt=prompt, vad_filter=True,
                vad_parameters={"min_silence_duration_ms": 500}, temperature=0.0,
            )
            text = " ".join(s.text for s in segments).strip()
        except RuntimeError as e:
            if "cublas" in str(e).lower() or "cuda" in str(e).lower():
                # CUDA runtime missing — reload model on CPU and retry
                print(f"WARNING: GPU error ({e}), reloading on CPU", flush=True)
                _device, _compute_type = "cpu", "int8"
                model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8",
                                     cpu_threads=_cpu_threads)
                segments, info = model.transcribe(
                    audio, language=language, task="transcribe",
                    beam_size=1, best_of=1, condition_on_previous_text=False,
                    initial_prompt=prompt, vad_filter=True,
                    vad_parameters={"min_silence_duration_ms": 500}, temperature=0.0,
                )
                text = " ".join(s.text for s in segments).strip()
            else:
                raise
    return {"text": text, "language": info.language}

def start_server():
    from waitress import serve
    serve(app, host="127.0.0.1", port=PORT, threads=4)
