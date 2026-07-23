"""Microphone recording utilities."""

from __future__ import annotations

from typing import Any
import importlib
import logging
import threading

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
