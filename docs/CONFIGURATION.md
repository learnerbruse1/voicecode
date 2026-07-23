# Configuration Guide

VoiceCode stores configuration in a user-writable path, never inside the installed package directory.

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
| `VOICECODE_HISTORY_FILE` | Override transcript history path |
| `VOICECODE_LOG_FILE` | Override log file path |
| `VOICECODE_LOG_LEVEL` | Python log level, for example `DEBUG` |
| `VOICECODE_LOG_MAX_BYTES` | Rotating log max bytes |
| `VOICECODE_LOG_BACKUP_COUNT` | Number of rotated log files to retain |
| `VOICECODE_MAX_UPLOAD_MB` | Flask max request body size, default 512 MB |
| `VOICECODE_OFFLINE` | Load local cached models only |
| `VOICECODE_SKIP_MODEL_LOAD` | Start UI/API without loading Whisper |
| `WHISPER_MODEL` | Startup model |
| `WHISPER_DEVICE` | `auto`, `cpu`, or `cuda` |
| `WHISPER_COMPUTE_TYPE` | `auto`, `int8`, `float16`, `float32`, etc. |
| `WHISPER_CPU_THREADS` | CPU inference thread count |


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
