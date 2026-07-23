"""Public compatibility facade for VoiceCode dependency management.

Implementation is split across catalog, environment, and installer modules so callers keep a
small stable API while packaging/status logic and background pip orchestration evolve separately.
"""

from .dependency_catalog import DEPENDENCIES, dependencies_for_feature, get_dependency_spec
from .dependency_environment import (
    _write_manifest,
    all_dependency_statuses,
    dependencies_for_feature_status,
    dependency_dir,
    dependency_status,
    ensure_dependency_path,
    missing_dependencies,
    project_root,
    uninstall_dependency as _uninstall_dependency,
)
from . import dependency_installer as _installer
from .dependency_installer import (
    cancel_task,
    dependency_operation_in_progress,
    get_task,
    list_tasks,
    shutdown_tasks,
)
from .dependency_types import DependencySpec, DependencyTask

_run_pip_install = _installer._run_pip_install


def start_install(dependency_id: str) -> DependencyTask:
    # Preserve the historical monkeypatch hook while delegating task orchestration.
    _installer._run_pip_install = _run_pip_install
    return _installer.start_install(dependency_id)


def uninstall_dependency(dependency_id: str, *, confirm: bool = False) -> dict[str, object]:
    if dependency_operation_in_progress(dependency_id):
        raise RuntimeError("Dependency operation is already in progress.")
    return _uninstall_dependency(dependency_id, confirm=confirm)


__all__ = [
    "DEPENDENCIES",
    "DependencySpec",
    "DependencyTask",
    "_write_manifest",
    "all_dependency_statuses",
    "cancel_task",
    "dependencies_for_feature",
    "dependencies_for_feature_status",
    "dependency_dir",
    "dependency_status",
    "ensure_dependency_path",
    "get_dependency_spec",
    "get_task",
    "list_tasks",
    "missing_dependencies",
    "project_root",
    "shutdown_tasks",
    "start_install",
    "uninstall_dependency",
]
