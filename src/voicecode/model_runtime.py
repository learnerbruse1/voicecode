"""Thread-safe model runtime state and background execution ownership."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
import threading
from typing import Any


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
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="voicecode-model")
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

    def set_state(self, status: str, error: str | None = None) -> None:
        with self.state_lock:
            self.state["status"] = status
            self.state["error"] = error
            if status == "ready":
                self.state["progress"] = 100
            elif status == "error":
                self.state.setdefault("progress", 0)

    def begin_operation(self) -> bool:
        with self.state_lock:
            if self.state.get("status") == "loading":
                return False
            self.state.update(
                {"status": "loading", "error": None, "progress": 0, "downloaded_bytes": 0}
            )
            return True

    def state_snapshot(self) -> dict[str, Any]:
        with self.state_lock:
            return dict(self.state)

    def operation_in_progress(self) -> bool:
        with self.state_lock:
            return self.state.get("status") == "loading"

    def submit(self, function: Any, *args: Any, **kwargs: Any) -> Future[Any]:
        return self.executor.submit(function, *args, **kwargs)

    def shutdown(self) -> None:
        self.executor.shutdown(wait=False, cancel_futures=True)
