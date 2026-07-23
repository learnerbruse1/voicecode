"""Background pip task orchestration for isolated optional dependencies."""

from __future__ import annotations

import importlib
import logging
import os
import subprocess
import sys
import threading
import time
import uuid

from .dependency_catalog import get_dependency_spec
from .dependency_environment import (
    cleanup_new_entries,
    created_entries,
    dependency_dir,
    dependency_status,
    ensure_dependency_path,
    top_level_snapshot,
    _write_manifest,
)
from .dependency_types import DependencySpec, DependencyTask

logger = logging.getLogger("voicecode.dependency_installer")
_tasks: dict[str, DependencyTask] = {}
_active_by_dependency: dict[str, str] = {}
_task_lock = threading.RLock()
_install_lock = threading.Lock()
_MAX_REMEMBERED_TASKS = 100


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
    count = max(0, len(_tasks) - _MAX_REMEMBERED_TASKS)
    for task in sorted(finished, key=_task_public_sort_key)[:count]:
        _tasks.pop(task.id, None)


def _remember_task(task: DependencyTask) -> None:
    with _task_lock:
        _tasks[task.id] = task
        _prune_finished_tasks_locked()


def _append_task_log(task: DependencyTask, line: str) -> None:
    cleaned = line.rstrip()
    if not cleaned:
        return
    with _task_lock:
        task.log.append(cleaned)
        if len(task.log) > 400:
            del task.log[:-400]
        task.message = cleaned[-240:]


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
        "--no-input",
        "--upgrade",
        "--target",
        str(target),
        candidate,
    ]
    with _task_lock:
        task.status = "running"
        task.progress = max(task.progress, 5 + attempt * 8)
        task.message = f"Installing {spec.name}..."
    _append_task_log(task, f"Running: {' '.join(command)}")
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    assert process.stdout is not None
    line_count = 0
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
            before_install = top_level_snapshot(target)
            candidates = list(dict.fromkeys((*spec.github_specs, spec.pip_spec)))
            success = False
            used_candidate = spec.pip_spec
            for attempt, candidate in enumerate(candidates):
                before_attempt = top_level_snapshot(target)
                if attempt:
                    _append_task_log(task, f"Trying fallback source: {candidate}")
                if _run_pip_install(task, spec, candidate, attempt):
                    success = True
                    used_candidate = candidate
                    break
                cleanup_new_entries(target, before_attempt)
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
                raise RuntimeError(
                    "Installed files were written, but imports still fail: "
                    + ", ".join(str(item) for item in missing_modules)
                )
            created_paths = created_entries(before_install, top_level_snapshot(target))
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
            message="Already installed in the isolated dependency directory.",
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
    threading.Thread(target=_run_install_task, args=(task.id, spec), daemon=True).start()
    return task


def get_task(task_id: str) -> DependencyTask:
    with _task_lock:
        try:
            return _tasks[task_id]
        except KeyError as exc:
            raise ValueError(f"Unknown dependency task: {task_id}") from exc


def dependency_operation_in_progress(dependency_id: str) -> bool:
    with _task_lock:
        return dependency_id in _active_by_dependency
