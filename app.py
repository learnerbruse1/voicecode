import os
import threading
import json
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


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


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
            except Exception as e:
                ws.send(json.dumps({"type": "error", "message": str(e)}))

        elif isinstance(msg, bytes) and recording:
            audio_buf.extend(msg)


def _transcribe(pcm_bytes: bytes, language=None) -> dict:
    audio = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    with model_lock:
        segments, info = model.transcribe(audio, language=language, beam_size=5, task="transcribe")
        text = " ".join(s.text for s in segments).strip()
    return {"text": text, "language": info.language}


def start_server():
    app.run(host="127.0.0.1", port=PORT, use_reloader=False)
