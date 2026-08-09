"""Safe discovery and deletion of faster-whisper model cache directories."""

from __future__ import annotations

import shutil
import threading
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any


class ModelCacheService:
    def __init__(
        self,
        cache_dir: Callable[[], Path],
        model_info: Mapping[str, Mapping[str, Any]],
        active_model: Callable[[], str],
        model_loaded: Callable[[], bool],
        operation_in_progress: Callable[[], bool],
    ) -> None:
        self._cache_dir = cache_dir
        self._model_info = model_info
        self._active_model = active_model
        self._model_loaded = model_loaded
        self._operation_in_progress = operation_in_progress
        self._status_cache: dict[str, tuple[float, dict[str, Any]]] = {}
        self._cache_lock = threading.RLock()
        self._cache_ttl_seconds = 10.0

    @staticmethod
    def _is_relative_to(path: Path, parent: Path) -> bool:
        try:
            path.resolve().relative_to(parent.resolve())
        except ValueError:
            return False
        return True

    def _normalize_model(self, model_name: str) -> str:
        normalized = model_name.strip()
        if normalized not in self._model_info:
            raise ValueError(f"Unsupported model: {model_name}")
        return normalized

    @staticmethod
    def _cache_names(model_name: str) -> tuple[str, ...]:
        safe_name = model_name.replace("/", "--")
        return (
            model_name,
            safe_name,
            f"models--Systran--faster-whisper-{safe_name}",
            f"models--guillaumekln--faster-whisper-{safe_name}",
        )

    @staticmethod
    def _path_matches(path: Path, names: tuple[str, ...]) -> bool:
        lowered = path.name.lower()
        return any(lowered == name.lower() or lowered.endswith(name.lower()) for name in names)

    @staticmethod
    def _directory_size(path: Path) -> int:
        total = 0
        if not path.exists():
            return 0
        for item in path.rglob("*"):
            try:
                if item.is_file():
                    total += item.stat().st_size
            except OSError:
                continue
        return total

    def candidates(self, model_name: str) -> list[Path]:
        normalized = self._normalize_model(model_name)
        root = self._cache_dir().resolve()
        if not root.exists():
            return []
        names = self._cache_names(normalized)
        candidates = []
        for path in root.iterdir():
            if self._path_matches(path, names) and self._is_relative_to(path, root):
                candidates.append(path)
        return candidates

    def status(self, model_name: str, *, force: bool = False) -> dict[str, Any]:
        normalized = self._normalize_model(model_name)
        now = time.monotonic()
        with self._cache_lock:
            cached = self._status_cache.get(normalized)
            if not force and cached and now - cached[0] < self._cache_ttl_seconds:
                return dict(cached[1])
        paths = self.candidates(normalized)
        result = {
            "model": normalized,
            "cached": bool(paths),
            "paths": [str(path) for path in paths],
            "size_bytes": sum(self._directory_size(path) for path in paths),
        }
        with self._cache_lock:
            self._status_cache[normalized] = (now, dict(result))
        return result

    def all_statuses(self) -> dict[str, dict[str, Any]]:
        return {name: self.status(name) for name in self._model_info}

    def delete(self, model_name: str, *, confirm: bool = False) -> dict[str, Any]:
        normalized = self._normalize_model(model_name)
        if not confirm:
            raise ValueError("Model cache deletion requires confirm=true.")
        if self._operation_in_progress():
            raise RuntimeError("Cannot delete a model cache while model work is in progress.")
        if normalized == self._active_model() and self._model_loaded():
            raise RuntimeError("Cannot delete the currently loaded model cache.")
        root = self._cache_dir().resolve()
        removed = []
        for path in self.candidates(normalized):
            resolved = path.resolve()
            if not self._is_relative_to(resolved, root):
                raise RuntimeError(f"Refusing to delete model path outside cache root: {resolved}")
            if resolved.is_dir():
                shutil.rmtree(resolved)
            elif resolved.exists():
                resolved.unlink()
            removed.append(str(resolved))
        with self._cache_lock:
            self._status_cache.pop(normalized, None)
        return {"status": "deleted", "model": normalized, "removed": removed}
