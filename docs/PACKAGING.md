# Packaging Guide

VoiceCode is an installable Python package with a mirrored source-tree UI. The authoritative Python code and packaged static assets live under `src/voicecode/`.

## Supported artifacts

| Artifact | Purpose | Command |
| --- | --- | --- |
| Wheel | Normal Python installation | `python -m build --wheel` |
| Source distribution | Reproducible source release | `python -m build --sdist` |
| Local wheel smoke build | Quick packaging check without extra tools | `python -m pip wheel . --no-deps -w dist` |

Generated files under `dist/`, `build/`, and `*.egg-info` are ignored and must not be committed.

## Package contents

The wheel must include:

- `voicecode` Python modules and `voicecode.extensions`;
- `voicecode/static/index.html`;
- `voicecode/static/css/*.css`;
- `voicecode/static/js/*.js`;
- `voicecode/static/i18n/en.json`, `zh.json`, and `ja.json`.

`pyproject.toml` declares package data and `MANIFEST.in` supplies documentation/static files to source distributions. Run the static synchronization test before building because `static/` and `src/voicecode/static/` must be byte-identical.

## Runtime and optional dependencies

The base wheel intentionally installs the desktop/API shell but keeps transcription and audio capture in the `runtime` extra:

```powershell
python -m pip install "voicecode[runtime]"
```

The first-start guide can install missing runtime packages into the isolated dependency directory after launch. This does not modify the installed wheel. Optional feature extras remain available for managed environments:

```powershell
python -m pip install "voicecode[extensions]"
python -m pip install "voicecode[gpu,tray]"
```

Managed installs may provision packages ahead of time. The local API remains bound to `127.0.0.1`.

## Runtime data in packaged builds

`voicecode.runtime.configure_runtime_paths()` keeps mutable caches outside package resources. Frozen builds default to `<executable-dir>/runtime`; normal Python installs use user/cache defaults unless `VOICECODE_RUNTIME_DIR` is set.

```text
runtime/
??? cache/
?   ??? huggingface/
?   ??? transformers/
??? dependencies/       # in-app isolated packages in packaged runtime mode
??? models/             # faster-whisper model cache
```

Configuration, logs, and transcript history remain in the user config directory, not beside package code.

## Build and inspect

```powershell
python -m pip install --upgrade build twine
Remove-Item -Recurse -Force dist -ErrorAction SilentlyContinue
python -m build
python -m twine check dist/*
python -m pip install --force-reinstall --no-deps (Get-ChildItem dist/*.whl | Select-Object -First 1).FullName
python -m voicecode
```

Before deleting `dist/`, resolve it to the repository root and do not remove arbitrary computed paths.

Inspect wheel contents with Python's `zipfile` module or `tar -tf` for the source distribution. Confirm every catalog under `voicecode/static/i18n/` is present.

## Desktop bundlers

PyInstaller, Nuitka, MSI/DMG/AppImage, and code signing are downstream release choices, not committed generated artifacts. A desktop bundle must:

1. include all packaged static assets and external JSON catalogs;
2. call runtime path setup before importing `voicecode.app`;
3. keep the HTTP listener on `127.0.0.1`;
4. preserve `/health` PID verification;
5. provide writable runtime/model/dependency directories;
6. include platform PortAudio/webview prerequisites;
7. test first-start dependency installation and restart behavior;
8. sign/notarize artifacts according to the target platform.

## Packaging verification matrix

| Check | Wheel | sdist | Frozen desktop |
| --- | --- | --- | --- |
| Import `voicecode` | Required | Required | Required |
| Load `/` and JSON catalogs | Required | Required | Required |
| Config writes outside package | Required | Required | Required |
| `VOICECODE_RUNTIME_DIR` override | Required | Required | Required |
| First-start guide | Smoke | Smoke | Full |
| Dependency install/uninstall | Isolated test | Isolated test | Full |
| CPU transcription | Optional CI | Optional CI | Release gate |
| CUDA transcription | Hardware CI/manual | Hardware CI/manual | Release gate when advertised |
