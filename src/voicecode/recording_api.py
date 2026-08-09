"""Recording and direct transcription Flask routes."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from flask import Blueprint, Response, jsonify, request
from werkzeug.exceptions import HTTPException

from .audio import Recorder
from .extensions import audio_io, exporters
from .extensions import registry as extension_registry


@dataclass(frozen=True)
class RecordingContext:
    error: Callable[[str, int], Any]
    json_payload: Callable[..., dict[str, Any]]
    load_config: Callable[[], dict[str, Any]]
    normalize_language: Callable[[Any], str | None]
    normalize_audio_device: Callable[[Any], Any]
    model_unavailable_reason: Callable[[], str | None]
    recorder: Recorder
    transcribe_audio: Callable[[Any, str | None], dict[str, Any]]
    finalize_result: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]
    coerce_audio_samples: Callable[[Any], Any]
    append_history: Callable[[dict[str, Any]], None]
    model_name: Callable[[], str]
    get_cancel_token: Callable[[], int]
    bump_cancel_token: Callable[[], int]
    deliver_transcription: Callable[[str, int], None]
    start_partial_worker: Callable[[int, str | None], None]
    stop_partial_worker: Callable[[], None]


def create_recording_blueprint(context: RecordingContext) -> Blueprint:
    blueprint = Blueprint("recording_api", __name__)

    @blueprint.post("/record/start")
    def record_start():
        try:
            payload = context.json_payload()
            language = context.normalize_language(payload.get("language", "zh"))
            reason = context.model_unavailable_reason()
            if reason:
                return context.error(
                    f"Cannot start recording because Whisper model is unavailable: {reason}", 503
                )
            config = context.load_config()
            device = context.normalize_audio_device(
                payload.get("audio_device", config.get("audio_device", ""))
            )
            started = context.recorder.start(device=device)
            if started and config.get("partial_results", True):
                context.start_partial_worker(int(config.get("partial_interval_ms", 600)), language)
            return jsonify({"status": "recording", "started": started})
        except ValueError as exc:
            return context.error(str(exc), 400)
        except HTTPException:
            raise
        except Exception as exc:
            return context.error(f"Failed to start recording: {exc}", 503)

    @blueprint.post("/record/stop")
    def record_stop():
        request_cancel_token = context.get_cancel_token()
        try:
            payload = context.json_payload()
            language = context.normalize_language(payload.get("language"))
        except ValueError as exc:
            return context.error(str(exc), 400)
        context.stop_partial_worker()
        audio = context.recorder.stop_and_get()
        if len(audio) == 0:
            return jsonify({"text": "", "language": language or "auto"})
        try:
            result = context.transcribe_audio(audio, language)
            config = context.load_config()
            result = context.finalize_result(result, config)
            if config.get("history_enabled", True) and result["text"]:
                context.append_history(
                    {
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "language": result.get("language"),
                        "model": context.model_name(),
                        "text": result["text"],
                    }
                )
        except RuntimeError as exc:
            return context.error(f"Transcription is unavailable: {exc}", 503)
        except Exception as exc:
            return context.error(f"Transcription failed: {exc}", 500)
        if result["text"]:
            context.deliver_transcription(result["text"], request_cancel_token)
        return jsonify(result)

    @blueprint.post("/record/cancel")
    def record_cancel():
        try:
            context.json_payload()
        except ValueError as exc:
            return context.error(str(exc), 400)
        context.stop_partial_worker()
        context.bump_cancel_token()
        context.recorder.stop_and_get()
        return jsonify({"status": "cancelled"})

    @blueprint.post("/transcribe")
    def transcribe_upload():
        temporary_path: Path | None = None
        try:
            output_format = "json"
            config = context.load_config()
            if request.files:
                if not extension_registry.is_enabled(config, "audio_io"):
                    return context.error("audio_io extension is disabled.", 409)
                uploaded = request.files.get("file")
                if uploaded is None or not uploaded.filename:
                    return context.error("Missing uploaded audio file field named 'file'.", 400)
                language = context.normalize_language(request.form.get("language"))
                output_format = str(request.form.get("output_format", "json"))
                audio_config = extension_registry.extension_config(config, "audio_io")
                temporary_path = audio_io.save_upload_to_temp(uploaded, audio_config)
                result = context.transcribe_audio(str(temporary_path), language)
            else:
                payload = context.json_payload()
                language = context.normalize_language(payload.get("language"))
                output_format = str(payload.get("output_format", "json"))
                audio = context.coerce_audio_samples(payload.get("audio"))
                result = context.transcribe_audio(audio, language)
            result = context.finalize_result(result, config)
            if output_format.lower().strip() in {"", "json"}:
                return jsonify(result)
            if not extension_registry.is_enabled(config, "exporters"):
                return context.error("exporters extension is disabled.", 409)
            exporter_config = extension_registry.extension_config(config, "exporters")
            allowed_formats = set(exporter_config.get("formats", ["json", "txt", "srt", "vtt"]))
            if output_format.lower().strip() not in allowed_formats:
                return context.error("Requested output_format is disabled by configuration.", 400)
            body, mimetype = exporters.export_result(result, output_format)
            return Response(body, mimetype=mimetype)
        except ValueError as exc:
            return context.error(str(exc), 400)
        except RuntimeError as exc:
            return context.error(f"Transcription is unavailable: {exc}", 503)
        except HTTPException:
            raise
        except Exception as exc:
            return context.error(f"Transcription failed: {exc}", 500)
        finally:
            if temporary_path is not None:
                with suppress(OSError):
                    temporary_path.unlink(missing_ok=True)

    return blueprint
