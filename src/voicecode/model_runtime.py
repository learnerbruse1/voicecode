"""Thread-safe model runtime state and background execution ownership."""

from __future__ import annotations

import threading
from collections.abc import Callable
from concurrent.futures import Future
from queue import Empty, Queue
from typing import Any

ACTIVE_MODEL_STATES = {"checking", "downloading", "loading"}
_Task = tuple[Future[Any], Callable[..., Any], tuple[Any, ...], dict[str, Any]]


class DaemonSerialExecutor:
    """A single-worker executor whose active task never keeps VoiceCode alive.

    ``ThreadPoolExecutor`` workers are non-daemon threads. A model download that is
    blocked in native/network code can therefore keep a windowless process running
    after the user closes the app. This small executor preserves the Future API and
    serial execution, while the daemon worker lets Windows reclaim the process and
    all of its resources immediately after the desktop GUI exits.
    """

    def __init__(self, *, thread_name: str) -> None:
        self._queue: Queue[_Task | None] = Queue()
        self._lock = threading.Lock()
        self._shutdown = False
        self._worker = threading.Thread(
            target=self._run,
            daemon=True,
            name=thread_name,
        )
        self._worker.start()

    def submit(self, function: Callable[..., Any], *args: Any, **kwargs: Any) -> Future[Any]:
        future: Future[Any] = Future()
        with self._lock:
            if self._shutdown:
                raise RuntimeError("Model executor is shutting down.")
            self._queue.put((future, function, args, kwargs))
        return future

    def _run(self) -> None:
        while True:
            task = self._queue.get()
            try:
                if task is None:
                    return
                future, function, args, kwargs = task
                if not future.set_running_or_notify_cancel():
                    continue
                try:
                    result = function(*args, **kwargs)
                except BaseException as exc:
                    future.set_exception(exc)
                else:
                    future.set_result(result)
            finally:
                self._queue.task_done()

    def shutdown(self, *, wait: bool = False, cancel_futures: bool = True) -> None:
        with self._lock:
            if self._shutdown:
                return
            self._shutdown = True
            if cancel_futures:
                while True:
                    try:
                        pending = self._queue.get_nowait()
                    except Empty:
                        break
                    try:
                        if pending is not None:
                            pending[0].cancel()
                    finally:
                        self._queue.task_done()
            self._queue.put(None)
        if wait and threading.current_thread() is not self._worker:
            self._worker.join()

    @property
    def shutting_down(self) -> bool:
        with self._lock:
            return self._shutdown


class ModelRuntime:
    def __init__(
        self,
        *,
        model_name: str,
        device: str,
        compute_type: str,
        cpu_threads: int,
    ) -> None:
        self.model_lock = threading.RLock()
        self.state_lock = threading.Lock()
        self.executor = DaemonSerialExecutor(thread_name="voicecode-model")
        self.model: Any | None = None
        self.model_name = model_name
        self.device = device
        self.compute_type = compute_type
        self.cpu_threads = cpu_threads
        self.state: dict[str, Any] = {"status": "not_loaded", "error": None, "progress": 0}

    def set_profile(self, device: str, compute_type: str, cpu_threads: int) -> None:
        with self.model_lock:
            self.device = device
            self.compute_type = compute_type
            self.cpu_threads = cpu_threads

    def profile(self) -> tuple[str, str, int]:
        with self.model_lock:
            return self.device, self.compute_type, self.cpu_threads

    def set_model(self, model: Any | None, model_name: str | None = None) -> None:
        with self.model_lock:
            self.model = model
            if model_name is not None:
                self.model_name = model_name

    def get_model(self) -> Any | None:
        with self.model_lock:
            return self.model

    def set_state(self, status: str, error: str | None = None, **details: Any) -> None:
        with self.state_lock:
            self.state["status"] = status
            self.state["error"] = error
            self.state.update(details)
            if status == "ready":
                self.state["progress"] = 100
            elif status == "error":
                self.state.setdefault("progress", 0)

    def begin_operation(
        self,
        *,
        model_name: str,
        cached: bool,
        estimated_bytes: int,
        cache_dir: str,
        started_at: float,
    ) -> bool:
        if self.executor.shutting_down:
            return False
        with self.state_lock:
            if self.state.get("status") in ACTIVE_MODEL_STATES:
                return False
            self.state.clear()
            self.state.update(
                {
                    "status": "loading" if cached else "downloading",
                    "phase": "initializing" if cached else "download",
                    "error": None,
                    "error_code": None,
                    "user_message": None,
                    "technical_details": None,
                    "suggestions": [],
                    "retryable": False,
                    "target_model": model_name,
                    "cached_before": cached,
                    "progress": 0,
                    "downloaded_bytes": 0,
                    "estimated_bytes": estimated_bytes,
                    "download_speed_bps": 0,
                    "elapsed_seconds": 0,
                    "stalled_seconds": 0,
                    "cache_dir": cache_dir,
                    "started_at": started_at,
                }
            )
            return True

    def state_snapshot(self) -> dict[str, Any]:
        with self.state_lock:
            return dict(self.state)

    def operation_in_progress(self) -> bool:
        with self.state_lock:
            return self.state.get("status") in ACTIVE_MODEL_STATES

    def submit(self, function: Callable[..., Any], *args: Any, **kwargs: Any) -> Future[Any]:
        return self.executor.submit(function, *args, **kwargs)

    def shutdown(self) -> None:
        self.executor.shutdown(wait=False, cancel_futures=True)
