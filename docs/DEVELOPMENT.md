# Development Guide

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
pre-commit install
```

## Checks

```powershell
python -m pytest
python -m ruff check app.py main.py tests src/voicecode
python -m ruff format --check app.py main.py tests src/voicecode
python -m mypy app.py main.py src/voicecode
python -m pip wheel . --no-deps -w dist
```

## Manual smoke test

1. Run `run.ps1` or `python -m voicecode`.
2. Confirm the window opens and the health endpoint is reachable.
3. Start and stop a short recording.
4. Reload each supported model you intend to ship.
5. Confirm PowerShell output remains readable UTF-8 and error messages are English.

## Release notes

Update `CHANGELOG.md` before publishing. Do not include private audio, local paths with personal data, API keys, or machine-specific logs in public issues or releases.
