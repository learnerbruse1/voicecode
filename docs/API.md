# VoiceCode API

VoiceCode exposes a local-only HTTP API on `127.0.0.1` for the desktop UI and local integrations. The default port is `7788` and can be overridden with `PORT`.

The server must not bind to a public interface. Desktop startup verifies that `/health` returns the current process PID so repeated launches and unrelated services fail clearly.

All non-empty JSON request bodies must be valid JSON objects. Malformed JSON, JSON `null`, arrays, strings, numbers, and booleans return `400` and must not trigger side effects.

Error responses use:

```json
{"error": "English error message", "request_id": "short request id"}
```

Each response also includes `X-VoiceCode-Request-ID`. The server logs request start/completion with method, path, status, duration, and request ID so UI/API failures can be correlated with log lines.

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

### `GET /extensions`

Returns extension status, availability, optional dependencies, missing dependencies, and effective config.

```json
{
  "extensions": [
    {
      "id": "hotwords",
      "name": "Hotwords",
      "enabled": true,
      "available": true,
      "optional_dependencies": [],
      "missing_dependencies": [],
      "config": {"enabled": true, "phrases": []}
    }
  ]
}
```

### `GET /models`

Returns supported model metadata, current model, active inference device, compute type, CUDA availability, model load state, and per-model compatibility advice.

Each model metadata entry includes size, description, minimum VRAM, recommended VRAM, and a short recommendation. The `compatibility` object marks models as not selectable when the current manual CUDA configuration has less VRAM than the model minimum.

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

Returns recent transcript history. Query parameter: `limit` from 1 to 500.

### `POST /history/clear`

Deletes transcript history.

### `GET /diagnostics`

Returns privacy-safe runtime diagnostics such as Python version, platform, config path, log path, model state, static directory, CUDA device count, and active inference profile. It does not include audio or transcript text.
