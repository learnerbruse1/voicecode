# VoiceCode API

VoiceCode exposes a local-only HTTP API on `127.0.0.1` for the bundled desktop UI. The default port is `7788` and can be overridden with the `PORT` environment variable.

All JSON request bodies must be objects. Error responses use this shape:

```json
{"error": "English error message"}
```

## Endpoints

### `GET /`

Returns the desktop web UI (`index.html`).

### `GET /health`

Returns service readiness.

```json
{"status": "ok"}
```

### `GET /status`

Returns model and recorder state.

```json
{
  "status": "ok",
  "model": "base",
  "recording": false,
  "model_state": {"status": "ready", "error": null}
}
```

### `GET /config`

Returns the persisted configuration merged with defaults.

### `POST /config`

Updates supported config keys only. Unknown keys return `400`.

Supported keys: `hotkey`, `model`, `language`, `ui_language`, `audio_device`, `text_mode`, `history_enabled`, `history_limit`, `font_size`, `append_mode`, `on_top`.

### `POST /reload_model`

Starts an asynchronous Whisper model reload.

Request:

```json
{"model": "base"}
```

Supported models: `tiny`, `base`, `small`, `medium`.

### `POST /record/start`

Starts microphone recording. Optional request field: `language` (`auto`, `zh`, `en`, or `ja`).

### `POST /record/stop`

Stops recording and transcribes the captured audio. Optional request field: `language` (`auto`, `zh`, `en`, or `ja`).

Success response:

```json
{"text": "transcribed text", "language": "en"}
```

### `POST /record/cancel`

Cancels active recording/transcription and suppresses stale callback output.

### `POST /log`

Accepts frontend diagnostic messages and writes them through Python logging.

### `GET /stats`

Returns best-effort local CPU/RAM/GPU telemetry. Values may be `-1` or `null` when telemetry is unavailable.

### `GET /models`

Returns supported model metadata, current model, inference device, and model load state.

### `GET /audio/devices`

Returns available input devices and the default input device index.

### `GET /history`

Returns recent transcript history entries. Query parameter: `limit` from 1 to 500.

### `POST /history/clear`

Deletes transcript history.

### `GET /diagnostics`

Returns privacy-safe runtime diagnostics such as Python version, platform, config path, log path, model state, and static directory. It does not include audio or transcript text.
