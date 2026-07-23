# VoiceCode

[English](README.md) | [简体中文](README_zh.md) | [日本語](README_ja.md)

VoiceCode is a local-first desktop speech-to-text app for coding, writing, and prompt drafting. It records microphone audio, transcribes it with [faster-whisper](https://github.com/SYSTRAN/faster-whisper) / CTranslate2, and can type the result into the active application with a push-to-talk hotkey.

## Highlights

- Local transcription powered by Whisper-compatible `faster-whisper` models.
- Automatic NVIDIA CUDA detection with safe CPU fallback.
- Automatic hardware selection UI with manual CPU/CUDA override and blocking progress overlay for long operations.
- Guided first launch for language, runtime dependencies, microphone, and model/hardware setup.
- English, Chinese, and Japanese UI languages loaded from external JSON catalogs.
- Operable extension cards with enable/disable controls, validated configuration, and one-click dependency installation.
- Model cache management page for downloading/loading models and deleting non-active local caches.
- Searchable transcript history with language filters, single-entry deletion, and JSON/TXT/Markdown export.
- Configurable inference device (`auto`, `cpu`, `cuda`) and compute type (`auto`, `int8`, `float16`, `float32`, `int8_float16`).
- Cross-platform Python package layout for Windows, macOS, and Linux development.
- Local-only Flask/Waitress API bound to `127.0.0.1`.
- Desktop UI via `pywebview`, global hotkey via `pynput`, and isolated runtime dependency installs into `VOICE_DEP`.
- Upload/API transcription endpoint for tests, integrations, and batch workflows.
- User-writable config/log/history paths; no writes into the installed package directory.
- English diagnostics and error messages for maintainers.

## Requirements

- Python 3.10+
- A microphone supported by PortAudio / `sounddevice`
- Network access for first model/dependency download unless models and runtime packages are already cached or installed
- Optional NVIDIA GPU with a CUDA/CuDNN runtime compatible with CTranslate2

VoiceCode is distributed as a Python project. This repository intentionally does not include one-click installer scripts or generated installer artifacts.

## Install from source

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m voicecode
```

On first launch, the setup guide checks runtime dependencies, microphone devices, language, model, and hardware preferences. Missing Whisper/audio packages can be installed in one click into the isolated dependency directory. The installer tries GitHub sources first and falls back to PyPI. The guide can be reopened from **About**.

The **Extensions** page supports real enable/disable and validated per-extension settings. Optional packages are installed into the same isolated directory without modifying the package installation.

Use **Settings -> Language** to switch the UI between English, Chinese, and Japanese. English is the default.

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
| `WHISPER_MODEL` | `tiny`, `base`, `small`, `medium`, `large-v3`, `large-v3-turbo`, `distil-large-v3` | Startup model |
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

## Documentation

- [API overview](docs/API.md) and split references under [docs/api/](docs/api/README.md)
- [Architecture](docs/ARCHITECTURE.md) for runtime design and thread-safety boundaries
- [Developer guide](docs/DEVELOPMENT.md) for setup, checks, logging, and frontend layout rules
- [Module boundaries](docs/MODULES.md) for maintainable extension points
- [Configuration guide](docs/CONFIGURATION.md) for config files, environment variables, and reset behavior
- [Hardware and model selection](docs/HARDWARE.md) for CPU/GPU, CUDA, compute types, and VRAM guidance
- [Error handling and resilience](docs/ERROR_HANDLING.md) for request IDs, JSON errors, progress overlays, and fallback behavior
- [Troubleshooting](docs/TROUBLESHOOTING.md) for common model, CUDA, and UI issues
- [Packaging](docs/PACKAGING.md) and [release process](docs/RELEASING.md) for wheel/sdist contents, validation, and release gates
- [Roadmap](docs/ROADMAP.md) for optional extension ideas and future work
- [FAQ](docs/FAQ.md) for user-facing answers

## API

See [docs/API.md](docs/API.md). Important endpoints include:

- `GET /health`
- `GET /status`
- `GET /onboarding`, `POST /onboarding/complete`
- `GET /extensions`, `POST /extensions/<extension_id>`
- `GET /hardware`
- `GET /models`
- `POST /reload_model`
- `POST /record/start`, `POST /record/stop`, `POST /record/cancel`
- `POST /transcribe`
- `GET /dependencies`, `POST /dependencies/install-required`
- `GET /audio/devices`, `POST /audio/test`
- `GET /history`, `POST /history/clear`
- `GET /diagnostics`

See [docs/MODULES.md](docs/MODULES.md) for module boundaries and [docs/ROADMAP.md](docs/ROADMAP.md) for optional feature ideas.

All non-empty JSON request bodies must be JSON objects. Malformed JSON and non-object JSON return `400` without side effects.

## Project layout

```text
voicecode/
|-- src/voicecode/                 # Authoritative package implementation
|   |-- app.py                     # Core Flask/model orchestration and blueprint wiring
|   |-- management_api.py          # Onboarding, extensions, dependencies
|   |-- history_api.py             # History query/export/mutation routes
|   |-- system_api.py              # Hardware, audio test, diagnostics, stats
|   |-- dependency_*.py            # Catalog, environment, installer, shared types
|   |-- audio.py, history.py       # Recorder and persistence services
|   |-- settings.py                # Config schema, validation, paths, model metadata
|   |-- extensions/                # Optional feature modules and registry
|   |-- main.py, runtime.py        # Desktop startup and runtime/cache paths
|   `-- static/                    # Packaged UI, JS feature modules, JSON catalogs
|-- static/                        # Source-tree mirror of packaged UI assets
|-- tests/                         # Smoke/API/runtime/static synchronization tests
|-- docs/                          # API, architecture, packaging, release documentation
|-- app.py, main.py                # Compatibility wrappers
`-- pyproject.toml                 # Packaging, dependencies, tool config
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md), and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## License

MIT. See [LICENSE](LICENSE).
