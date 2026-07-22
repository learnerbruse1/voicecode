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
