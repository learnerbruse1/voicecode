"""Shared data structures for optional dependency management."""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class DependencySpec:
    id: str
    name: str
    description: str
    pip_spec: str
    import_modules: tuple[str, ...]
    distributions: tuple[str, ...]
    feature_ids: tuple[str, ...] = ()
    required: bool = False
    notes: str = ""
    estimated_install_mb: int = 256
    restart_required: bool = False


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
    cancel_requested: bool = False
    cancelled: bool = False
    process_id: int | None = None
    timeout_seconds: int = 1800
    source: str | None = None
    restart_required: bool = False

    def public_dict(self) -> dict[str, object]:
        result = asdict(self)
        result["log"] = self.log[-80:]
        return result
