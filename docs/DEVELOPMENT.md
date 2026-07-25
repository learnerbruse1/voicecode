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

Source development uses the standard Python packaging workflow above. The maintained end-user Windows installer pipeline is documented in [WINDOWS_INSTALLER.md](WINDOWS_INSTALLER.md).

## Quality checks

Run before submitting changes:

```powershell
python -m ruff format --check app.py main.py tests src/voicecode packaging/windows tools
python -m ruff check app.py main.py tests src/voicecode packaging/windows tools
python -m mypy app.py main.py src/voicecode
python -X utf8 -m pytest -q
Get-ChildItem src/voicecode/static/js/*.js | ForEach-Object { node --check $_.FullName }
```

Build a wheel when packaging metadata changes:

```powershell
python -m pip wheel . --no-deps -w dist
```

Generated directories such as `dist/`, `build/`, caches, and egg-info are ignored and should not be committed. Windows packaging changes must also run `python -X utf8 -m py_compile packaging/windows/*.py`, build the installer, and execute `packaging/windows/verify_windows_installer.py` against a disposable installation path.

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

## Backend route modules

Route groups live in `management_api.py`, `history_api.py`, `system_api.py`, and `recording_api.py`. Model state, cache operations, and transcription finalization live in `model_runtime.py`, `model_cache.py`, and `transcription_service.py`. Pass mutable runtime state through context callables instead of importing app globals. Dependency management is split across catalog, environment, installer, and facade modules.

## Static assets

The source-tree UI under `static/` and the packaged UI under `src/voicecode/static/` must stay byte-for-byte synchronized. The test suite enforces this.

## API contracts

- Keep error messages in English.
- Keep the server local-only.
- Preserve local API token checks on mutating endpoints unless a test explicitly disables or forces them.
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

## Static mirror workflow

Treat `src/voicecode/static/` as the editing source, then run `python -X utf8 tools/sync_static.py`. CI runs `--check`; do not manually resolve drift by editing only the root mirror. Core bootstrap infrastructure uses ES Modules while feature scripts remain gradual compatibility modules.

## Browser E2E

Install `.[e2e]`, run `python -m playwright install chromium`, set `VOICECODE_RUN_E2E=1`, and run `pytest tests/e2e`. The smoke test starts a skip-model-load server, verifies first-start rendering, dynamic version metadata, and external catalog loading, and fails on page errors.

## Installer validation

The repeatable Windows verifier performs silent install, payload/catalog/icon checks, embedded-pip execution, optional installed-app HTTP checks, and optional uninstall. Release CI uses `--skip-launch --uninstall`; interactive validation omits `--skip-launch` and additionally checks the desktop UI, single-instance behavior, model readiness, transcription, and microphone capture. The download prerequisites used by the builder are cached below `build/windows/downloads/` so an interrupted download does not force another complete PyInstaller run.
