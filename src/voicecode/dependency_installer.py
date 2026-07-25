"""Cancellable and persistent pip task orchestration for isolated dependencies."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import fields
import importlib
import json
import logging
import os
from queue import Empty, Queue
import shutil
import subprocess
import threading
import time
import uuid
from typing import Iterator

from .dependency_catalog import get_dependency_spec
from .runtime import pip_python_executable
from .dependency_environment import (
    _write_manifest,
    changed_entries,
    cleanup_new_entries,
    dependency_dir,
    dependency_status,
    ensure_dependency_path,
    install_lock_path,
    task_state_path,
    top_level_snapshot,
)
from .dependency_types import DependencySpec, DependencyTask

logger = logging.getLogger("voicecode.dependency_installer")
_tasks: dict[str, DependencyTask] = {}
_active_by_dependency: dict[str, str] = {}
_processes: dict[str, subprocess.Popen[str]] = {}
_task_lock = threading.RLock()
_install_lock = threading.Lock()
_MAX_REMEMBERED_TASKS = 100
_TASK_FIELDS = {item.name for item in fields(DependencyTask)}


def _task_timeout_seconds() -> int:
    raw = os.environ.get("VOICECODE_DEP_INSTALL_TIMEOUT_SECONDS", "1800")
    try:
        return max(60, min(int(raw), 14400))
    except ValueError:
        return 1800


def _task_public_sort_key(task: DependencyTask) -> tuple[float, str]:
    return (task.finished_at or task.started_at, task.id)


def _prune_finished_tasks_locked() -> None:
    if len(_tasks) <= _MAX_REMEMBERED_TASKS:
        return
    active_ids = set(_active_by_dependency.values())
    finished = [
        task
        for task in _tasks.values()
        if task.id not in active_ids and task.status in {"completed", "failed", "cancelled"}
    ]
    count = max(0, len(_tasks) - _MAX_REMEMBERED_TASKS)
    for task in sorted(finished, key=_task_public_sort_key)[:count]:
        _tasks.pop(task.id, None)


def _save_tasks_locked() -> None:
    path = task_state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [task.public_dict() for task in sorted(_tasks.values(), key=_task_public_sort_key)]
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _load_tasks() -> None:
    path = task_state_path()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if not isinstance(payload, list):
        return
    now = time.time()
    with _task_lock:
        for raw in payload[-_MAX_REMEMBERED_TASKS:]:
            if not isinstance(raw, dict):
                continue
            values = {key: value for key, value in raw.items() if key in _TASK_FIELDS}
            try:
                task = DependencyTask(**values)
            except (TypeError, ValueError):
                continue
            if task.status in {"queued", "running", "cancelling"}:
                task.status = "failed"
                task.error = "Installation was interrupted by an application restart."
                task.message = task.error
                task.finished_at = now
                task.process_id = None
            _tasks[task.id] = task
        _prune_finished_tasks_locked()


def _persist_tasks() -> None:
    with _task_lock:
        try:
            _save_tasks_locked()
        except OSError as exc:
            logger.warning("Failed to persist dependency tasks: %s", exc)


def _remember_task(task: DependencyTask) -> None:
    with _task_lock:
        _tasks[task.id] = task
        _prune_finished_tasks_locked()
        _save_tasks_locked()


def _append_task_log(task: DependencyTask, line: str) -> None:
    cleaned = line.rstrip()
    if not cleaned:
        return
    with _task_lock:
        task.log.append(cleaned)
        if len(task.log) > 400:
            del task.log[:-400]
        task.message = cleaned[-240:]
    _persist_tasks()


def _check_disk_space(spec: DependencySpec) -> None:
    target = dependency_dir()
    target.mkdir(parents=True, exist_ok=True)
    free_mb = shutil.disk_usage(target).free / 1024**2
    required_mb = max(100, round(spec.estimated_install_mb * 1.2))
    if free_mb < required_mb:
        raise RuntimeError(
            f"Not enough free disk space for {spec.name}: "
            f"approximately {required_mb}MB required, {free_mb:.0f}MB available."
        )


@contextmanager
def _cross_process_install_lock(timeout_seconds: int) -> Iterator[None]:
    path = install_lock_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        try:
            age = time.time() - path.stat().st_mtime
        except OSError:
            age = 0
        if age > timeout_seconds + 300:
            try:
                path.unlink()
            except OSError:
                pass
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        else:
            raise RuntimeError(
                "Another VoiceCode process is already modifying the dependency directory."
            ) from exc
    try:
        os.write(descriptor, f"pid={os.getpid()} started={time.time()}\n".encode("utf-8"))
        os.close(descriptor)
        yield
    finally:
        try:
            path.unlink()
        except OSError:
            pass


def _terminate_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    try:
        psutil = importlib.import_module("psutil")
        parent = psutil.Process(process.pid)
        children = parent.children(recursive=True)
        for child in children:
            child.terminate()
        parent.terminate()
        _, alive = psutil.wait_procs([*children, parent], timeout=5)
        for item in alive:
            item.kill()
        return
    except Exception:
        pass
    try:
        process.terminate()
        process.wait(timeout=5)
    except Exception:
        try:
            process.kill()
        except Exception:
            pass


def _run_pip_install(
    task: DependencyTask, spec: DependencySpec, candidate: str, attempt: int
) -> bool:
    target = dependency_dir()
    target.mkdir(parents=True, exist_ok=True)
    report_path = target / ".voicecode" / f"pip-report-{task.id}-{attempt}.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        str(pip_python_executable()),
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
        "--no-input",
        "--upgrade",
        "--report",
        str(report_path),
        "--target",
        str(target),
        candidate,
    ]
    with _task_lock:
        task.status = "running"
        task.progress = max(task.progress, 5 + attempt * 8)
        task.message = f"Installing {spec.name} from the configured package index..."
        task.source = candidate
        _save_tasks_locked()
    _append_task_log(task, f"Running pip for catalog dependency {spec.id}.")
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
    with _task_lock:
        task.process_id = process.pid
        _processes[task.id] = process
        _save_tasks_locked()
    stdout = process.stdout
    assert stdout is not None
    output_queue: Queue[str | None] = Queue()

    def read_output() -> None:
        try:
            for output_line in stdout:
                output_queue.put(output_line)
        finally:
            output_queue.put(None)

    threading.Thread(target=read_output, daemon=True).start()
    started = time.monotonic()
    line_count = 0
    reader_finished = False
    try:
        while process.poll() is None or not reader_finished:
            if task.cancel_requested:
                _append_task_log(task, "Cancellation requested; terminating pip.")
                _terminate_process(process)
                break
            if time.monotonic() - started > task.timeout_seconds:
                _append_task_log(task, "Dependency installation timed out; terminating pip.")
                _terminate_process(process)
                raise TimeoutError(
                    f"Dependency installation exceeded {task.timeout_seconds} seconds."
                )
            try:
                line = output_queue.get(timeout=0.2)
            except Empty:
                continue
            if line is None:
                reader_finished = True
                continue
            line_count += 1
            _append_task_log(task, line)
            with _task_lock:
                task.progress = min(88, max(task.progress, 12 + attempt * 8 + line_count // 2))
        return_code = process.wait(timeout=10)
    finally:
        with _task_lock:
            _processes.pop(task.id, None)
            task.process_id = None
            _save_tasks_locked()
        try:
            report_path.unlink()
        except OSError:
            pass
    if task.cancel_requested:
        return False
    if return_code == 0:
        _append_task_log(task, "pip install completed successfully.")
        return True
    _append_task_log(task, f"pip install exited with code {return_code}.")
    return False


def _install_candidates(spec: DependencySpec) -> list[str]:
    return [spec.pip_spec]


def _run_install_task(task_id: str, spec: DependencySpec) -> None:
    task = _tasks[task_id]
    try:
        _check_disk_space(spec)
        with _install_lock, _cross_process_install_lock(task.timeout_seconds):
            target = dependency_dir()
            before_install = top_level_snapshot(target)
            success = False
            used_candidate = spec.pip_spec
            for attempt, candidate in enumerate(_install_candidates(spec)):
                before_attempt = top_level_snapshot(target)
                if attempt:
                    _append_task_log(task, "Trying the explicitly enabled fallback source.")
                if _run_pip_install(task, spec, candidate, attempt):
                    success = True
                    used_candidate = candidate
                    break
                cleanup_new_entries(target, before_attempt)
                if task.cancel_requested:
                    break
            if task.cancel_requested:
                with _task_lock:
                    task.status = "cancelled"
                    task.cancelled = True
                    task.message = "Installation cancelled."
                    task.finished_at = time.time()
                return
            if not success:
                raise RuntimeError(
                    "Dependency installation failed. See task log for pip output and try again."
                )
            with _task_lock:
                task.progress = max(task.progress, 92)
                task.message = "Verifying installed modules..."
                _save_tasks_locked()
            ensure_dependency_path()
            importlib.invalidate_caches()
            status = dependency_status(spec)
            missing_modules = status["missing_modules"]
            if isinstance(missing_modules, list) and missing_modules:
                raise RuntimeError(
                    "Installed files were written, but imports still fail: "
                    + ", ".join(str(item) for item in missing_modules)
                )
            installed_paths = changed_entries(before_install, top_level_snapshot(target))
            if installed_paths:
                _write_manifest(spec, installed_paths, used_candidate)
            with _task_lock:
                task.status = "completed"
                task.progress = 100
                task.message = "Installed successfully."
                task.finished_at = time.time()
                task.restart_required = spec.restart_required
    except TimeoutError as exc:
        logger.warning("Dependency install task timed out: %s", spec.id)
        with _task_lock:
            task.status = "failed"
            task.error = str(exc)
            task.message = str(exc)
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
            try:
                _save_tasks_locked()
            except OSError as exc:
                logger.warning("Failed to persist completed dependency task: %s", exc)


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
            restart_required=False,
        )
        _remember_task(task)
        return task
    with _task_lock:
        active_id = _active_by_dependency.get(spec.id)
        if active_id and active_id in _tasks:
            return _tasks[active_id]
        task = DependencyTask(
            id=uuid.uuid4().hex[:12],
            dependency_id=spec.id,
            action="install",
            timeout_seconds=_task_timeout_seconds(),
        )
        _tasks[task.id] = task
        _active_by_dependency[spec.id] = task.id
        _prune_finished_tasks_locked()
        _save_tasks_locked()
    threading.Thread(target=_run_install_task, args=(task.id, spec), daemon=True).start()
    return task


def get_task(task_id: str) -> DependencyTask:
    with _task_lock:
        try:
            return _tasks[task_id]
        except KeyError as exc:
            raise ValueError(f"Unknown dependency task: {task_id}") from exc


def list_tasks() -> list[DependencyTask]:
    with _task_lock:
        return sorted(_tasks.values(), key=_task_public_sort_key, reverse=True)


def cancel_task(task_id: str) -> DependencyTask:
    task = get_task(task_id)
    with _task_lock:
        if task.status in {"completed", "failed", "cancelled"}:
            return task
        task.cancel_requested = True
        task.status = "cancelling"
        task.message = "Cancellation requested."
        process = _processes.get(task.id)
        _save_tasks_locked()
    if process is not None:
        _terminate_process(process)
    return task


def dependency_operation_in_progress(dependency_id: str) -> bool:
    with _task_lock:
        return dependency_id in _active_by_dependency


def shutdown_tasks() -> None:
    with _task_lock:
        task_ids = list(_processes)
    for task_id in task_ids:
        try:
            cancel_task(task_id)
        except ValueError:
            pass


_load_tasks()
