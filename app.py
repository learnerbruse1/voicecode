import io
import os
import queue
import threading
import webbrowser
import numpy as np
from flask import Flask, send_from_directory
from flask_sock import Sock
import json

from faster_whisper import WhisperModel

app = Flask(__name__, static_folder="static")
sock = Sock(app)

MODEL_SIZE = os.environ.get("WHISPER_MODEL", "base")
PORT = int(os.environ.get("PORT", 7788))

print(f"Loading Whisper '{MODEL_SIZE}' model (first run downloads ~150MB)...")
model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")
model_lock = threading.Lock()
print("Model ready.")


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/status")
def status():
    return {"status": "ok", "model": MODEL_SIZE}


@sock.route("/ws")
def ws_handler(ws):
    audio_buf = bytearray()
    language = None
    recording = False

    while True:
        msg = ws.receive()
        if msg is None:
            break

        # Control messages (JSON strings)
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
                    if len(audio_buf) > 0:
                        ws.send(json.dumps({"type": "processing"}))
                        result = _transcribe(bytes(audio_buf), language)
                        audio_buf.clear()
                        ws.send(json.dumps({"type": "final", "text": result["text"], "language": result["language"]}))
            except Exception as e:
                ws.send(json.dumps({"type": "error", "message": str(e)}))

        # Binary audio chunks (Int16 PCM @ 16kHz)
        elif isinstance(msg, bytes) and recording:
            audio_buf.extend(msg)


def _transcribe(pcm_bytes: bytes, language=None) -> dict:
    audio = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    with model_lock:
        segments, info = model.transcribe(audio, language=language, beam_size=5, task="transcribe")
        text = " ".join(s.text for s in segments).strip()
    return {"text": text, "language": info.language}


def _open_browser():
    import time; time.sleep(1.5)
    webbrowser.open(f"http://localhost:{PORT}")


if __name__ == "__main__":
    threading.Thread(target=_open_browser, daemon=True).start()
    print(f"VoiceCode → http://localhost:{PORT}  (Ctrl+C to quit)")
    app.run(host="127.0.0.1", port=PORT)
