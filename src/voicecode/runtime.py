"""Runtime path helpers for packaged VoiceCode builds."""

from __future__ import annotations

import logging
import os
import shutil
import sys
from pathlib import Path

logger = logging.getLogger("voicecode.runtime")


def _is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def _default_packaged_runtime_dir() -> Path | None:
    if not _is_frozen():
        return None
    return Path(sys.executable).resolve().parent / "runtime"


def pip_python_executable() -> Path:
    """Return the Python executable used for isolated dependency installs.

    Frozen Windows builds ship a compact CPython + pip runtime under
    ``<install-dir>/runtime/python``.  Running ``sys.executable -m pip`` from a
    PyInstaller executable is invalid, so prefer that bundled interpreter.
    """
    runtime_dir = _default_packaged_runtime_dir()
    if runtime_dir is not None:
        candidate = runtime_dir / "python" / ("python.exe" if os.name == "nt" else "python")
        if candidate.is_file():
            return candidate
        raise RuntimeError(
            "The bundled dependency installer is missing. Reinstall VoiceCode to restore "
            "runtime/python."
        )
    return Path(sys.executable).resolve()


def migrate_legacy_model_cache(
    model_name: str, legacy_roots: tuple[Path, ...] | None = None
) -> Path | None:
    """Copy an existing faster-whisper cache into the packaged runtime once.

    Previous source/wheel versions used the default Hugging Face cache in the user profile.
    Installed builds keep models beside the application, so reuse a complete legacy cache
    instead of forcing another network download.
    """
    if not _is_frozen():
        return None
    configured_target = os.environ.get("VOICECODE_MODEL_DIR")
    runtime_dir = _default_packaged_runtime_dir()
    if configured_target:
        target_root = Path(configured_target).expanduser().resolve()
    elif runtime_dir is not None:
        target_root = runtime_dir / "models"
    else:
        return None
    target_root.mkdir(parents=True, exist_ok=True)

    safe_name = model_name.replace("/", "--")
    cache_names = (
        f"models--Systran--faster-whisper-{safe_name}",
        f"models--guillaumekln--faster-whisper-{safe_name}",
        f"models--mobiuslabsgmbh--faster-whisper-{safe_name}",
    )
    if any((target_root / name).exists() for name in cache_names):
        return None

    roots = legacy_roots
    if roots is None:
        roots = (
            Path.home() / ".cache" / "huggingface" / "hub",
            Path(os.environ.get("LOCALAPPDATA", Path.home())) / "huggingface" / "hub",
        )
    for root in roots:
        resolved_root = root.expanduser().resolve()
        if resolved_root == target_root or not resolved_root.is_dir():
            continue
        for name in cache_names:
            source = resolved_root / name
            if not source.is_dir():
                continue
            destination = target_root / name
            temporary = target_root / f".{name}.migrating-{os.getpid()}"
            try:
                if temporary.exists():
                    shutil.rmtree(temporary)
                shutil.copytree(source, temporary, symlinks=False)
                temporary.replace(destination)
                logger.info("Migrated legacy model cache: %s -> %s", source, destination)
                return destination
            except OSError as exc:
                logger.warning("Failed to migrate legacy model cache from %s: %s", source, exc)
                if temporary.exists():
                    shutil.rmtree(temporary, ignore_errors=True)
    return None


def configure_runtime_paths(runtime_dir: str | os.PathLike[str] | None = None) -> Path | None:
    """Keep model/download caches inside the installed app folder when packaged.

    Development runs keep the normal user cache layout unless VOICECODE_RUNTIME_DIR is set.
    PyInstaller builds default to ``<install-dir>/runtime`` so future Hugging Face / Whisper
    downloads are colocated with the application and easy for non-technical users to manage.
    """
    # Hugging Face defaults favor responsiveness over slow or unstable links. VoiceCode
    # allows more time per file request, avoids the Xet/CAS path that is frequently blocked
    # by regional networks, and still respects explicit user overrides.
    os.environ.setdefault("HF_HUB_ETAG_TIMEOUT", "10")
    os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "30")
    os.environ.setdefault("HF_HUB_DISABLE_XET", "1")

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
    pip_cache = cache_dir / "pip"
    model_dir = resolved_dir / "models"
    dependency_dir = resolved_dir / "dependencies"

    for directory in (
        resolved_dir,
        cache_dir,
        hf_home,
        hf_hub_cache,
        transformers_cache,
        pip_cache,
        model_dir,
        dependency_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)

    os.environ.setdefault("VOICECODE_RUNTIME_DIR", str(resolved_dir))
    os.environ.setdefault("VOICECODE_MODEL_DIR", str(model_dir))
    os.environ.setdefault("VOICECODE_DEP_DIR", str(dependency_dir))
    os.environ.setdefault("HF_HOME", str(hf_home))
    os.environ.setdefault("HF_HUB_CACHE", str(hf_hub_cache))
    os.environ.setdefault("HUGGINGFACE_HUB_CACHE", str(hf_hub_cache))
    os.environ.setdefault("TRANSFORMERS_CACHE", str(transformers_cache))
    os.environ.setdefault("PIP_CACHE_DIR", str(pip_cache))
    os.environ.setdefault("XDG_CACHE_HOME", str(cache_dir))
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
    return resolved_dir
