"""Transcript history persistence."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import hashlib
import json
import logging

logger = logging.getLogger("voicecode.history")


def history_entry_id(entry: dict[str, Any]) -> str:
    existing = entry.get("id")
    if isinstance(existing, str) and existing.strip():
        return existing.strip()
    raw = json.dumps(
        {
            "created_at": entry.get("created_at"),
            "language": entry.get("language"),
            "model": entry.get("model"),
            "text": entry.get("text"),
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def normalize_entry(entry: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(entry)
    normalized["id"] = history_entry_id(normalized)
    return normalized


def append_history(history_file: Path, entry: dict[str, Any]) -> None:
    try:
        history_file.parent.mkdir(parents=True, exist_ok=True)
        with history_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(normalize_entry(entry), ensure_ascii=False) + "\n")
    except Exception as exc:
        logger.warning("Failed to append transcript history: %s", exc)


def read_all_history(history_file: Path) -> list[dict[str, Any]]:
    if not history_file.is_file():
        return []
    entries: list[dict[str, Any]] = []
    try:
        with history_file.open("r", encoding="utf-8") as f:
            for line in f:
                try:
                    raw_entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(raw_entry, dict):
                    entries.append(normalize_entry(raw_entry))
    except Exception as exc:
        logger.warning("Failed to read transcript history: %s", exc)
        return []
    return entries


def filter_history(
    entries: list[dict[str, Any]], *, query: str = "", language: str = "", model: str = ""
) -> list[dict[str, Any]]:
    query_text = query.strip().lower()
    language_text = language.strip().lower()
    model_text = model.strip().lower()
    results = []
    for entry in entries:
        entry_text = str(entry.get("text", ""))
        entry_language = str(entry.get("language", "") or "auto")
        entry_model = str(entry.get("model", ""))
        if query_text and query_text not in entry_text.lower():
            continue
        if language_text and language_text != entry_language.lower():
            continue
        if model_text and model_text != entry_model.lower():
            continue
        results.append(entry)
    return results


def read_history(
    history_file: Path,
    limit: int = 50,
    *,
    query: str = "",
    language: str = "",
    model: str = "",
) -> list[dict[str, Any]]:
    entries = filter_history(
        read_all_history(history_file), query=query, language=language, model=model
    )
    return entries[-limit:]


def delete_history_entry(history_file: Path, entry_id: str) -> bool:
    target_id = entry_id.strip()
    if not target_id:
        raise ValueError("history entry id must be non-empty.")
    entries = read_all_history(history_file)
    kept = [entry for entry in entries if history_entry_id(entry) != target_id]
    if len(kept) == len(entries):
        return False
    history_file.parent.mkdir(parents=True, exist_ok=True)
    tmp = history_file.with_name(f"{history_file.name}.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        for entry in kept:
            f.write(json.dumps(normalize_entry(entry), ensure_ascii=False) + "\n")
    tmp.replace(history_file)
    return True


def clear_history(history_file: Path) -> None:
    if history_file.exists():
        history_file.unlink()
