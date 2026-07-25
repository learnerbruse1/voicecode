# VoiceCode API

The installed v0.2.0 artifact was revalidated on July 24, 2026 against the health, status, hardware, configuration/schema, onboarding, extensions, dependencies, models, audio devices, history, diagnostics, static-resource, and JSON-sample transcription paths. See [RELEASE_VALIDATION_0.2.0.md](RELEASE_VALIDATION_0.2.0.md). No endpoint contract changed during the final installer pass.

VoiceCode exposes a local-only HTTP API on `127.0.0.1` for the desktop UI and local integrations. The default port is `7788` and can be overridden with `PORT`.

The server must not bind to a public interface. Desktop startup verifies that `/health` returns the current process PID so repeated launches and unrelated services fail clearly.

All non-empty JSON request bodies must be valid JSON objects. Malformed JSON, JSON `null`, arrays, strings, numbers, and booleans return `400` and must not trigger side effects.

Error responses use:

```json
{"error": "English error message", "request_id": "short request id"}
```

Each response also includes `X-VoiceCode-Request-ID`. The server logs request start/completion with method, path, status, duration, and request ID so UI/API failures can be correlated with log lines.

## Local API token

Mutating requests (`POST`, `PUT`, `PATCH`, and `DELETE`) require the per-process local API token in the `X-VoiceCode-Token` header during normal desktop runtime. The token is generated at startup, injected only into the same-origin HTML shell as a non-cacheable meta tag, and automatically attached by `static/js/api.js`. This reduces the risk of another local webpage driving VoiceCode through `127.0.0.1`.

For trusted local integrations, either read the token from the running desktop page context or launch VoiceCode with `VOICECODE_API_TOKEN` set to a known high-entropy value and send:

```http
X-VoiceCode-Token: your-token
```

`VOICECODE_DISABLE_API_TOKEN=1` is available for isolated tests and controlled development environments only. Do not disable token checks in normal desktop use.

The server also validates loopback `Host` values and rejects cross-origin mutation requests. Responses include CSP, anti-framing, content-type sniffing, referrer, and permissions-policy headers.

## Endpoints

### `GET /health`

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

`model_state.status` can be `not_loaded`, `loading`, `ready`, `error`, or `skipped`.

### `GET /config`

Returns persisted configuration merged with defaults. Invalid config files are ignored and defaults are used.

### `POST /config`

Updates supported config keys. Unknown keys return `400`.

Supported keys:

| Key | Values |
| --- | --- |
| `hotkey` | object with `modifiers` (`alt`, `ctrl`, `shift`) and non-empty `key` |
| `model` | `tiny`, `base`, `small`, `medium`, `large-v3`, `large-v3-turbo`, `distil-large-v3` |
| `device` | `auto`, `cpu`, `cuda` |
| `compute_type` | `auto`, `default`, `int8`, `int8_float16`, `int16`, `float16`, `float32` |
| `beam_size` | integer from 1 to 10 |
| `vad_filter` | boolean |
| `language` | `auto`, `zh`, `en`, `ja` |
| `ui_language` | `en`, `zh`, `ja` |
| `audio_device` | empty string, `null`, device index, or device name |
| `text_mode` | `plain`, `coding`, `markdown`, `prompt` |
| `history_enabled` | boolean |
| `history_limit` | integer from 1 to 500 |
| `font_size` | `0.85rem`, `1rem`, `1.2rem`, `1.5rem` |
| `append_mode` | `append`, `replace` |
| `on_top` | boolean |
| `extensions` | object containing per-extension enable flags and options |

Extension config IDs currently supported: `audio_io`, `exporters`, `hotwords`, `vad`, `zh_normalizer`, `quality`, `diarization`, and `punctuation`.

Example:

```json
{
  "extensions": {
    "hotwords": {"enabled": true, "phrases": ["FastAPI", "CTranslate2"]},
    "vad": {"enabled": true, "engine": "faster_whisper", "min_silence_duration_ms": 700},
    "exporters": {"enabled": true, "formats": ["json", "txt", "srt", "vtt"]}
  }
}
```

### `GET /config/schema`

Returns the current configuration schema version and core field constraints.

### `POST /config/reset`

Restores default configuration, writes it to the user config file, and returns the restored config. The UI reloads the default model after this call.

### `POST /reload_model`

Starts asynchronous Whisper model loading/reloading. It also accepts inference settings and persists them before loading.

Request:

```json
{
  "model": "small",
  "device": "auto",
  "compute_type": "auto",
  "beam_size": 5,
  "vad_filter": true
}
```

Response:

```json
{"status": "loading", "model": "small", "device": "auto", "compute_type": "auto"}
```

If another reload is in progress, returns `409`.

### `POST /record/start`

Starts microphone recording.

Optional request fields:

- `language`: `auto`, `zh`, `en`, or `ja`
- `audio_device`: device index, device name, empty string, or `null`

