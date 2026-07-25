# Configuration Guide

VoiceCode stores configuration in a user-writable path, never inside the installed package directory. Packaged models, optional dependencies, and caches live under the selected installation directory and can remain after uninstall so a reinstall can reuse them.

## Default paths

- Windows: `%APPDATA%\VoiceCode\config.json`
- Linux/macOS: `$XDG_CONFIG_HOME/voicecode/config.json` or `~/.config/voicecode/config.json`

## Important environment variables

| Variable | Purpose |
| --- | --- |
| `VOICECODE_CONFIG_FILE` | Override config file location |
| `VOICECODE_STATIC_DIR` | Override static UI directory |
| `VOICECODE_RUNTIME_DIR` | Runtime/cache root |
| `VOICECODE_MODEL_DIR` | faster-whisper model download/cache root |
| `VOICECODE_DEP_DIR` | Isolated optional dependency directory |
| `PIP_CACHE_DIR` | pip download cache; packaged builds force this below `runtime/cache/pip` |
| `HF_ENDPOINT` | Explicit Hugging Face endpoint; if unset, v0.2.0 probes the official endpoint and reachable mirror |
| `VOICECODE_HISTORY_FILE` | Override transcript history path |
| `VOICECODE_LOG_FILE` | Override log file path |
| `VOICECODE_LOG_LEVEL` | Python log level, for example `DEBUG` |
| `VOICECODE_LOG_MAX_BYTES` | Rotating log max bytes |
| `VOICECODE_LOG_BACKUP_COUNT` | Number of rotated log files to retain |
| `VOICECODE_MAX_UPLOAD_MB` | Flask max request body size, default 512 MB |
| `VOICECODE_API_TOKEN` | Optional fixed token for trusted local API integrations; generated randomly by default |
| `VOICECODE_DISABLE_API_TOKEN` | Disable mutating-request token checks for isolated tests only |
| `VOICECODE_OFFLINE` | Load local cached models only |
| `VOICECODE_SKIP_MODEL_LOAD` | Start UI/API without loading Whisper |
| `WHISPER_MODEL` | Startup model |
| `WHISPER_DEVICE` | `auto`, `cpu`, or `cuda` |
| `WHISPER_COMPUTE_TYPE` | `auto`, `int8`, `float16`, `float32`, etc. |
| `WHISPER_CPU_THREADS` | CPU inference thread count |



## Local API protection

VoiceCode binds to `127.0.0.1`, but mutating API calls are still protected by a per-process local API token in normal runtime. The desktop page receives the token through a non-cacheable same-origin HTML meta tag and sends it as `X-VoiceCode-Token` for JSON writes.

Use `VOICECODE_API_TOKEN` only when a trusted local integration needs a stable token. Use `VOICECODE_DISABLE_API_TOKEN=1` only in isolated development or test environments.


## Model cache management

The **Models** page shows every supported Whisper model, its hardware guidance, whether VoiceCode sees a local cache, and the managed cache directory. Users can download/load a model or delete a non-active model cache with a second confirmation click.

Model cache root resolution:

1. `VOICECODE_MODEL_DIR` when explicitly set.
2. `<VOICECODE_RUNTIME_DIR>/models` when `VOICECODE_RUNTIME_DIR` is configured by a packaged/runtime launch.
3. `<project>/models` for source-tree development runs.

Deletion only removes matching model cache entries inside the managed cache root and is refused for the active model.

## Language and localization

VoiceCode separates two language settings:

| Config key | Values | Purpose | Default |
| --- | --- | --- | --- |
| `ui_language` | `en`, `zh`, `ja` | Desktop interface language | `en` |
| `language` | `auto`, `zh`, `en`, `ja` | Default transcription language sent to Whisper | `zh` |

The Settings page exposes these controls in a dedicated **Language** module. Changing `ui_language` updates static labels, current view titles, dynamic panels, status chips, and accessibility labels without restarting the app. The frontend sets `html[data-ui-language]` so CSS can adapt label widths and wrapping for English, Chinese, and Japanese.

When adding a new UI language:

1. Add the code to `VALID_UI_LANGUAGES` in `src/voicecode/settings.py`.
2. Add a complete catalog to `static/js/i18n.js` and mirror it to `src/voicecode/static/js/i18n.js`.
3. Add layout overrides in `static/css/app.css` if labels need different spacing.
4. Update tests that verify i18n catalog completeness and static asset synchronization.


## Transcript history

When `history_enabled` is true, successful transcriptions are appended to a JSONL history file in the user-writable config area unless `VOICECODE_HISTORY_FILE` overrides it. The History page can search text, filter by language, export filtered results as JSON/TXT/Markdown, delete individual entries with confirmation, or clear all history.

Each history entry stores a stable `id`, timestamp, transcription language, model, and final text. Older entries without an `id` receive a deterministic compatibility ID when read.

## Resetting defaults

Use the UI button:

```text
Settings -> Interface -> Restore defaults
```

Or API:

```http
POST /config/reset
```

After reset, the UI reloads the default model.

## Extension config

Extensions are configured under the `extensions` object. Unknown extension IDs and unknown nested keys are rejected.

Example:

```json
{
  "extensions": {
    "hotwords": {"enabled": true, "phrases": ["FastAPI", "CTranslate2"]},
    "vad": {"enabled": true, "engine": "faster_whisper", "min_silence_duration_ms": 700}
  }
}
```

## First-start state

The `onboarding` object stores `completed`, `completed_version`, and `skipped`. Use `GET /onboarding`, `POST /onboarding/complete`, and `POST /onboarding/reset` for normal UI/client behavior. Resetting onboarding preserves model, language, extension, and history settings.

The guide can save only UI/transcription language, model, device, compute type, audio device, and hotkey. Full config validation still applies.

## Isolated dependency directory

Resolution order is `VOICECODE_DEP_DIR`, `<VOICECODE_RUNTIME_DIR>/dependencies` for packaged runtime mode, then source-tree `<project>/VOICE_DEP`, or the user config `dependencies/` directory for a normal installed package. The directory is inserted after application and standard-library paths but before global site-packages; `.pth` files in the optional directory are not executed. Install manifests live under `.voicecode/`; do not edit them while an install/uninstall is running.

## Configuration versions and migration

The current schema is `config_version: 2`. Files without a version are treated as version 1, migrated to current extension defaults/onboarding fields, then validated. Config files from a future unsupported version are rejected rather than silently rewritten. `GET /config/schema` exposes core constraints.

## Heavy extension credentials

Diarization stores only the environment-variable name (`token_env`, default `HF_TOKEN`), never the token value. Set that variable before starting VoiceCode. NeMo and pyannote model names and execution devices are configurable, and binary dependency installation can require a full application restart.

## Model download network controls

VoiceCode sets process-local defaults `HF_HUB_ETAG_TIMEOUT=10`, `HF_HUB_DOWNLOAD_TIMEOUT=30`, and `HF_HUB_DISABLE_XET=1` unless the user already supplied values. Disabling Xet makes `huggingface_hub` use its regular HTTP downloader, which is more reliable on networks that cannot sustain the CAS/Xet bridge used in the July 24, 2026 installed log. `HF_ENDPOINT` still selects an explicit host; when it is unset, VoiceCode probes the official endpoint and the configured mirror fallback.

## Theme and hardware layout

`theme` accepts `system`, `dark`, or `light`. The top bar intentionally contains only compact CPU, GPU, and memory utilization. Detailed process, VRAM, driver, compute type, and model information is displayed under Settings.
