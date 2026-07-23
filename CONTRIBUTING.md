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

For metadata or runtime-path changes, also run:

```powershell
python -X utf8 -m py_compile app.py main.py src/voicecode/app.py src/voicecode/main.py src/voicecode/__init__.py src/voicecode/__main__.py src/voicecode/runtime.py
python -m pip wheel . --no-deps -w dist
```

## Code style

- Prefer small, focused changes.
- Keep platform-specific behavior behind safe fallbacks.
- Keep the local HTTP server bound to `127.0.0.1` only.
- Keep user-visible logs, exceptions, API errors, and script output in English.
- Add or update tests for bug fixes, hardware fallback behavior, and API boundaries.
- Treat non-empty API JSON request bodies as objects only; malformed/non-object payloads must return `400` before side effects.
- Do not write config, logs, history, or model caches into the installed package directory by default.
- Do not commit generated caches or outputs such as `__pycache__`, `.pytest_cache`, `htmlcov`, `dist/`, `build/`, or `*.egg-info`.
- Do not reintroduce repository-specific one-click setup or installer scripts without a documented maintenance plan.

## Frontend and extensions

Keep root and packaged static trees synchronized. Add visible copy to all external JSON catalogs. New extension fields require defaults, validation, registry schema, dependency mapping when needed, API tests, and documentation.

## Packaging and release changes

For package-data, runtime-path, or release workflow changes, follow `docs/PACKAGING.md` and `docs/RELEASING.md`, build both wheel and sdist, and inspect catalog/static inclusion.

## Documentation

Update README and docs when you change:

- install behavior
- runtime/cache/config paths
- hardware or model selection behavior
- environment variables
- API endpoints or response shapes
- user-visible troubleshooting steps
