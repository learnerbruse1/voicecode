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
    optional_dependencies: list[str] = field(default_factory=list)
    missing_dependencies: list[str] = field(default_factory=list)


class Extension(Protocol):
    id: str
    name: str
    description: str
    enabled_by_default: bool
    optional_dependencies: list[str]

    def default_config(self) -> dict[str, Any]: ...

    def is_available(self) -> bool: ...

    def missing_dependencies(self) -> list[str]: ...

    def status(self, config: Mapping[str, Any]) -> ExtensionStatus: ...


class BaseExtension:
    id = "base"
    name = "Base extension"
    description = "Base extension"
    enabled_by_default = False
    optional_dependencies: list[str] = []

    def default_config(self) -> dict[str, Any]:
        return {"enabled": self.enabled_by_default}

    def missing_dependencies(self) -> list[str]:
        return []

    def is_available(self) -> bool:
        return not self.missing_dependencies()

    def status(self, config: Mapping[str, Any]) -> ExtensionStatus:
        return ExtensionStatus(
            id=self.id,
            name=self.name,
            description=self.description,
            enabled=bool(config.get("enabled", self.enabled_by_default)),
            available=self.is_available(),
            optional_dependencies=list(self.optional_dependencies),
            missing_dependencies=self.missing_dependencies(),
        )
