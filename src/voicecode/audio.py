"""Microphone recording utilities."""

from __future__ import annotations

from typing import Any
import logging
import threading

import numpy as np
import sounddevice as sd  # type: ignore[import-untyped]

logger = logging.getLogger("voicecode.audio")


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
