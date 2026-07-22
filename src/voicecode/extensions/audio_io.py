"""Audio input extension helpers."""

from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, BinaryIO

import numpy as np

from .base import BaseExtension

ALLOWED_SUFFIXES = {
    ".wav",
    ".mp3",
    ".m4a",
    ".flac",
    ".ogg",
    ".opus",
    ".webm",
    ".aac",
    ".audio",
}


class AudioIOExtension(BaseExtension):
    id = "audio_io"
    name = "Audio input"
    description = "Validates uploaded audio files and JSON sample arrays."
    enabled_by_default = True

    def default_config(self) -> dict[str, Any]:
        return {
            "enabled": True,
            "max_upload_mb": 100,
            "max_json_seconds": 600,
            "sample_rate": 16000,
            "allowed_suffixes": sorted(ALLOWED_SUFFIXES),
        }


def _max_json_samples(config: dict[str, Any]) -> int:
    seconds = int(config.get("max_json_seconds", 600))
    sample_rate = int(config.get("sample_rate", 16000))
    return max(1, seconds * sample_rate)


def coerce_audio_samples(value: Any, config: dict[str, Any]) -> np.ndarray:
    if not isinstance(value, list) or not value:
        raise ValueError("audio must be a non-empty array of float samples.")
    try:
        samples = np.asarray(value, dtype=np.float32)
    except (TypeError, ValueError) as exc:
        raise ValueError("audio must contain numeric samples.") from exc
    if samples.ndim > 2:
        raise ValueError("audio must be a one-dimensional array or a mono/stereo array.")
    if samples.ndim == 2:
        samples = samples.mean(axis=1, dtype=np.float32)
    if samples.size > _max_json_samples(config):
        raise ValueError("audio exceeds the configured maximum JSON sample duration.")
    if not np.all(np.isfinite(samples)):
        raise ValueError("audio samples must be finite numbers.")
    return np.clip(samples, -1.0, 1.0).astype(np.float32, copy=False)


def save_upload_to_temp(uploaded: Any, config: dict[str, Any]) -> Path:
    filename = str(getattr(uploaded, "filename", ""))
    if not filename:
        raise ValueError("Missing uploaded audio file field named 'file'.")
    suffix = Path(filename).suffix.lower() or ".audio"
    allowed = {
        str(item).lower() for item in config.get("allowed_suffixes", sorted(ALLOWED_SUFFIXES))
    }
    if suffix not in allowed:
        raise ValueError("Unsupported audio file extension.")

    max_bytes = int(config.get("max_upload_mb", 100)) * 1024 * 1024
    stream: BinaryIO | None = getattr(uploaded, "stream", None)
    if stream is not None:
        try:
            pos = stream.tell()
            stream.seek(0, 2)
            size = stream.tell()
            stream.seek(pos)
            if size > max_bytes:
                raise ValueError("Uploaded audio file exceeds the configured maximum size.")
        except (AttributeError, OSError):
            pass

    with NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
        tmp_path = Path(tmp_file.name)
        uploaded.save(tmp_file)
    return tmp_path
