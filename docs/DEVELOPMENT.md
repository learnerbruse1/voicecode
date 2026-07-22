# Development Guide

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
python -m voicecode
```

Unix-like systems:

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m voicecode
```

This project intentionally avoids repository-specific one-click setup scripts. Use the standard Python packaging workflow above.

## Quality checks

Run before submitting changes:

```powershell
python -m ruff format --check app.py main.py tests src/voicecode
python -m ruff check app.py main.py tests src/voicecode
python -m mypy app.py main.py src/voicecode
python -X utf8 -m pytest -q
```

Build a wheel when packaging metadata changes:

```powershell
python -m pip wheel . --no-deps -w dist
```

Generated directories such as `dist/`, `build/`, caches, and egg-info are ignored and should not be committed.

## Running without a model

For UI/API preview without downloading Whisper models:

```powershell
$env:VOICECODE_SKIP_MODEL_LOAD = "1"
python -m voicecode
```

For offline-only model loading:

```powershell
$env:VOICECODE_OFFLINE = "1"
$env:VOICECODE_MODEL_DIR = "C:\\path\\to\\cached-models"
python -m voicecode
```

## Hardware testing

Useful overrides:

```powershell
$env:WHISPER_DEVICE = "cpu"
$env:WHISPER_COMPUTE_TYPE = "int8"
python -m voicecode
```

```powershell
$env:WHISPER_DEVICE = "cuda"
$env:WHISPER_COMPUTE_TYPE = "float16"
python -m voicecode
```

Use `GET /hardware`, `GET /models`, and `GET /diagnostics` to inspect the resolved profile.

## Static assets

The source-tree UI under `static/` and the packaged UI under `src/voicecode/static/` must stay byte-for-byte synchronized. The test suite enforces this.

## API contracts

- Keep error messages in English.
- Keep the server local-only.
- Validate JSON bodies before side effects.
- Preserve compatibility wrappers unless a major-version migration removes them.

## Logging

VoiceCode uses English structured log messages suitable for open-source issue reports. Request logs include request ID, method, path, status, and duration. Error responses include the same request ID in the JSON body and `X-VoiceCode-Request-ID` response header.

Useful variables:

| Variable | Purpose |
| --- | --- |
| `VOICECODE_LOG_FILE` | Override the rotating log file path |
| `VOICECODE_LOG_LEVEL` | Set log level, for example `DEBUG` |
| `VOICECODE_LOG_MAX_BYTES` | Max bytes per log file before rotation |
| `VOICECODE_LOG_BACKUP_COUNT` | Number of rotated log files to keep |
| `VOICECODE_DISABLE_FILE_LOG` | Disable file logging for tests or temporary runs |

## Frontend layout

The desktop UI uses a left navigation rail and a right-side scrollable content area. Keep primary speech-to-text controls on the Home page. Move settings, extensions, history, diagnostics, and project information into separate views. For operations that can take time, such as model reload or transcription, use the global progress overlay so the page is dimmed and accidental interactions are discouraged.
