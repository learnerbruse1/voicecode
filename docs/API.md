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

Supported keys: `hotkey`, `model`, `language`, `font_size`, `append_mode`, `on_top`.

### `POST /reload_model`

Starts an asynchronous Whisper model reload.

Request:

```json
{"model": "base"}
```

Supported models: `tiny`, `base`, `small`, `medium`.

### `POST /record/start`

Starts microphone recording. Optional request field: `language` (`auto`, `zh`, or `en`).

### `POST /record/stop`

Stops recording and transcribes the captured audio. Optional request field: `language` (`auto`, `zh`, or `en`).

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
