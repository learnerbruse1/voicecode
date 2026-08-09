"""Microphone recording utilities."""

from __future__ import annotations

import importlib
import logging
import threading
from typing import Any

import numpy as np

logger = logging.getLogger("voicecode.audio")

sd: Any = None
_sounddevice_import_error: BaseException | None = None
try:
    sd = importlib.import_module("sounddevice")
except Exception as exc:  # pragma: no cover - depends on host audio packages
    _sounddevice_import_error = exc


def _sounddevice():  # noqa: ANN202
    global sd, _sounddevice_import_error
    if sd is not None:
        return sd
    try:
        sd = importlib.import_module("sounddevice")
    except Exception as exc:
        _sounddevice_import_error = exc
        raise RuntimeError(
            "Missing dependency 'sounddevice'. Open Dependencies in the left sidebar and "
            "install Audio capture into VOICE_DEP."
        ) from exc
    _sounddevice_import_error = None
    return sd


def test_input_level(device: int | str | None = None, *, duration_ms: int = 1000) -> dict[str, Any]:
    """Record a short microphone sample and return simple level metrics."""
    if duration_ms < 50 or duration_ms > 5000:
        raise ValueError("duration_ms must be an integer between 50 and 5000.")
    runtime = _sounddevice()
    samples: list[np.ndarray] = []
    lock = threading.Lock()
    seen_audio = threading.Event()

    def callback(indata, frames, time_info, status) -> None:  # noqa: ANN001, ARG001
        if status:
            logger.warning("Audio test recorder status: %s", status)
        data = np.asarray(indata, dtype=np.float32)
        if data.ndim == 2:
            data = data[:, 0]
        else:
            data = data.reshape(-1)
        with lock:
            samples.append(data.copy())
        seen_audio.set()

    stream_kwargs: dict[str, Any] = {
        "samplerate": Recorder.RATE,
        "channels": 1,
        "dtype": "float32",
        "blocksize": 1024,
        "callback": callback,
    }
    if device is not None:
        stream_kwargs["device"] = device

    stream: Any | None = None
    try:
        stream = runtime.InputStream(**stream_kwargs)
        stream.start()
        seen_audio.wait(timeout=max(0.1, duration_ms / 1000))
        threading.Event().wait(timeout=duration_ms / 1000)
    finally:
        if stream is not None:
            try:
                stream.stop()
            finally:
                stream.close()

    with lock:
        audio = np.concatenate(samples) if samples else np.array([], dtype=np.float32)
    if audio.size == 0:
        return {
            "duration_ms": duration_ms,
            "sample_rate": Recorder.RATE,
            "samples": 0,
            "rms": 0.0,
            "peak": 0.0,
            "level_percent": 0,
            "has_signal": False,
        }
    rms = float(np.sqrt(np.mean(np.square(audio))))
    peak = float(np.max(np.abs(audio)))
    return {
        "duration_ms": duration_ms,
        "sample_rate": Recorder.RATE,
        "samples": int(audio.size),
        "rms": rms,
        "peak": peak,
        "level_percent": int(max(0, min(100, round(peak * 100)))),
        "has_signal": peak >= 0.01 or rms >= 0.005,
    }


def normalize_audio_device(value: Any) -> int | str | None:
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


def query_input_devices() -> tuple[list[dict[str, Any]], int | None]:
    runtime = _sounddevice()
    devices = runtime.query_devices()
    default_input = None
    try:
        default_input = runtime.default.device[0]
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
    return result, default_input


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
                runtime = _sounddevice()
                stream_kwargs: dict[str, Any] = {
                    "samplerate": self.RATE,
                    "channels": 1,
                    "dtype": "float32",
                    "blocksize": 1024,
                    "callback": self._cb,
                }
                if device is not None:
                    stream_kwargs["device"] = device
                self._stream = runtime.InputStream(**stream_kwargs)
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

    def snapshot(self) -> np.ndarray:
        """Return a copy of the audio buffered so far without stopping recording."""
        with self._lock:
            if not self._buf:
                return np.array([], dtype=np.float32)
            return np.concatenate(self._buf).copy()

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

    def cancel(self) -> bool:
        """Discard buffered audio and close the input stream without transcription."""
        with self._lock:
            was_active = self._active or self._stream is not None
            self._active = False
            stream = self._stream
            self._stream = None
            self._buf = []
        if stream:
            try:
                stream.stop()
            except Exception:
                logger.debug("Failed to stop audio stream during cancellation.", exc_info=True)
            try:
                stream.close()
            except Exception:
                logger.debug("Failed to close audio stream during cancellation.", exc_info=True)
        if was_active:
            logger.info("Audio recorder cancelled.")
        return was_active
