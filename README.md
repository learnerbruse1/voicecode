# VoiceCode

[English](README.md) | [简体中文](README_zh.md) | [日本語](README_ja.md)

Offline speech-to-text desktop app for vibe coding. VoiceCode records audio locally, transcribes it with Whisper, and can type the recognized text into the active application through a global push-to-talk hotkey.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey)

## Features

- Offline transcription with `faster-whisper`
- Windows desktop UI powered by `pywebview`
- Local Flask/Waitress API bound to `127.0.0.1`
- Global push-to-talk hotkey support
- English, Simplified Chinese, and Japanese UI language switching
- Transcription language options: auto detect, Chinese, English, and Japanese
- No-model preview mode via `VOICECODE_SKIP_MODEL_LOAD=1`
- Split frontend assets for easier maintenance
- Optional tray support via the `.[tray]` extra and `VOICECODE_ENABLE_TRAY=1`
- Text post-processing modes for plain text, coding, Markdown, and prompts
- Optional transcript history stored locally
- Microphone device selection and local diagnostics panel
- UTF-8-safe console output for PowerShell and cmd
- English logs and error messages for release diagnostics
- User-writable config directory with environment-variable overrides
- Packaged Windows installer with selectable install directory
- Packaged runtime cache layout for model downloads under the install folder
- Installable package entry point: `voicecode`

## Requirements

### For end users

- Windows 10/11
- Microphone access
- Network access only if the selected Whisper model is not already cached
- Optional NVIDIA GPU for CUDA inference

End users do **not** need to install Python when using the Windows installer.

### For development

- Python 3.10 or newer
- PowerShell with UTF-8 output enabled on Windows
- Optional Inno Setup 6 for building the Windows installer

## Install and run

### Recommended: Windows installer

Download or build:

```text
packaging/installer/Output/VoiceCodeSetup-0.1.0.exe
```

Run the installer and choose the installation folder when prompted. The default is:

```text
%LOCALAPPDATA%\Programs\VoiceCode
```

After installation, launch VoiceCode from the Start Menu or optional desktop shortcut.

The packaged app keeps Python/native dependencies under the selected install directory. Future Hugging Face / faster-whisper model downloads are redirected to:

```text
<install-dir>
untime\cache
<install-dir>
untime\models
```

This keeps the application and its large runtime downloads easy to find, back up, move, or delete.

### Development quick start: PowerShell

```powershell
.\setup.ps1
.
un.ps1
```

### Development quick start: cmd.exe

```bat
setup.bat
run.bat
```

### Python package workflow

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\voicecode.exe
```

You can also run:

```powershell
python -m voicecode
```

## Development

```powershell
python -m pip install -e ".[dev]"
pre-commit install
python -m pytest
python -m ruff check app.py main.py tests src/voicecode
python -m mypy app.py main.py src/voicecode
```

The test suite uses fake Whisper and audio-device modules for smoke tests, so it does not download models or require a real microphone.

## Configuration and runtime data

VoiceCode stores user settings in a user-writable directory instead of the installed package directory.

- Windows config default: `%APPDATA%\VoiceCode\config.json`
- Linux/macOS config default: `$XDG_CONFIG_HOME/voicecode/config.json` or `~/.config/voicecode/config.json`
- Windows log default: `%APPDATA%\VoiceCode\logs\voicecode.log`
- Transcript history default: next to the config file as `history.jsonl`

Packaged Windows builds additionally set runtime cache variables so model downloads stay under the install folder.

Useful environment variables:

| Variable | Purpose |
| --- | --- |
| `VOICECODE_CONFIG_FILE` | Override the config file location |
| `VOICECODE_STATIC_DIR` | Override the web UI static directory |
| `VOICECODE_RUNTIME_DIR` | Override packaged runtime/cache root |
| `VOICECODE_MODEL_DIR` | Override local model directory hint |
| `VOICECODE_LOG_FILE` | Override log file location |
| `VOICECODE_LOG_LEVEL` | Set Python logging level, for example `DEBUG` |
| `VOICECODE_HISTORY_FILE` | Override transcript history path |
| `VOICECODE_SKIP_MODEL_LOAD` | Start the UI without loading Whisper, for preview/testing |
| `VOICECODE_ENABLE_TRAY` | Enable optional system tray integration when dependencies are installed |
| `PORT` | Override the local HTTP port, default `7788` |
| `WHISPER_MODEL` | Set startup Whisper model, default `base` |
| `HF_HOME`, `HF_HUB_CACHE`, `HUGGINGFACE_HUB_CACHE`, `TRANSFORMERS_CACHE`, `XDG_CACHE_HOME` | Lower-level cache overrides used by packaged builds |

## API and architecture

- `GET /health` returns service readiness and the server PID.
- `GET /status` returns model and recorder state.
- `GET /config` and `POST /config` read/update supported settings.
- `POST /reload_model` reloads a supported Whisper model.
- `POST /record/start`, `POST /record/stop`, and `POST /record/cancel` control recording.
- `GET /stats` returns best-effort CPU/RAM/GPU telemetry.

See [docs/API.md](docs/API.md), [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md), and [docs/FAQ.md](docs/FAQ.md) for more detail.

## Build a Windows installer

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\packaging\installer\build-installer.ps1
```

Outputs:

```text
packaging\installer\dist\VoiceCode\
packaging\installer\Output\VoiceCodeSetup-0.1.0.exe
```

If Inno Setup is not available, build only the one-folder app:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\packaging\installer\build-installer.ps1 -SkipInno
```

## Final release validation

The current release candidate has passed:

- `ruff format --check`
- `ruff check`
- `mypy`
- `pytest` (`35 passed`)
- `py_compile` for all entry modules
- wheel build
- PyInstaller one-folder build
- Inno Setup installer build
- custom-directory installer install/uninstall smoke test

## Privacy

VoiceCode is designed to run locally. Audio is captured on the local machine and sent only to the local Flask server at `127.0.0.1`. Transcript history, logs, settings, and model caches are local files and are not uploaded by VoiceCode.

## Release checklist

Before publishing a release:

1. Run the full checks:
   ```powershell
   python -m ruff format --check app.py main.py tests src/voicecode
   python -m ruff check app.py main.py tests src/voicecode
   python -m mypy app.py main.py src/voicecode
   python -X utf8 -m pytest -q
   python -X utf8 -m py_compile app.py main.py src/voicecode/app.py src/voicecode/main.py src/voicecode/__init__.py src/voicecode/__main__.py src/voicecode/runtime.py
   python -m pip wheel . --no-deps -w dist
   ```
2. Build the installer with `packaging/installer/build-installer.ps1`.
3. Install to both the default path and a custom user-writable path.
4. Confirm `VoiceCode.exe`, `_internal`, and `runtime` are present under the install directory.
5. Confirm first model download/cache writes under `<install-dir>
untime`.
6. Confirm the local server binds only to `127.0.0.1` and repeated launch detects port/PID conflicts.
7. Confirm logs and error messages are English.
8. Update `CHANGELOG.md`.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Security

See [SECURITY.md](SECURITY.md).

## Code of Conduct

See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## License

MIT. See [LICENSE](LICENSE).
