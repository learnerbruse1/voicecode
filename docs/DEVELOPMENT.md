# Development Guide

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
pre-commit install
```

Use PowerShell with UTF-8 output enabled on Windows.

## Checks

Run at least:

```powershell
python -m ruff format --check app.py main.py tests src/voicecode
python -m ruff check app.py main.py tests src/voicecode
python -m mypy app.py main.py src/voicecode
python -X utf8 -m pytest -q
```

For release-impacting changes, also run:

```powershell
python -X utf8 -m py_compile app.py main.py src/voicecode/app.py src/voicecode/main.py src/voicecode/__init__.py src/voicecode/__main__.py src/voicecode/runtime.py
python -m pip wheel . --no-deps -w dist
```

The test suite uses fake Whisper and audio-device modules for smoke tests, so it does not download models or require a real microphone. The current release candidate has `35 passed` in the smoke suite.

The smoke suite also covers defensive API input cases, including malformed JSON, JSON `null`, non-object payloads, boolean-vs-integer config confusion, invalid hotkey modifiers, repeated start, cancel/stop ordering, model reload races, and startup port/PID conflicts.

## Manual smoke test

1. Run `run.ps1`, `run.bat`, `python main.py`, or `python -m voicecode`.
2. Confirm the window opens and `/health` is reachable on `127.0.0.1`.
3. Confirm `/health` returns the current process PID.
4. Start and stop a short recording.
5. Cancel a recording and confirm stale output is suppressed.
6. Reload each supported model you intend to ship.
7. Try launching a second instance and confirm the port/PID conflict message is clear.
8. Confirm PowerShell output remains readable UTF-8 and error messages are English.

## Packaging and installer build

The recommended Windows release packaging project is in `packaging/installer/`.

Build the one-folder app and Inno Setup installer:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\packaging\installer\build-installer.ps1
```

Build only the PyInstaller one-folder app:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\packaging\installer\build-installer.ps1 -SkipInno
```

Outputs:

```text
packaging\installer\dist\VoiceCode\
packaging\installer\Output\VoiceCode-0.1.0-windows-x86_64-setup.exe
```

The installer uses Inno Setup 6 and supports custom install directories. It defaults to non-admin per-user installs, while allowing elevation through the installer dialog/command line when a user chooses a protected directory. The default install directory is per-user:

```text
%LOCALAPPDATA%\Programs\VoiceCode
```

The packaged launcher redirects future model/download caches to:

```text
<install-dir>\runtime\cache
<install-dir>\runtime\models
```

Generated packaging outputs are ignored by `packaging/installer/.gitignore`.

## Installer release test checklist

1. Build from a clean working tree or clean CI environment.
2. Install to the default path.
3. Install to a custom user-writable path.
4. Confirm `VoiceCode.exe`, `_internal`, `runtime`, `runtime\cache`, and `runtime\models` exist under the chosen path.
5. Launch the installed app and verify the local server binds only to `127.0.0.1`.
6. Trigger first model load/download and confirm files appear under `<install-dir>\runtime`.
7. Verify Start Menu and optional desktop shortcuts.
8. Uninstall and confirm the app files are removed. Large user-downloaded runtime caches may remain if Windows cannot remove files in use; document manual cleanup if needed.
9. Test on a clean Windows VM with microphone access before publishing.

## Optional tray support

Optional tray support can be tested with:

```powershell
python -m pip install -e ".[tray]"
$env:VOICECODE_ENABLE_TRAY = "1"
python -m voicecode
```

## Frontend modules

The desktop UI intentionally uses plain browser scripts without a build step. Keep script order in `static/index.html` synchronized with `src/voicecode/static/index.html`. The main modules are:

- `i18n.js`: English, Simplified Chinese, and Japanese UI strings
- `dom.js`: DOM references and shared UI state
- `modal.js`: user-facing error/details dialog
- `api.js`: local API helper
- `config.js`: settings load/save and microphone discovery
- `hotkey.js`: hotkey editing UI
- `settings.js`: settings event handlers
- `recorder.js`: recording controls and transcript rendering
- `history.js`: transcript history and diagnostics buttons
- `status.js`: model status polling and performance stats
- `app.js`: bootstrap only

## Release notes

Update `CHANGELOG.md` before publishing. Do not include private audio, local paths with personal data, API keys, or machine-specific logs in public issues or releases.
