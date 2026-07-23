"""Isolated dependency management for VoiceCode optional/runtime add-ons."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import importlib
import importlib.util
import json
import logging
import os
from pathlib import Path
import shutil
import site
import subprocess
import sys
import threading
import time
import uuid

logger = logging.getLogger("voicecode.dependencies")


@dataclass(frozen=True)
class DependencySpec:
    id: str
    name: str
    description: str
    pip_spec: str
    import_modules: tuple[str, ...]
    distributions: tuple[str, ...]
    feature_ids: tuple[str, ...] = ()
    github_specs: tuple[str, ...] = ()
    required: bool = False
    notes: str = ""


@dataclass
class DependencyTask:
    id: str
    dependency_id: str
    action: str
    status: str = "queued"
    progress: int = 0
    message: str = "Queued."
    started_at: float = field(default_factory=time.time)
    finished_at: float | None = None
    error: str | None = None
    log: list[str] = field(default_factory=list)

    def public_dict(self) -> dict[str, object]:
        result = asdict(self)
        result["log"] = self.log[-80:]
        return result


DEPENDENCIES: tuple[DependencySpec, ...] = (
    DependencySpec(
        id="whisper-runtime",
        name="Whisper runtime",
        description="Core transcription engine powered by faster-whisper and CTranslate2.",
        pip_spec="faster-whisper>=1.1.1,<2",
        import_modules=("faster_whisper", "ctranslate2"),
        distributions=("faster-whisper", "ctranslate2"),
        github_specs=("git+https://github.com/SYSTRAN/faster-whisper.git",),
        required=True,
        notes="Required for transcription. Installing faster-whisper also installs its runtime dependencies.",
    ),
    DependencySpec(
        id="audio-capture",
        name="Audio capture",
        description="Microphone recording support via python-sounddevice.",
        pip_spec="sounddevice>=0.5,<1",
        import_modules=("sounddevice",),
        distributions=("sounddevice",),
        github_specs=("git+https://github.com/spatialaudio/python-sounddevice.git",),
        required=True,
        notes="Required for push-to-talk microphone recording.",
    ),
    DependencySpec(
        id="opencc-python-reimplemented",
        name="Chinese script conversion",
        description="Simplified/traditional Chinese conversion for the Chinese normalizer extension.",
        pip_spec="opencc-python-reimplemented>=0.1.7,<1",
        import_modules=("opencc",),
        distributions=("opencc-python-reimplemented",),
        feature_ids=("zh_normalizer",),
        github_specs=("git+https://github.com/yichen0831/opencc-python.git",),
    ),
    DependencySpec(
        id="jiwer",
        name="Quality metrics",
        description="WER/CER transcript quality metrics.",
        pip_spec="jiwer>=3,<5",
        import_modules=("jiwer",),
        distributions=("jiwer",),
        feature_ids=("quality",),
        github_specs=("git+https://github.com/jitsi/jiwer.git",),
    ),
    DependencySpec(
        id="silero-vad",
        name="Silero VAD",
        description="Optional Silero voice activity detection package for future VAD adapters.",
        pip_spec="silero-vad",
        import_modules=("silero_vad",),
        distributions=("silero-vad",),
        feature_ids=("vad",),
        github_specs=("git+https://github.com/snakers4/silero-vad.git",),
        notes="The built-in faster-whisper VAD works without this package.",
    ),
    DependencySpec(
        id="pyannote-audio",
        name="Speaker diarization",
        description="Optional pyannote.audio dependency for speaker diarization adapters.",
        pip_spec="pyannote.audio>=3,<5",
        import_modules=("pyannote.audio",),
        distributions=("pyannote.audio",),
        feature_ids=("diarization",),
        github_specs=("git+https://github.com/pyannote/pyannote-audio.git",),
        notes="This is a large dependency and may require additional model credentials later.",
    ),
    DependencySpec(
        id="nemo-toolkit",
        name="NeMo punctuation",
        description="Optional NVIDIA NeMo toolkit dependency for punctuation adapters.",
        pip_spec="nemo-toolkit[nlp]>=1,<3",
        import_modules=("nemo",),
        distributions=("nemo-toolkit",),
        feature_ids=("punctuation",),
        github_specs=("nemo-toolkit[nlp] @ git+https://github.com/NVIDIA/NeMo.git",),
        notes="This is a large dependency. PyPI fallback is used if the GitHub install is unavailable.",
    ),
)

_DEPENDENCY_BY_ID = {dependency.id: dependency for dependency in DEPENDENCIES}
_tasks: dict[str, DependencyTask] = {}
_active_by_dependency: dict[str, str] = {}
_task_lock = threading.RLock()
_install_lock = threading.Lock()
_MANIFEST_DIR_NAME = ".voicecode"
_MAX_REMEMBERED_TASKS = 100


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
    if (cwd / "pyproject.toml").exists():
        return cwd
    return cwd


def dependency_dir() -> Path:
    configured = os.environ.get("VOICECODE_DEP_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    return project_root() / "VOICE_DEP"


def ensure_dependency_path() -> Path:
    target = dependency_dir()
    target_text = str(target)
    if target.exists():
        # Process .pth files written by pip --target while still keeping VOICE_DEP
        # ahead of the global environment for deterministic optional dependency resolution.
        try:
            site.addsitedir(target_text)
        except Exception as exc:
            logger.debug("Failed to process dependency directory .pth files: %s", exc)
        if target_text in sys.path:
            sys.path.remove(target_text)
        sys.path.insert(0, target_text)
        importlib.invalidate_caches()
    return target


def _manifest_root() -> Path:
    return dependency_dir() / _MANIFEST_DIR_NAME


def _manifest_path(spec: DependencySpec) -> Path:
    return _manifest_root() / f"{spec.id}.json"


def _task_public_sort_key(task: DependencyTask) -> tuple[float, str]:
    return (task.finished_at or task.started_at, task.id)


def _prune_finished_tasks_locked() -> None:
    if len(_tasks) <= _MAX_REMEMBERED_TASKS:
        return
    active_ids = set(_active_by_dependency.values())
    finished = [
        task
        for task in _tasks.values()
        if task.id not in active_ids and task.status in {"completed", "failed"}
    ]
    for task in sorted(finished, key=_task_public_sort_key)[
        : max(0, len(_tasks) - _MAX_REMEMBERED_TASKS)
    ]:
        _tasks.pop(task.id, None)


def _remember_task(task: DependencyTask) -> None:
    with _task_lock:
        _tasks[task.id] = task
        _prune_finished_tasks_locked()


def _path_is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def _top_level_snapshot(root: Path) -> dict[str, tuple[bool, int, int]]:
    if not root.exists():
        return {}
    snapshot: dict[str, tuple[bool, int, int]] = {}
    for entry in root.iterdir():
        if entry.name == _MANIFEST_DIR_NAME:
            continue
        try:
            stat = entry.stat()
        except OSError:
            logger.debug("Skipping disappearing dependency entry during snapshot: %s", entry)
            continue
        snapshot[entry.name] = (entry.is_dir(), stat.st_mtime_ns, stat.st_size)
    return snapshot


def _created_entries(
    before: dict[str, tuple[bool, int, int]], after: dict[str, tuple[bool, int, int]]
) -> list[str]:
    return sorted(name for name in after if name not in before)


def _cleanup_new_entries(root: Path, before: dict[str, tuple[bool, int, int]]) -> None:
    after = _top_level_snapshot(root)
    for name in _created_entries(before, after):
        try:
            _safe_remove(root / name, root)
        except Exception as exc:
            logger.warning("Failed to clean partial dependency entry %s: %s", name, exc)


def _write_manifest(spec: DependencySpec, paths: list[str], source: str) -> None:
    manifest_dir = _manifest_root()
    manifest_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": 1,
        "dependency_id": spec.id,
        "name": spec.name,
        "pip_spec": spec.pip_spec,
        "source": source,
        "installed_at": time.time(),
        "python": sys.version.split()[0],
        "paths": sorted(set(paths)),
    }
    tmp = _manifest_path(spec).with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(_manifest_path(spec))


def _read_manifest(spec: DependencySpec) -> dict[str, object] | None:
    path = _manifest_path(spec)
    try:
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Ignoring unreadable dependency manifest %s: %s", path, exc)
        return None
    if not isinstance(payload, dict) or payload.get("dependency_id") != spec.id:
        logger.warning("Ignoring invalid dependency manifest: %s", path)
        return None
    return payload


def _manifest_paths(spec: DependencySpec) -> list[Path]:
    manifest = _read_manifest(spec)
    if not manifest:
        return []
    raw_paths = manifest.get("paths", [])
    if not isinstance(raw_paths, list):
        return []
    root = dependency_dir().resolve()
    paths: list[Path] = []
    for raw_path in raw_paths:
        if not isinstance(raw_path, str) or not raw_path or raw_path == _MANIFEST_DIR_NAME:
            continue
        candidate = (root / raw_path).resolve()
        if _path_is_relative_to(candidate, root):
            paths.append(candidate)
        else:
            logger.warning("Ignoring manifest path outside dependency directory: %s", raw_path)
    return paths


def _other_manifest_path_names(spec: DependencySpec) -> set[str]:
    names: set[str] = set()
    manifest_dir = _manifest_root()
    if not manifest_dir.exists():
        return names
    for manifest_file in manifest_dir.glob("*.json"):
        if manifest_file == _manifest_path(spec):
            continue
        try:
            payload = json.loads(manifest_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        raw_paths = payload.get("paths", []) if isinstance(payload, dict) else []
        if isinstance(raw_paths, list):
            names.update(path for path in raw_paths if isinstance(path, str))
    return names


def _find_module_origin(module: str) -> str | None:
    ensure_dependency_path()
    try:
        spec = importlib.util.find_spec(module)
    except Exception as exc:
        logger.debug("Failed to inspect module %s: %s", module, exc)
        return None
    if spec is None:
        return None
    origin = spec.origin or ""
    if origin in {"built-in", "frozen"}:
        return origin
    if origin:
        return origin
    locations = getattr(spec, "submodule_search_locations", None)
    if locations:
        try:
            return str(next(iter(locations)))
        except StopIteration:
            return None
    return None


def _is_origin_in_dependency_dir(origin: str | None) -> bool:
    if not origin or origin in {"built-in", "frozen"}:
        return False
    try:
        return _path_is_relative_to(Path(origin), dependency_dir())
    except OSError:
        return False


def dependency_status(spec: DependencySpec) -> dict[str, object]:
    origins = {module: _find_module_origin(module) for module in spec.import_modules}
    missing = [module for module, origin in origins.items() if origin is None]
    installed = not missing
    installed_in_voice_dep = installed and all(
        _is_origin_in_dependency_dir(origin) for origin in origins.values()
    )
    manifest = _read_manifest(spec)
    managed_paths = _manifest_paths(spec)
    return {
        "id": spec.id,
        "name": spec.name,
        "description": spec.description,
        "pip_spec": spec.pip_spec,
        "import_modules": list(spec.import_modules),
        "feature_ids": list(spec.feature_ids),
        "required": spec.required,
        "notes": spec.notes,
        "installed": installed,
        "installed_in_voice_dep": installed_in_voice_dep,
        "managed_by_voice_dep": bool(manifest and managed_paths),
        "missing_modules": missing,
        "origins": origins,
        "install_dir": str(dependency_dir()),
        "github_preferred": bool(spec.github_specs),
    }


def all_dependency_statuses() -> list[dict[str, object]]:
    return [dependency_status(spec) for spec in DEPENDENCIES]


def missing_dependencies(*, required_only: bool = False) -> list[dict[str, object]]:
    results = []
    for spec in DEPENDENCIES:
        if required_only and not spec.required:
            continue
        status = dependency_status(spec)
        if status["missing_modules"]:
            results.append(status)
    return results


def get_dependency_spec(dependency_id: str) -> DependencySpec:
    try:
        return _DEPENDENCY_BY_ID[dependency_id]
    except KeyError as exc:
        raise ValueError(f"Unknown dependency: {dependency_id}") from exc


def _append_task_log(task: DependencyTask, line: str) -> None:
    clean = line.rstrip()
    if not clean:
        return
    with _task_lock:
        task.log.append(clean[-1000:])
        if len(task.log) > 200:
            del task.log[: len(task.log) - 200]
        task.message = clean[-240:]


def _run_pip_install(
    task: DependencyTask, spec: DependencySpec, candidate: str, attempt: int
) -> bool:
    target = dependency_dir()
    target.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
        "--no-warn-script-location",
        "--no-cache-dir",
        "--no-input",
        "--upgrade",
        "--target",
        str(target),
        candidate,
    ]
    with _task_lock:
        task.status = "running"
        task.progress = max(task.progress, 8)
        task.message = (
            f"Installing from {'GitHub' if candidate in spec.github_specs else 'PyPI'}..."
        )
        task.log.append("Running: " + " ".join(command))
    logger.info("Installing dependency %s into %s", spec.id, target)
    try:
        env = {**os.environ, "PYTHONNOUSERSITE": "1", "PIP_NO_INPUT": "1"}
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
        )
    except Exception as exc:
        _append_task_log(task, f"Failed to start pip: {exc}")
        with _task_lock:
            task.progress = max(task.progress, 12)
        return False

    line_count = 0
    assert process.stdout is not None
    for line in process.stdout:
        line_count += 1
        _append_task_log(task, line)
        with _task_lock:
            task.progress = min(88, max(task.progress, 12 + attempt * 8 + line_count // 2))
    return_code = process.wait()
    if return_code == 0:
        _append_task_log(task, "pip install completed successfully.")
        return True
    _append_task_log(task, f"pip install exited with code {return_code}.")
    return False


def _run_install_task(task_id: str, spec: DependencySpec) -> None:
    task = _tasks[task_id]
    try:
        with _install_lock:
            target = dependency_dir()
            before_install = _top_level_snapshot(target)
            candidates = [*spec.github_specs, spec.pip_spec]
            seen: set[str] = set()
            unique_candidates = []
            for candidate in candidates:
                if candidate not in seen:
                    seen.add(candidate)
                    unique_candidates.append(candidate)
            success = False
            used_candidate = spec.pip_spec
            for attempt, candidate in enumerate(unique_candidates):
                before_attempt = _top_level_snapshot(target)
                if attempt > 0:
                    _append_task_log(task, f"Trying fallback source: {candidate}")
                if _run_pip_install(task, spec, candidate, attempt):
                    success = True
                    used_candidate = candidate
                    break
                _cleanup_new_entries(target, before_attempt)
            if not success:
                raise RuntimeError(
                    "Dependency installation failed. See task log for pip output and try again."
                )
            with _task_lock:
                task.progress = max(task.progress, 92)
                task.message = "Verifying installed modules..."
            ensure_dependency_path()
            importlib.invalidate_caches()
            status = dependency_status(spec)
            missing_modules = status["missing_modules"]
            if isinstance(missing_modules, list) and missing_modules:
                missing = ", ".join(str(m) for m in missing_modules)
                raise RuntimeError(
                    f"Installed files were written, but imports still fail: {missing}"
                )
            after_install = _top_level_snapshot(target)
            created_paths = _created_entries(before_install, after_install)
            if created_paths:
                _write_manifest(spec, created_paths, used_candidate)
            with _task_lock:
                task.status = "completed"
                task.progress = 100
                task.message = "Installed successfully."
                task.finished_at = time.time()
    except Exception as exc:
        logger.exception("Dependency install task failed: %s", spec.id)
        with _task_lock:
            task.status = "failed"
            task.error = str(exc)
            task.message = str(exc)
            task.finished_at = time.time()
            task.progress = max(task.progress, 1)
    finally:
        with _task_lock:
            _active_by_dependency.pop(spec.id, None)
            _prune_finished_tasks_locked()


def start_install(dependency_id: str) -> DependencyTask:
    spec = get_dependency_spec(dependency_id)
    status = dependency_status(spec)
    if status["installed_in_voice_dep"]:
        task = DependencyTask(
            id=uuid.uuid4().hex[:12],
            dependency_id=spec.id,
            action="install",
            status="completed",
            progress=100,
            message="Already installed in VOICE_DEP.",
            finished_at=time.time(),
        )
        _remember_task(task)
        return task
    with _task_lock:
        active_id = _active_by_dependency.get(spec.id)
        if active_id and active_id in _tasks:
            return _tasks[active_id]
        task = DependencyTask(id=uuid.uuid4().hex[:12], dependency_id=spec.id, action="install")
        _tasks[task.id] = task
        _active_by_dependency[spec.id] = task.id
        _prune_finished_tasks_locked()
    thread = threading.Thread(target=_run_install_task, args=(task.id, spec), daemon=True)
    thread.start()
    return task


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
        entry_name = entry.name
        entry_stem = entry_name.rsplit(".", 1)[0]
        entry_normalized = _normalize_name(entry_stem)
        if entry_name in module_roots or entry_normalized in normalized:
            candidates.append(entry)
            continue
        for name in normalized:
            if entry_normalized.startswith(name + "-") or entry_normalized.startswith(name + "_"):
                candidates.append(entry)
                break
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
    with _task_lock:
        if spec.id in _active_by_dependency:
            raise RuntimeError("Dependency operation is already in progress.")
    root = dependency_dir().resolve()
    manifest_paths = _manifest_paths(spec)
    candidates = manifest_paths or _candidate_uninstall_paths(spec)
    protected_names = _other_manifest_path_names(spec)
    removed: list[str] = []
    skipped: list[str] = []
    seen: set[Path] = set()
    for path in candidates:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        relative_name = resolved.name
        if relative_name in protected_names:
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
    return {
        "status": "uninstalled",
        "removed": removed,
        "skipped": skipped,
        "dependency": dependency_status(spec),
    }


def get_task(task_id: str) -> DependencyTask:
    with _task_lock:
        try:
            return _tasks[task_id]
        except KeyError as exc:
            raise ValueError(f"Unknown dependency task: {task_id}") from exc