Idempotent behavior: if recording is already active, returns `started: false`.

### `POST /record/stop`

Stops recording and transcribes captured audio.

Optional request field: `language`.

Success:

```json
{"text": "transcribed text", "language": "en"}
```

The response can also include `language_probability` when the model exposes it.

### `POST /record/cancel`

Cancels active recording/transcription, clears buffered recorder audio, and suppresses stale hotkey callback output.

### `POST /transcribe`

Transcribes audio without using the recorder. This endpoint is useful for local integrations, regression tests, and batch workflows.

Multipart upload:

- field `file`: audio file supported by faster-whisper/PyAV
- field `language` optional: `auto`, `zh`, `en`, `ja`

JSON samples:

```json
{"audio": [0.0, 0.1, -0.1], "language": "en", "output_format": "json"}
```

`audio` must be a non-empty numeric sample array. One-dimensional mono arrays and two-dimensional mono/stereo arrays are accepted. `output_format` can be `json`, `txt`, `srt`, or `vtt` when the `exporters` extension is enabled.

### `GET /onboarding`

Returns whether first-start setup is required, the persisted setup version, selected core preferences, and readiness summaries for runtime dependencies, microphone devices, and the active model.

### `POST /onboarding/complete`

Persists supported first-start preferences and marks the guide complete. Body:

```json
{
  "config": {
    "ui_language": "zh",
    "language": "zh",
    "model": "base",
    "device": "auto",
    "audio_device": ""
  },
  "skipped": false
}
```

Only onboarding-safe config keys are accepted. `skipped` records that the user intentionally finished without resolving every readiness warning.

### `POST /onboarding/reset`

Clears onboarding completion so the guide opens again. Other user settings are preserved.

### `GET /extensions`

Returns effective extension status, UI config schema, installable dependencies, config-aware required dependency IDs, missing required IDs, and current config.

```json
{
  "extensions": [
    {
      "id": "hotwords",
      "enabled": true,
      "ready": true,
      "dependencies": [],
      "missing_dependency_ids": [],
      "config_schema": [
        {"name": "enabled", "type": "boolean", "default": true},
        {"name": "phrases", "type": "string_list", "default": []}
      ],
      "config": {"enabled": true, "phrases": []}
    }
  ]
}
```

### `POST /extensions/<extension_id>`

Validates and persists a single extension config. Use either the config object directly or wrap it under `config`:

```json
{"config": {"enabled": true, "phrases": ["VoiceCode", "CTranslate2"]}}
```

### `POST /extensions/<extension_id>/install`

Starts isolated install tasks for the extension's cataloged optional dependencies. Returns `tasks`; poll each task through `/dependencies/tasks/<task_id>`.

### `GET /dependencies`

Returns downloadable dependency status and the isolated install directory. Source checkouts default to `<project>/VOICE_DEP`; normal installed packages use a user-writable config `dependencies/` directory; `VOICECODE_DEP_DIR` is honored for tests and release overrides. Missing required dependencies and missing dependencies for enabled extensions are listed in `action_required_missing` so the UI can show a closeable warning dialog at startup.

```json
{
  "install_dir": "E:/path/to/voicecode/VOICE_DEP",
  "dependencies": [
    {
      "id": "whisper-runtime",
      "name": "Whisper runtime",
      "installed": false,
      "installed_in_voice_dep": false,
      "missing_modules": ["faster_whisper", "ctranslate2"],
      "github_preferred": true
    }
  ],
  "missing": [],
  "action_required_missing": []
}
```

### `POST /dependencies/install-required`

Starts tasks for every missing dependency marked as required by the core runtime. The endpoint is used by the first-start guide and the Dependencies page. It returns an empty task list when the runtime is already provisioned.

### `POST /dependencies/<dependency_id>/install`

Starts a catalog-constrained asynchronous install from the configured Python package index. Before pip starts, VoiceCode checks free space and obtains thread/process locks. Tasks are persisted, time-limited, cancellable, and record recent output. Binary packages can return `restart_required=true`.

```json
{
  "task": {
    "id": "abc123",
    "dependency_id": "jiwer",
    "action": "install",
    "status": "running",
    "progress": 42,
    "message": "Installing Quality metrics from the configured package index..."
  }
}
```

### `GET /dependencies/tasks`

Returns recent persisted dependency tasks, newest first. Tasks interrupted by an application restart are restored as failed with an interruption message.

### `POST /dependencies/tasks/<task_id>/cancel`

Requests cancellation and terminates the active pip process tree. A completed, failed, or already-cancelled task is returned unchanged.

### `GET /dependencies/tasks/<task_id>`

Returns the current dependency install task, including the last log lines. `status` is `queued`, `running`, `completed`, or `failed`.

### `POST /dependencies/<dependency_id>/uninstall`

