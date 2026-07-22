# VoiceCode API

VoiceCode exposes a local-only HTTP API on `127.0.0.1` for the bundled desktop UI. The default port is `7788` and can be overridden with the `PORT` environment variable.

The HTTP server must never bind to a public interface. Desktop startup checks the `/health` PID and rejects both repeated VoiceCode launches and unrelated services that occupy the configured port.

All non-empty JSON request bodies must be valid JSON objects. Malformed JSON, `null`, arrays, strings, numbers, and booleans return `400` and must not trigger side effects such as model reloads or recording starts. Empty request bodies are accepted by endpoints that have defaults.

Error responses use this shape:

```json
{"error": "English error message"}
```

## Endpoints

### `GET /`

Returns the desktop web UI (`index.html`).

### `GET /health`

Returns service readiness and the owning process ID. Desktop startup uses this PID to ensure the ready server belongs to the current process.

```json
{"status": "ok", "pid": 12345}
```

### `GET /status`

Returns model and recorder state.

```json
{
  "status": "ok",
  "model": "base",
  "recording": false,
  "model_loaded": true,
  "model_state": {"status": "ready", "error": null}
}
```

`model_state.status` may be `not_loaded`, `loading`, `ready`, `error`, or `skipped`.

### `GET /config`

Returns the persisted configuration merged with defaults. If a config file is syntactically valid JSON but contains invalid supported values, VoiceCode ignores it and falls back to defaults instead of crashing.

### `POST /config`

Updates supported config keys only. Unknown keys return `400`.

Supported keys: `hotkey`, `model`, `language`, `ui_language`, `audio_device`, `text_mode`, `history_enabled`, `history_limit`, `font_size`, `append_mode`, `on_top`.

Validation notes:

- `history_limit` must be a real integer from 1 to 500; booleans are rejected.
- `hotkey.modifiers` may contain only `alt`, `ctrl`, and `shift`; unsupported modifiers are rejected rather than silently dropped.
- `hotkey.key` is trimmed/lowercased and must remain non-empty.
- `audio_device` may be an empty string, `null`, a device index, or a device name; booleans are rejected.

### `POST /reload_model`

Starts an asynchronous Whisper model reload.

Request:

```json
{"model": "base"}
```

Supported models: `tiny`, `base`, `small`, `medium`.

If another reload is already in progress, this endpoint returns `409`.

### `POST /record/start`

Starts microphone recording. Optional request fields:

- `language`: `auto`, `zh`, `en`, or `ja`
- `audio_device`: device index, device name, empty string, or `null`

If recording is already active, the endpoint remains idempotent and returns `started: false`.

### `POST /record/stop`

Stops recording and transcribes the captured audio. Optional request field: `language` (`auto`, `zh`, `en`, or `ja`).

Success response:

```json
{"text": "transcribed text", "language": "en"}
```

When no audio is available, the response contains an empty `text` string.

### `POST /record/cancel`

Cancels active recording/transcription, clears pending recorder audio, and suppresses stale callback output.

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
