# VoiceCode

Offline speech-to-text desktop app for vibe coding. VoiceCode records audio locally, transcribes it with Whisper, and can type the recognized text into the active application through a global hotkey.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey)

## Features

- Offline transcription with `faster-whisper`
- Windows desktop UI powered by `pywebview`
- Local Flask/Waitress API bound to `127.0.0.1`
- Global push-to-talk hotkey support
- UTF-8-safe console output for PowerShell and cmd
- English logs and error messages for release diagnostics
- User-writable config directory with environment-variable overrides
- Installable package entry point: `voicecode`

## Requirements

- Windows 10/11 is the primary supported desktop target
- Python 3.10 or newer
- Microphone access
- Optional NVIDIA GPU for CUDA inference

## Quick start

### PowerShell

```powershell
.\setup.ps1
.\run.ps1
```

### cmd.exe

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

## Configuration

VoiceCode stores config in a user-writable directory instead of the installed package directory.

- Windows default: `%APPDATA%\VoiceCode\config.json`
- Linux/macOS default: `$XDG_CONFIG_HOME/voicecode/config.json` or `~/.config/voicecode/config.json`

Useful environment variables:

| Variable | Purpose |
| --- | --- |
| `VOICECODE_CONFIG_FILE` | Override the config file location |
| `VOICECODE_STATIC_DIR` | Override the web UI static directory |
| `VOICECODE_LOG_LEVEL` | Set Python logging level, for example `DEBUG` |
| `PORT` | Override the local HTTP port, default `7788` |
| `WHISPER_MODEL` | Set startup Whisper model, default `base` |

## API and architecture

- `GET /health` returns service readiness.
- `GET /status` returns model and recorder state.
- `GET /config` and `POST /config` read/update supported settings.
- `POST /reload_model` reloads a supported Whisper model.
- `POST /record/start`, `POST /record/stop`, and `POST /record/cancel` control recording.
- `GET /stats` returns best-effort CPU/RAM/GPU telemetry.

See `docs/API.md` and `docs/ARCHITECTURE.md` for more detail.

## Privacy

VoiceCode is designed to run locally. Audio is captured on the local machine and sent only to the local Flask server at `127.0.0.1`.

## Release checklist

Before publishing a release:

1. Run the full checks:
   ```powershell
   python -m pytest
   python -m ruff check app.py main.py tests src/voicecode
   python -m mypy app.py main.py src/voicecode
   python -m pip wheel . --no-deps -w dist
   ```
2. Confirm the desktop app starts with `run.ps1`, `run.bat`, and `voicecode`.
3. Confirm logs and error messages are English.
4. Confirm `voicecode/static/index.html` is included in the built wheel.
5. Update `CHANGELOG.md`.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Security

See [SECURITY.md](SECURITY.md).

## Code of Conduct

See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## License

MIT. See [LICENSE](LICENSE).