Uninstalls files managed for that dependency from `VOICE_DEP`. The request must include `{"confirm": true}`; the frontend requires a second click before sending this confirmation. Uninstall refuses paths outside `VOICE_DEP` and keeps files still referenced by another dependency manifest.

### `GET /models`

Returns supported model metadata, current model, active inference device, compute type, CUDA availability, model load state, model cache directory/status, and per-model compatibility advice.

Each model metadata entry includes size, description, minimum VRAM, recommended VRAM, and a short recommendation. The `compatibility` object marks models as not selectable when the current manual CUDA configuration has less VRAM than the model minimum.


### `GET /models/cache`

Returns the model cache directory and per-model cache summary. VoiceCode uses `VOICECODE_MODEL_DIR` when set, otherwise `<VOICECODE_RUNTIME_DIR>/models` when a runtime directory is configured, otherwise the source-tree `models/` folder for development runs.

```json
{
  "cache_dir": "E:/path/to/voicecode/models",
  "models": {
    "base": {"model": "base", "cached": true, "paths": [".../base"], "size_mb": 148.2}
  }
}
```

### `POST /models/<model_name>/download`

Downloads and loads a supported Whisper model. This reuses the normal model loader, so a successful operation makes the model active and immediately usable. If another model load is already running, returns `409`.

### `DELETE /models/<model_name>/cache`

Deletes cached files for a supported model from the managed model cache directory. The body must include `{"confirm": true}`. Deletion is refused for the currently loaded model or while any model load is in progress.

### `GET /hardware`

Returns hardware capability and active inference profile. When the UI hardware switch is enabled, `device=auto` lets the backend choose the fastest available supported profile: CUDA with the best supported GPU compute type when available, otherwise CPU with an efficient compute type.

```json
{
  "cpu_threads": 8,
  "cuda_available": true,
  "cuda_device_count": 1,
  "active_device": "cuda",
  "active_compute_type": "float16",
  "supported_devices": ["auto", "cpu", "cuda"],
  "supported_compute_types": ["auto", "default", "float16", "float32", "int16", "int8", "int8_float16"]
}
```

### `GET /audio/devices`

Returns available input devices and the default input index.

### `POST /audio/test`

Captures a short local microphone sample and returns peak/RMS/percentage plus `has_signal`. Body accepts `audio_device` and `duration_ms` (50-5000). It returns `409` while recording is active.

### `POST /log`

Writes frontend diagnostic messages through Python logging.

### `GET /stats`

Returns best-effort CPU/RAM/GPU telemetry for the status bar and home page. Values may be `-1` or `null` when telemetry is unavailable.

Notable fields:

- `cpu`: CPU name, physical/logical cores, and frequency when available.
- `cpu_percent`: system CPU utilization.
- `process_cpu_percent`: VoiceCode process CPU utilization.
- `process_memory_mb`: VoiceCode process RSS memory.
- `system_memory_total_mb`, `system_memory_available_mb`, `system_memory_percent`: system memory details.
- `gpu`: NVIDIA GPU name, utilization, VRAM usage, and driver version when NVML is available.

### `GET /history`

Returns recent transcript history. Query parameters:

| Parameter | Purpose |
| --- | --- |
| `limit` | Max entries from 1 to 500 |
| `q` | Case-insensitive text search |
| `language` | Filter by `auto`, `zh`, `en`, or `ja` |
| `model` | Filter by model name |

Each entry includes a stable `id` suitable for single-entry deletion.

### `GET /history/export`

Exports filtered transcript history. Supports the same filter query parameters as `GET /history` plus `format=json`, `format=txt`, or `format=md`. The response is returned as an attachment.

### `DELETE /history/<entry_id>`

Deletes one transcript history entry. The JSON body must include `{"confirm": true}`. `POST /history/<entry_id>` is also accepted for clients that cannot send `DELETE`.

### `POST /history/clear`

Deletes all transcript history.

### `GET /diagnostics/export`

Downloads a ZIP containing redacted diagnostics, redacted config, recent dependency task logs, and a redacted tail of the application log when available. It excludes transcript history and replaces the hotkey key value.

### `GET /diagnostics`

Returns privacy-safe runtime diagnostics such as Python version, platform, config path, log path, model state, static directory, CUDA device count, and active inference profile. It does not include audio or transcript text.

## Model operation state fields

`GET /status` and `GET /models` expose `configured_model`/`configured` and a detailed `model_state`. During downloads, clients can render `target_model`, `phase`, `progress`, `downloaded_bytes`, `estimated_bytes`, `download_speed_bps`, `elapsed_seconds`, `stalled_seconds`, `endpoint`, and `cache_dir`. Errors include `error_code`, `user_message`, sanitized `technical_details`, `suggestions`, `retryable`, and whether a previous active model remains available. Model cache entries now distinguish `partial`, `complete`, and `cached`; `cached` means the required faster-whisper files are complete.
