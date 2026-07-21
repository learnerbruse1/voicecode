"""Runtime path helpers for packaged VoiceCode builds."""

from __future__ import annotations

import os
from pathlib import Path
import sys


def _is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def _default_packaged_runtime_dir() -> Path | None:
    if not _is_frozen():
        return None
    return Path(sys.executable).resolve().parent / "runtime"


def configure_runtime_paths(runtime_dir: str | os.PathLike[str] | None = None) -> Path | None:
    """Keep model/download caches inside the installed app folder when packaged.

    Development runs keep the normal user cache layout unless VOICECODE_RUNTIME_DIR is set.
    PyInstaller builds default to ``<install-dir>/runtime`` so future Hugging Face / Whisper
    downloads are colocated with the application and easy for non-technical users to manage.
    """
    configured_dir = runtime_dir or os.environ.get("VOICECODE_RUNTIME_DIR")
    resolved_dir = Path(configured_dir).expanduser().resolve() if configured_dir else None
    if resolved_dir is None:
        resolved_dir = _default_packaged_runtime_dir()
    if resolved_dir is None:
        return None

    cache_dir = resolved_dir / "cache"
    hf_home = cache_dir / "huggingface"
    hf_hub_cache = hf_home / "hub"
    transformers_cache = cache_dir / "transformers"
    model_dir = resolved_dir / "models"

    for directory in (
        resolved_dir,
        cache_dir,
        hf_home,
        hf_hub_cache,
        transformers_cache,
        model_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)

    os.environ.setdefault("VOICECODE_RUNTIME_DIR", str(resolved_dir))
    os.environ.setdefault("VOICECODE_MODEL_DIR", str(model_dir))
    os.environ.setdefault("HF_HOME", str(hf_home))
    os.environ.setdefault("HF_HUB_CACHE", str(hf_hub_cache))
    os.environ.setdefault("HUGGINGFACE_HUB_CACHE", str(hf_hub_cache))
    os.environ.setdefault("TRANSFORMERS_CACHE", str(transformers_cache))
    os.environ.setdefault("XDG_CACHE_HOME", str(cache_dir))
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
    return resolved_dir
