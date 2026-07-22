"""Transcript history persistence."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import json
import logging

logger = logging.getLogger("voicecode.history")


def append_history(history_file: Path, entry: dict[str, Any]) -> None:
    try:
        history_file.parent.mkdir(parents=True, exist_ok=True)
        with history_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as exc:
        logger.warning("Failed to append transcript history: %s", exc)


def read_history(history_file: Path, limit: int = 50) -> list[dict[str, Any]]:
    if not history_file.is_file():
        return []
    entries: list[dict[str, Any]] = []
    try:
        with history_file.open("r", encoding="utf-8") as f:
            for line in f:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except Exception as exc:
        logger.warning("Failed to read transcript history: %s", exc)
        return []
    return entries[-limit:]


def clear_history(history_file: Path) -> None:
    if history_file.exists():
        history_file.unlink()
