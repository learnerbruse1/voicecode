# Contributing

Thanks for helping improve VoiceCode.

## Before you submit changes

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

If packaging or runtime path behavior changed, build and smoke-test the Windows installer:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\packaging\installer\build-installer.ps1
```

## Code style

- Prefer small, focused changes.
- Keep platform-specific behavior behind safe fallbacks.
- Keep the local HTTP server bound to `127.0.0.1` only.
- Keep user-visible logs, exceptions, API errors, and script output in English.
- Add or update tests for bug fixes and boundary behavior.
- Treat non-empty API JSON request bodies as objects only; add regression tests for malformed/non-object payloads when touching API handlers.
- Do not write config into the installed package directory.
- Keep packaged runtime/model caches under the selected install directory for frozen builds.
- Do not commit generated caches or packaging outputs such as `__pycache__`, `.pytest_cache`, `htmlcov`, `dist/`, `build/`, or `packaging/installer/Output/`.

## Documentation

Update README/docs/packaging documentation when you change:

- install or packaging behavior
- runtime/cache/config paths
- environment variables
- API endpoints or response shapes
- user-visible troubleshooting steps
