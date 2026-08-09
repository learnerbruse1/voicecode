"""Filesystem isolation, status inspection, and uninstall support for dependencies."""

from __future__ import annotations

import importlib
import importlib.util
import json
import logging
import os
import shutil
import sys
import threading
import time
from pathlib import Path
from typing import Any

from .dependency_catalog import DEPENDENCIES, get_dependency_spec
from .dependency_types import DependencySpec

_dependency_cache_lock = threading.Lock()
_dependency_status_cache: list[dict[str, Any]] | None = None

logger = logging.getLogger("voicecode.dependency_environment")
_MANIFEST_DIR_NAME = ".voicecode"


def _normalize_name(value: str) -> str:
    return value.lower().replace("-", "_").replace(".", "_")


def project_root() -> Path:
    configured = os.environ.get("VOICECODE_PROJECT_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    package_root = Path(__file__).resolve().parents[2]
    if (package_root / "pyproject.toml").exists():
        return package_root
    cwd = Path.cwd().resolve()
    return cwd


def dependency_dir() -> Path:
    configured = os.environ.get("VOICECODE_DEP_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    runtime_dir = os.environ.get("VOICECODE_RUNTIME_DIR")
    if runtime_dir:
        return Path(runtime_dir).expanduser().resolve() / "dependencies"
    source_root = project_root()
    if (source_root / "pyproject.toml").is_file():
        return source_root / "VOICE_DEP"
    from .settings import config_dir

    return config_dir() / "dependencies"


def ensure_dependency_path() -> Path:
    target = dependency_dir()
    target_text = str(target)
    if target.exists():
        if target_text in sys.path:
            sys.path.remove(target_text)
        insertion_index = len(sys.path)
        for index, existing in enumerate(sys.path):
            lowered = existing.lower()
            if "site-packages" in lowered or "dist-packages" in lowered:
                insertion_index = index
                break
        # Keep the application, working directory, and standard library ahead of optional
        # packages while still preferring the isolated directory over global site-packages.
        sys.path.insert(insertion_index, target_text)
        importlib.invalidate_caches()
    return target


def manifest_root() -> Path:
    return dependency_dir() / _MANIFEST_DIR_NAME


def _manifest_root() -> Path:
    return manifest_root()


def task_state_path() -> Path:
    return manifest_root() / "tasks.json"


def install_lock_path() -> Path:
    return manifest_root() / "install.lock"


def _manifest_path(spec: DependencySpec) -> Path:
    return _manifest_root() / f"{spec.id}.json"


def _path_is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def top_level_snapshot(root: Path) -> dict[str, tuple[bool, int, int]]:
    if not root.exists():
        return {}
    snapshot: dict[str, tuple[bool, int, int]] = {}
    for entry in root.iterdir():
        if entry.name == _MANIFEST_DIR_NAME:
            continue
        try:
            stat = entry.stat()
        except OSError:
            continue
        snapshot[entry.name] = (entry.is_dir(), stat.st_mtime_ns, stat.st_size)
    return snapshot


def created_entries(
    before: dict[str, tuple[bool, int, int]], after: dict[str, tuple[bool, int, int]]
) -> list[str]:
    return sorted(name for name in after if name not in before)


def changed_entries(
    before: dict[str, tuple[bool, int, int]], after: dict[str, tuple[bool, int, int]]
) -> list[str]:
    return sorted(name for name, metadata in after.items() if before.get(name) != metadata)


def cleanup_new_entries(root: Path, before: dict[str, tuple[bool, int, int]]) -> None:
    if not root.exists():
        return
    for entry in root.iterdir():
        if entry.name == _MANIFEST_DIR_NAME or entry.name in before:
            continue
        try:
            _safe_remove(entry, root)
        except OSError as exc:
            logger.warning("Failed to clean partial dependency path %s: %s", entry, exc)


def _write_manifest(spec: DependencySpec, paths: list[str], source: str) -> None:
    root = _manifest_root()
    root.mkdir(parents=True, exist_ok=True)
    payload = {
        "dependency_id": spec.id,
        "paths": sorted(set(paths)),
        "source": source,
        "pip_spec": spec.pip_spec,
        "installed_at": time.time(),
        "restart_required": spec.restart_required,
    }
    path = _manifest_path(spec)
    temp_path = path.with_suffix(".tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp_path, path)
    invalidate_dependency_cache()


def _read_manifest(spec: DependencySpec) -> dict[str, Any] | None:
    path = _manifest_path(spec)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or payload.get("dependency_id") != spec.id:
        return None
    paths = payload.get("paths")
    if not isinstance(paths, list) or not all(isinstance(item, str) for item in paths):
        return None
    return payload


def _manifest_paths(spec: DependencySpec) -> list[Path]:
    payload = _read_manifest(spec)
    if payload is None:
        return []
    root = dependency_dir().resolve()
    results: list[Path] = []
    for name in payload["paths"]:
        candidate = (root / name).resolve()
        if _path_is_relative_to(candidate, root) and candidate.exists():
            results.append(candidate)
    return results


def _other_manifest_path_names(spec: DependencySpec) -> set[str]:
    names: set[str] = set()
    for other in DEPENDENCIES:
        if other.id == spec.id:
            continue
        payload = _read_manifest(other)
        if payload:
            names.update(str(item) for item in payload["paths"])
    return names


def _find_module_origin(module_name: str) -> tuple[bool, str | None]:
    try:
        found = importlib.util.find_spec(module_name)
    except (ImportError, AttributeError, ValueError):
        return False, None
    if found is None:
        return False, None
    origin = found.origin
    if origin in {None, "built-in", "frozen"} and found.submodule_search_locations:
        origin = next(iter(found.submodule_search_locations), None)
    return True, str(origin) if origin else None


def _is_origin_in_dependency_dir(origin: str | None) -> bool:
    if not origin:
        return False
    try:
        return _path_is_relative_to(Path(origin), dependency_dir())
    except (OSError, RuntimeError):
        return False


def dependency_status(spec: DependencySpec) -> dict[str, object]:
    ensure_dependency_path()
    module_status = []
    missing_modules = []
    installed_in_voice_dep = True
    for module in spec.import_modules:
        available, origin = _find_module_origin(module)
        if not available:
            missing_modules.append(module)
            installed_in_voice_dep = False
        elif not _is_origin_in_dependency_dir(origin):
            installed_in_voice_dep = False
        module_status.append({"module": module, "available": available, "origin": origin})
    installed = not missing_modules
    return {
        "id": spec.id,
        "name": spec.name,
        "description": spec.description,
        "pip_spec": spec.pip_spec,
        "required": spec.required,
        "feature_ids": list(spec.feature_ids),
        "github_preferred": False,
        "trusted_source": "pypi",
        "estimated_install_mb": spec.estimated_install_mb,
        "restart_required": spec.restart_required,
        "notes": spec.notes,
        "installed": installed,
        "installed_in_voice_dep": installed and installed_in_voice_dep,
        "missing_modules": missing_modules,
        "modules": module_status,
    }


def invalidate_dependency_cache() -> None:
    """Drop cached dependency statuses so the next read re-scans the environment."""
    global _dependency_status_cache
    with _dependency_cache_lock:
        _dependency_status_cache = None


def all_dependency_statuses() -> list[dict[str, object]]:
    global _dependency_status_cache
    with _dependency_cache_lock:
        cached = _dependency_status_cache
    if cached is not None:
        return cached
    statuses = [dependency_status(spec) for spec in DEPENDENCIES]
    with _dependency_cache_lock:
        _dependency_status_cache = statuses
    return statuses


def missing_dependencies(*, required_only: bool = False) -> list[dict[str, object]]:
    return [
        status
        for status in all_dependency_statuses()
        if (not required_only or status.get("required")) and not bool(status.get("installed"))
    ]


def dependencies_for_feature_status(feature_id: str) -> list[dict[str, object]]:
    return [dependency_status(spec) for spec in DEPENDENCIES if feature_id in spec.feature_ids]


def _safe_remove(path: Path, root: Path) -> None:
    resolved = path.resolve()
    if not _path_is_relative_to(resolved, root):
        raise RuntimeError(f"Refusing to remove path outside dependency directory: {resolved}")
    if resolved.is_dir():
        shutil.rmtree(resolved)
    elif resolved.exists():
        resolved.unlink()


def _candidate_uninstall_paths(spec: DependencySpec) -> list[Path]:
    root = dependency_dir().resolve()
    if not root.exists():
        return []
    normalized = {_normalize_name(name) for name in spec.distributions}
    module_roots = {module.split(".", 1)[0] for module in spec.import_modules}
    normalized.update(_normalize_name(module) for module in module_roots)
    candidates: list[Path] = []
    for entry in root.iterdir():
        entry_stem = entry.name.rsplit(".", 1)[0]
        entry_normalized = _normalize_name(entry_stem)
        if entry.name in module_roots or entry_normalized in normalized:
            candidates.append(entry)
            continue
        if any(
            entry_normalized.startswith(name + "-") or entry_normalized.startswith(name + "_")
            for name in normalized
        ):
            candidates.append(entry)
    return candidates


def _loaded_module_is_from_root(module: object, root: Path) -> bool:
    module_file = getattr(module, "__file__", None)
    if module_file and _path_is_relative_to(Path(module_file), root):
        return True
    module_paths = getattr(module, "__path__", None)
    if module_paths:
        for module_path in module_paths:
            try:
                if _path_is_relative_to(Path(module_path), root):
                    return True
            except TypeError:
                continue
    return False


def uninstall_dependency(dependency_id: str, *, confirm: bool = False) -> dict[str, object]:
    if not confirm:
        raise ValueError("Dependency uninstall requires confirm=true.")
    spec = get_dependency_spec(dependency_id)
    root = dependency_dir().resolve()
    candidates = _manifest_paths(spec) or _candidate_uninstall_paths(spec)
    protected_names = _other_manifest_path_names(spec)
    removed: list[str] = []
    skipped: list[str] = []
    seen: set[Path] = set()
    for path in candidates:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        if resolved.name in protected_names:
            skipped.append(str(resolved))
            continue
        _safe_remove(resolved, root)
        removed.append(str(resolved))
    manifest_path = _manifest_path(spec)
    try:
        if manifest_path.exists():
            manifest_path.unlink()
    except OSError as exc:
        logger.warning("Failed to remove dependency manifest %s: %s", manifest_path, exc)
    importlib.invalidate_caches()
    for module in spec.import_modules:
        root_name = module.split(".", 1)[0]
        for loaded_name in list(sys.modules):
            if loaded_name == root_name or loaded_name.startswith(root_name + "."):
                loaded_module = sys.modules.get(loaded_name)
                if loaded_module is not None and _loaded_module_is_from_root(loaded_module, root):
                    sys.modules.pop(loaded_name, None)
    invalidate_dependency_cache()
    return {
        "status": "uninstalled",
        "removed": removed,
        "skipped": skipped,
        "dependency": dependency_status(spec),
    }
