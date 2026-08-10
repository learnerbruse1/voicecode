"""Serialized, watchdog-guarded transcription execution.

CTranslate2 models are not safe for concurrent inference, and a hung or
error-poisoned native call must never block the HTTP layer forever.  All
transcriptions run on a single daemon worker; callers bound each job with a
timeout via ``Future.result(timeout=...)``.  When a job exceeds the timeout the
caller marks this executor as *stalled* and discards it (the stuck daemon
thread leaks with its model reference); the next transcription starts on a
freshly reloaded model.

The executor deliberately holds no application locks while running a job, so a
stuck native call cannot block model reloads or other requests.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from concurrent.futures import Future
from queue import Empty, Queue
from typing import Any

logger = logging.getLogger("voicecode.transcription_executor")

_Job = tuple[Callable[[], Any], Future[Any]]


class TranscriptionExecutor:
    """A single-worker executor whose native jobs are bounded by the caller.

    The worker thread is the only caller of the native model, which keeps
    CTranslate2 serialized.  Use ``submit(fn)`` and wait on the returned future
    with a timeout; on timeout call :meth:`mark_stalled` and discard this
    instance so a fresh executor (and model) is used for the next job.
    """

    def __init__(self, *, thread_name: str = "voicecode-transcribe") -> None:
        self._queue: Queue[_Job | None] = Queue()
        self._lock = threading.Lock()
        self._stalled = False
        self._shutdown = False
        self._worker = threading.Thread(target=self._run, daemon=True, name=thread_name)
        self._worker.start()

    @property
    def stalled(self) -> bool:
        with self._lock:
            return self._stalled

    def submit(self, fn: Callable[[], Any]) -> Future[Any]:
        future: Future[Any] = Future()
        with self._lock:
            if self._shutdown or self._stalled:
                future.set_exception(RuntimeError("Transcription executor is unavailable."))
                return future
            self._queue.put((fn, future))
        return future

    def mark_stalled(self) -> None:
        """Mark this executor as stalled; its worker may be stuck in a native call."""
        with self._lock:
            self._stalled = True

    def close(self, *, cancel_pending: bool = True) -> None:
        """Stop accepting jobs.  Pending jobs are cancelled unless requested otherwise.

        A worker stuck in a native call is a daemon thread and will not block
        process exit; it simply stops being referenced.
        """
        with self._lock:
            if self._shutdown:
                return
            self._shutdown = True
            if cancel_pending:
                while True:
                    try:
                        item = self._queue.get_nowait()
                    except Empty:
                        break
                    if item is None:
                        continue
                    _, future = item
                    future.cancel()
            self._queue.put(None)

    def _run(self) -> None:
        while True:
            job = self._queue.get()
            try:
                if job is None:
                    return
                fn, future = job
                if not future.set_running_or_notify_cancel():
                    continue
                try:
                    result = fn()
                except BaseException as exc:  # noqa: BLE001 - delivered to the caller
                    future.set_exception(exc)
                else:
                    future.set_result(result)
            finally:
                self._queue.task_done()
