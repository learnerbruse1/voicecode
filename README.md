# VoiceCode

[English](README.md) | [简体中文](README_zh.md) | [日本語](README_ja.md)

VoiceCode is a local-first desktop speech-to-text app for coding, writing, and prompt drafting. It records microphone audio, transcribes it with [faster-whisper](https://github.com/SYSTRAN/faster-whisper) / CTranslate2, and can type the result into the active application with a push-to-talk hotkey.

## Highlights

- Local transcription powered by Whisper-compatible `faster-whisper` models.
- Automatic NVIDIA CUDA detection with safe CPU fallback.
- Automatic hardware selection UI with manual CPU/CUDA override and blocking progress overlay for long operations.
- Configurable inference device (`auto`, `cpu`, `cuda`) and compute type (`auto`, `int8`, `float16`, `float32`, `int8_float16`).
- Cross-platform Python package layout for Windows, macOS, and Linux development.
- Local-only Flask/Waitress API bound to `127.0.0.1`.
- Desktop UI via `pywebview`, global hotkey via `pynput`, microphone capture via `sounddevice`.
- Upload/API transcription endpoint for tests, integrations, and batch workflows.
- User-writable config/log/history paths; no writes into the installed package directory.
- English diagnostics and error messages for maintainers.

## Requirements

- Python 3.10+
- A microphone supported by PortAudio / `sounddevice`
- Network access for first model download unless models are already cached
- Optional NVIDIA GPU with a CUDA/CuDNN runtime compatible with CTranslate2

VoiceCode is distributed as a Python project. This repository intentionally does not include one-click installer scripts or generated installer artifacts.

## Install from source

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m voicecode
```

On Unix-like systems:

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m voicecode
```

> PowerShell users can replace the first command with any preferred virtual environment workflow. No repository setup script is required.

## CPU and NVIDIA GPU behavior

By default, VoiceCode chooses `cuda/float16` when CTranslate2 can see a CUDA-capable NVIDIA GPU; otherwise it uses `cpu/int8`. If CUDA initialization or inference fails, VoiceCode falls back to `cpu/int8` and keeps the app usable.

Environment overrides:

| Variable | Values | Purpose |
| --- | --- | --- |
| `WHISPER_MODEL` | `tiny`, `base`, `small`, `medium`, `large-v3`, `distil-large-v3` | Startup model |
| `WHISPER_DEVICE` | `auto`, `cpu`, `cuda` | Preferred inference device |
| `WHISPER_COMPUTE_TYPE` | `auto`, `int8`, `float16`, `float32`, `int8_float16` | Preferred compute type |
| `WHISPER_CPU_THREADS` | positive integer | CPU worker threads |
| `VOICECODE_MODEL_DIR` | path | Model download/cache root for faster-whisper |
| `VOICECODE_OFFLINE` | `1`, `true`, `yes`, `on` | Load cached models only |
| `VOICECODE_SKIP_MODEL_LOAD` | `1`, `true`, `yes`, `on` | Start UI without loading Whisper |

Large models are more accurate but require more RAM/VRAM. Recommended defaults:

- CPU-only: `base` or `small`, `device=cpu`, `compute_type=int8`.
- NVIDIA GPU: `small`, `medium`, `large-v3`, or `distil-large-v3`, `device=auto`, `compute_type=auto`.

## Run checks

```powershell
python -m ruff format --check app.py main.py tests src/voicecode
python -m ruff check app.py main.py tests src/voicecode
python -m mypy app.py main.py src/voicecode
python -X utf8 -m pytest -q
```

## Runtime data

VoiceCode stores user data outside the package directory:

- Windows config: `%APPDATA%\VoiceCode\config.json`
- Linux/macOS config: `$XDG_CONFIG_HOME/voicecode/config.json` or `~/.config/voicecode/config.json`
- Logs: `logs/voicecode.log` under the config directory by default
- Transcript history: `history.jsonl` under the config directory by default

Additional overrides: `VOICECODE_CONFIG_FILE`, `VOICECODE_STATIC_DIR`, `VOICECODE_RUNTIME_DIR`, `VOICECODE_LOG_FILE`, `VOICECODE_HISTORY_FILE`, `VOICECODE_LOG_LEVEL`, and `PORT`.

## API

See [docs/API.md](docs/API.md). Important endpoints include:

- `GET /health`
- `GET /status`
- `GET /extensions`
- `GET /hardware`
- `GET /models`
- `POST /reload_model`
- `POST /record/start`, `POST /record/stop`, `POST /record/cancel`
- `POST /transcribe`
- `GET /audio/devices`
- `GET /history`, `POST /history/clear`
- `GET /diagnostics`

See [docs/MODULES.md](docs/MODULES.md) for module boundaries and [docs/ROADMAP.md](docs/ROADMAP.md) for optional feature ideas.

All non-empty JSON request bodies must be JSON objects. Malformed JSON and non-object JSON return `400` without side effects.

## Project layout

```text
voicecode/
├── src/voicecode/       # Authoritative package implementation
│   ├── app.py           # Local API, config, recorder, Whisper inference
│   ├── main.py          # Desktop window, hotkey integration, startup checks
│   ├── runtime.py       # Runtime/cache path helpers
│   └── static/          # Packaged web UI assets
├── static/              # Source-tree copy of web UI assets (kept in sync by tests)
├── tests/               # Smoke/API/runtime tests with fake Whisper/audio modules
├── docs/                # API, architecture, development, FAQ
├── app.py, main.py      # Compatibility wrappers
└── pyproject.toml       # Packaging, dependencies, tool config
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md), and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## License

MIT. See [LICENSE](LICENSE).
