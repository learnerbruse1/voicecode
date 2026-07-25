# Packaging Guide

VoiceCode is an installable Python package with a mirrored source-tree UI. The authoritative Python code and packaged static assets live under `src/voicecode/`.

## Supported artifacts

| Artifact | Purpose | Command |
| --- | --- | --- |
| Wheel | Normal Python installation | `python -m build --wheel` |
| Source distribution | Reproducible source release | `python -m build --sdist` |
| Local wheel smoke build | Quick packaging check without extra tools | `python -m pip wheel . --no-deps -w dist` |
| Windows x64 installer | Self-contained desktop installation | `python -X utf8 packaging/windows/build_windows_installer.py` |

Generated files under `dist/`, `build/`, and `*.egg-info` are ignored and must not be committed.

## Package contents

The wheel must include:

- `voicecode` Python modules and `voicecode.extensions`;
- `voicecode/static/index.html`;
- `voicecode/static/css/*.css`;
- `voicecode/static/js/*.js`, including ES Module bootstrap files and the Minesweeper-only `games.js`;
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
|-- cache/
|   |-- huggingface/
|   |-- transformers/
|   `-- pip/
|-- dependencies/       # in-app isolated packages in packaged runtime mode
|-- models/             # faster-whisper model cache
`-- python/             # embedded CPython + pip used by dependency installs
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

VoiceCode maintains a PyInstaller + Inno Setup Windows pipeline under `packaging/windows/`. Nuitka, MSI, DMG, AppImage, and code signing remain downstream release choices. A desktop bundle must:

1. include all packaged static assets and external JSON catalogs, including `games.js` for Minesweeper;
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

## Windows installer verification

The Windows builder downloads and validates embedded-Python bootstrap assets before PyInstaller, caches them under `build/windows/downloads/`, and retries interrupted downloads through an atomic `.part` file. After building, run `packaging/windows/verify_windows_installer.py` on a disposable Windows path. Release CI performs silent install, file/catalog/icon/Minesweeper-payload checks, embedded-pip execution, and uninstall before uploading the installer and `verification.json`. Interactive release validation must additionally cover startup PID/bind checks, UI rendering, repeat launch, cached-model readiness, transcription, and a physical microphone. See [WINDOWS_INSTALLER.md](WINDOWS_INSTALLER.md) and [RELEASE_VALIDATION_0.2.0.md](RELEASE_VALIDATION_0.2.0.md).

## Supply-chain artifacts

Tagged release CI creates SHA-256 checksums, a CycloneDX JSON SBOM, and GitHub build-provenance attestations. It installs the built wheel into a clean virtual environment and verifies packaged catalogs/onboarding assets before upload. In-app dependency catalog entries must use bounded package-index specs; mutable GitHub branches are not accepted.

## Shutdown and clipboard packaging

The Windows bundle includes the native icon, tray dependencies, GPU telemetry dependencies, and the final frozen-process exit guard. The clipboard bridge uses Win32 APIs and requires no additional package. Silent installer validation does not auto-launch the application.
