"""Transcript history query, export, and mutation routes."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from flask import Blueprint, Response, jsonify, request

from . import history as history_store


@dataclass(frozen=True)
class HistoryContext:
    history_file: Callable[[], Path]
    json_payload: Callable[..., dict[str, Any]]
    error: Callable[[str, int], Any]


def _query_params() -> tuple[int | None, str, str, str]:
    raw_limit = request.args.get("limit", "50")
    try:
        limit = int(raw_limit)
    except (TypeError, ValueError):
        limit = None
    if limit is not None:
        limit = max(1, min(limit, 500))
    return (
        limit,
        str(request.args.get("q", "") or "")[:200],
        str(request.args.get("language", "") or "")[:20],
        str(request.args.get("model", "") or "")[:80],
    )


def _filtered_entries(
    history_file: Path, limit: int, query: str, language: str, model_name: str
) -> list[dict[str, Any]]:
    return history_store.read_history(
        history_file, limit, query=query, language=language, model=model_name
    )


def _export_text(entries: list[dict[str, Any]], export_format: str) -> tuple[str, str, str]:
    if export_format == "json":
        return (
            json.dumps({"entries": entries}, ensure_ascii=False, indent=2),
            "application/json; charset=utf-8",
            "voicecode-history.json",
        )
    if export_format == "txt":
        blocks = [
            "\n".join(
                [
                    f"[{entry.get('created_at', '')}] {entry.get('language', 'auto')} / {entry.get('model', '')}",
                    str(entry.get("text", "")),
                ]
            )
            for entry in entries
        ]
        return "\n\n".join(blocks), "text/plain; charset=utf-8", "voicecode-history.txt"
    if export_format == "md":
        lines = ["# VoiceCode History", ""]
        for entry in entries:
            lines.extend(
                [
                    f"## {entry.get('created_at', '')}",
                    "",
                    f"- Language: {entry.get('language', 'auto')}",
                    f"- Model: {entry.get('model', '')}",
                    "",
                    str(entry.get("text", "")),
                    "",
                ]
            )
        return "\n".join(lines), "text/markdown; charset=utf-8", "voicecode-history.md"
    raise ValueError("Unsupported history export format. Use one of: json, txt, md.")


def create_history_blueprint(context: HistoryContext) -> Blueprint:
    blueprint = Blueprint("history_api", __name__)

    @blueprint.get("/history")
    def get_history():
        limit, query, language, model_name = _query_params()
        if limit is None:
            return context.error("limit must be an integer between 1 and 500.", 400)
        entries = _filtered_entries(context.history_file(), limit, query, language, model_name)
        return jsonify(
            {
                "entries": entries,
                "total": len(entries),
                "filters": {"q": query, "language": language, "model": model_name},
            }
        )

    @blueprint.get("/history/export")
    def export_history():
        limit, query, language, model_name = _query_params()
        if limit is None:
            return context.error("limit must be an integer between 1 and 500.", 400)
        export_format = str(request.args.get("format", "json") or "json").lower()
        try:
            content, mimetype, filename = _export_text(
                _filtered_entries(context.history_file(), limit, query, language, model_name),
                export_format,
            )
        except ValueError as exc:
            return context.error(str(exc), 400)
        response = Response(content, mimetype=mimetype)
        response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    @blueprint.route("/history/<entry_id>", methods=["DELETE", "POST"])
    def delete_history_entry(entry_id: str):
        try:
            payload = context.json_payload()
            if payload.get("confirm") is not True:
                raise ValueError("History entry deletion requires confirm=true.")
            if not history_store.delete_history_entry(context.history_file(), entry_id):
                return context.error(f"Unknown history entry: {entry_id}", 404)
            return jsonify({"status": "deleted", "id": entry_id})
        except ValueError as exc:
            return context.error(str(exc), 400)
        except Exception as exc:
            return context.error(f"Failed to delete transcript history entry: {exc}", 500)

    @blueprint.post("/history/clear")
    def clear_history():
        try:
            context.json_payload()
            history_store.clear_history(context.history_file())
            return jsonify({"status": "cleared"})
        except ValueError as exc:
            return context.error(str(exc), 400)
        except Exception as exc:
            return context.error(f"Failed to clear transcript history: {exc}", 500)

    return blueprint
