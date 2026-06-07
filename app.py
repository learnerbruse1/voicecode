import os
import threading
import json

# Use HF mirror for users in China, suppress symlink warning
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
import numpy as np
from flask import Flask, send_from_directory, jsonify, request
from flask_sock import Sock
from faster_whisper import WhisperModel

app = Flask(__name__, static_folder="static")
sock = Sock(app)

PORT = int(os.environ.get("PORT", 7788))
MODEL_SIZE = os.environ.get("WHISPER_MODEL", "base")

print(f"Loading Whisper '{MODEL_SIZE}' model...")
model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")
model_lock = threading.Lock()
print("Model ready.")


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
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, encoding="utf-8") as f:
                data = json.load(f)
            # fill missing keys with defaults
            return {**DEFAULT_CONFIG, **data}
        except Exception:
            pass
    return dict(DEFAULT_CONFIG)

def save_config(cfg):
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
    global model, MODEL_SIZE
    size = request.json.get("model", "base")
    MODEL_SIZE = size
    with model_lock:
        model = WhisperModel(size, device="cpu", compute_type="int8")
    return jsonify({"status": "ok", "model": MODEL_SIZE})


# Hook called after each transcription — set by main.py
on_transcription: callable = None

@sock.route("/ws")
def ws_handler(ws):
    audio_buf = bytearray()
    language = None
    recording = False

    while True:
        msg = ws.receive()
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
                        result = _transcribe(bytes(audio_buf), language)
                        audio_buf.clear()
                        ws.send(json.dumps({"type": "final", "text": result["text"], "language": result["language"]}))
                        if on_transcription and result["text"]:
                            on_transcription(result["text"])
            except Exception as e:
                ws.send(json.dumps({"type": "error", "message": str(e)}))

        elif isinstance(msg, bytes) and recording:
            audio_buf.extend(msg)


def _transcribe(pcm_bytes: bytes, language=None) -> dict:
    audio = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    with model_lock:
        segments, info = model.transcribe(
            audio,
            language=language,
            task="transcribe",
            beam_size=1,                    # 3x faster, negligible accuracy loss for short speech
            best_of=1,
            condition_on_previous_text=False,  # prevents slowdown accumulation
            vad_filter=True,                # skip silence segments
            vad_parameters={"min_silence_duration_ms": 300},
            temperature=0.0,               # greedy decode, no sampling overhead
        )
        text = " ".join(s.text for s in segments).strip()
    return {"text": text, "language": info.language}


def start_server():
    app.run(host="127.0.0.1", port=PORT, use_reloader=False)
