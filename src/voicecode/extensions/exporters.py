"""Transcript export helpers."""

from __future__ import annotations

import json
from typing import Any

from .base import BaseExtension

SUPPORTED_FORMATS = {"json", "txt", "srt", "vtt"}


class ExportersExtension(BaseExtension):
    id = "exporters"
    name = "Exporters"
    description = "Exports transcripts as JSON, plain text, SRT, or VTT."
    enabled_by_default = True

    def default_config(self) -> dict[str, Any]:
        return {"enabled": True, "formats": sorted(SUPPORTED_FORMATS)}


def _timestamp(seconds: float, *, separator: str) -> str:
    milliseconds = round(max(0.0, seconds) * 1000)
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02}{separator}{millis:03}"


def _segments(result: dict[str, Any]) -> list[dict[str, Any]]:
    segments = result.get("segments")
    if isinstance(segments, list) and segments:
        return [s for s in segments if isinstance(s, dict)]
    text = str(result.get("text", ""))
    if not text:
        return []
    return [{"start": 0.0, "end": 0.001, "text": text}]


def to_txt(result: dict[str, Any]) -> str:
    return str(result.get("text", ""))


def to_json(result: dict[str, Any]) -> str:
    return json.dumps(result, ensure_ascii=False, indent=2)


def to_srt(result: dict[str, Any]) -> str:
    blocks = []
    for index, segment in enumerate(_segments(result), start=1):
        start = _timestamp(float(segment.get("start", 0.0)), separator=",")
        end = _timestamp(float(segment.get("end", 0.001)), separator=",")
        text = str(segment.get("text", "")).strip()
        blocks.append(f"{index}\n{start} --> {end}\n{text}")
    return "\n\n".join(blocks) + ("\n" if blocks else "")


def to_vtt(result: dict[str, Any]) -> str:
    blocks = ["WEBVTT", ""]
    for segment in _segments(result):
        start = _timestamp(float(segment.get("start", 0.0)), separator=".")
        end = _timestamp(float(segment.get("end", 0.001)), separator=".")
        text = str(segment.get("text", "")).strip()
        blocks.append(f"{start} --> {end}\n{text}")
    return "\n\n".join(blocks) + "\n"


def export_result(result: dict[str, Any], output_format: str) -> tuple[str, str]:
    normalized = output_format.lower().strip() or "json"
    if normalized not in SUPPORTED_FORMATS:
        raise ValueError("Unsupported output_format. Use one of: json, txt, srt, vtt.")
    if normalized == "json":
        return to_json(result), "application/json; charset=utf-8"
    if normalized == "txt":
        return to_txt(result), "text/plain; charset=utf-8"
    if normalized == "srt":
        return to_srt(result), "application/x-subrip; charset=utf-8"
    return to_vtt(result), "text/vtt; charset=utf-8"
