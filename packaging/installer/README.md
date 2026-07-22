# VoiceCode Windows Installer Packaging

This folder contains the recommended Windows release packaging project.

## What this produces

- A PyInstaller **one-folder** desktop app at `packaging/installer/dist/VoiceCode/`.
- An Inno Setup installer at `packaging/installer/Output/VoiceCodeSetup-0.1.0.exe` when Inno Setup 6 is available.
- A standard Windows installer that lets users choose the installation directory.
- A per-user default installation path: `%LOCALAPPDATA%\Programs\VoiceCode`.
- Optional elevation when users intentionally choose a protected directory such as `Program Files`.
- Bundled Python runtime, Python packages, native libraries, and static UI files under the chosen install directory.
- Runtime directories for future model/cache downloads:
  - `<install-dir>\runtime\cache`
  - `<install-dir>\runtime\models`

The generated `dist/`, `build/`, and `Output/` folders are intentionally ignored by this directory's `.gitignore`.

## Prerequisites

```powershell
python -m pip install -e ".[build]"
```

To build the `.exe` installer, install [Inno Setup 6](https://jrsoftware.org/isinfo.php). The build script auto-detects common machine-wide and per-user install locations, or you can pass `-InnoSetupCompiler`.

## Build the installer

From the repository root:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\packaging\installer\build-installer.ps1
```

If Inno Setup is not installed, build only the one-folder app:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\packaging\installer\build-installer.ps1 -SkipInno
```

If Inno Setup is installed in a custom location:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\packaging\installer\build-installer.ps1 -InnoSetupCompiler "C:\Path\To\ISCC.exe"
```

## Output layout

```text
packaging\installer\dist\VoiceCode\
  VoiceCode.exe
  _internal\
  runtime\
    cache\
    models\

packaging\installer\Output\
  VoiceCodeSetup-0.1.0.exe
```

## Runtime/cache behavior

The packaged launcher calls `voicecode.runtime.configure_runtime_paths()` before importing the main desktop/server modules. In frozen builds it defaults to:

```text
<install-dir>\runtime
```

and sets Hugging Face / transformer cache variables with `setdefault` so future model downloads stay under the chosen install folder unless the user explicitly overrides them.

## Release testing checklist

1. Run the repository checks from `docs/DEVELOPMENT.md`.
2. Build from a clean tree or CI worker.
3. Install to the default path.
4. Install to a custom user-writable path.
5. Verify `VoiceCode.exe`, `_internal`, `runtime`, `runtime\cache`, and `runtime\models` exist in the chosen directory.
6. Launch VoiceCode and verify the HTTP server binds only to `127.0.0.1`.
7. Trigger first model load/download and verify cache files appear under `<install-dir>\runtime`.
8. Verify Start Menu and optional desktop shortcuts.
9. Verify uninstall removes installed application files.
10. Confirm malformed/non-object JSON API payloads are rejected with `400` and do not start recording or reload models.
11. Test on a clean Windows VM with microphone access before publishing.

## Current release-candidate validation

The latest local release validation completed successfully:

- `ruff format --check`
- `ruff check`
- `mypy`
- `pytest` (`35 passed`)
- `py_compile`
- wheel build
- PyInstaller one-folder build
- Inno Setup installer build
- custom-directory silent install/uninstall smoke test
