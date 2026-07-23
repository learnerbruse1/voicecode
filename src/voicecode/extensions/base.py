"""Extension protocol and shared data structures."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class ExtensionStatus:
    id: str
    name: str
    description: str
    enabled: bool
    available: bool
    operational: bool
    state: str
    maturity: str
    restart_required: bool
    status_message: str | None = None
    optional_dependencies: list[str] = field(default_factory=list)
    missing_dependencies: list[str] = field(default_factory=list)


class Extension(Protocol):
    id: str
    name: str
    description: str
    enabled_by_default: bool
    optional_dependencies: list[str]
    maturity: str
    restart_required_after_install: bool

    def default_config(self) -> dict[str, Any]: ...

    def is_available(self) -> bool: ...

    def missing_dependencies(self) -> list[str]: ...

    def operational_status(self, config: Mapping[str, Any]) -> tuple[bool, str | None]: ...

    def status(self, config: Mapping[str, Any]) -> ExtensionStatus: ...


class BaseExtension:
    id = "base"
    name = "Base extension"
    description = "Base extension"
    enabled_by_default = False
    optional_dependencies: list[str] = []
    maturity = "stable"
    restart_required_after_install = False

    def default_config(self) -> dict[str, Any]:
        return {"enabled": self.enabled_by_default}

    def missing_dependencies(self) -> list[str]:
        return []

    def is_available(self) -> bool:
        return not self.missing_dependencies()

    def operational_status(self, config: Mapping[str, Any]) -> tuple[bool, str | None]:
        available = self.is_available()
        return available, None if available else "Required dependencies are missing."

    def status(self, config: Mapping[str, Any]) -> ExtensionStatus:
        enabled = bool(config.get("enabled", self.enabled_by_default))
        missing = self.missing_dependencies()
        available = not missing
        operational, message = self.operational_status(config)
        if not enabled:
            state = "disabled"
        elif missing:
            state = "dependency_missing"
        elif not operational:
            state = "error"
        elif self.maturity != "stable":
            state = "experimental"
        else:
            state = "operational"
        return ExtensionStatus(
            id=self.id,
            name=self.name,
            description=self.description,
            enabled=enabled,
            available=available,
            operational=operational,
            state=state,
            maturity=self.maturity,
            restart_required=self.restart_required_after_install and bool(missing),
            status_message=message,
            optional_dependencies=list(self.optional_dependencies),
            missing_dependencies=missing,
        )
