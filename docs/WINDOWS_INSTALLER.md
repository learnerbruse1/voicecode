# Windows Installer Build (v0.2.0)

VoiceCode ships a standard Windows x64 installer built from a PyInstaller **one-folder** bundle and wrapped by Inno Setup. The setup wizard always displays the destination page; the default is `%LOCALAPPDATA%\Programs\VoiceCode`, which is writable without administrator rights.

The v0.2.0 functional installer pass completed on **July 24, 2026**, and the Minesweeper-only payload was rebuilt and revalidated on **July 25, 2026**. See [RELEASE_VALIDATION_0.2.0.md](RELEASE_VALIDATION_0.2.0.md) for the tested artifact, environment, checks, and remaining signing gate.

## Installed layout

```text
VoiceCode/
  VoiceCode.exe
  _internal/                 # bundled application and core Python dependencies
  runtime/
    python/                  # embedded CPython + pip for optional dependency installs
    dependencies/            # packages installed later from the Dependencies screen
    models/                  # faster-whisper model downloads
    cache/                   # Hugging Face, transformer, and pip download caches
```

The packaged entry point automatically sets `VOICECODE_RUNTIME_DIR`, `VOICECODE_MODEL_DIR`, and `VOICECODE_DEP_DIR` to this `runtime` directory. Therefore the installation includes all core runtime packages, and every later model or optional package download remains beneath the user-selected installation folder. Configuration, history, and logs remain in the documented per-user configuration location.

The uninstaller removes files installed by Setup. Files created later by VoiceCode, including downloaded models and optional dependencies, are intentionally not registered as setup payloads and can remain below `runtime`. This allows a reinstall to reuse them. Users who want a complete removal must delete the remaining installation/runtime directory after uninstalling.

## Release-machine prerequisites

- Windows x64 with CPython **3.12 x64**.
- Project dependencies installed with `python -m pip install -e ".[runtime,dev]"`.
- [Inno Setup 6](https://jrsoftware.org/isinfo.php) installed, or `ISCC` set to its `ISCC.exe`.

## Build

```powershell
python -X utf8 tools/generate_icon.py
python -X utf8 packaging/windows/build_windows_installer.py
```

The installer is written to `dist/windows/installer/`. For diagnosing only the PyInstaller layout without Inno Setup, use:

```powershell
python -X utf8 packaging/windows/build_windows_installer.py --skip-installer
```

The build downloads the exact CPython 3.12 embedded ZIP and `get-pip.py` **before** the expensive PyInstaller stage. Files are cached under `build/windows/downloads/`; downloads use a `.part` file, atomic replacement, validation, a five-minute socket timeout, and bounded retries. The PyInstaller `work` and `spec` directories are cleaned without deleting this download cache. After bundling, the build requires the Minesweeper index, `games.js`, and board styles, and rejects removed card-game markers.

Do not publish an unpacked development directory or a wheel as the desktop installation. Publish only the generated `VoiceCode-v<version>-Windows-x64-Setup.exe` after signing it and running the release checks.

## Automated installer smoke

Run on a disposable Windows machine or clean CI runner:

```powershell
python -X utf8 packaging/windows/verify_windows_installer.py `
  --installer dist/windows/installer/VoiceCode-v0.2.0-Windows-x64-Setup.exe `
  --install-dir "$env:TEMP\VoiceCode-installer-smoke" `
  --version 0.2.0 `
  --skip-launch `
  --uninstall `
  --report dist/windows/installer/verification.json
```

The verifier checks the installed executable, license/README files, packaged Minesweeper-only UI (`games.js`, board markup, and no removed card-game markers), PNG icon, all three JSON catalogs, writable runtime directories, embedded Python/pip, and silent uninstall. Omit `--skip-launch` on an interactive desktop to additionally launch `VoiceCode.exe` and verify `/health`, `/status`, the icon, and language resources.

`--uninstall` must only be used for a disposable installation path. The installer uses a stable Inno Setup AppId, so do not run destructive installer smoke tests alongside a production installation for the same Windows user.

## Release-critical manual checks

Before publishing, also verify:

- install and repair-install to a custom writable path;
- first-start guide and full `en -> zh -> ja -> en` language round trip;
- the Minesweeper page opens in all three languages and offers Beginner, Intermediate, and Expert without any card-game view;
- `/health` reports the installed process PID and the listener is only `127.0.0.1:7788`;
- repeat launch leaves exactly one running application instance;
- a cached/downloaded model reaches `ready` and a real transcription succeeds;
- a physical microphone recording succeeds;
- uninstall removes installed program files and handles retained runtime data as documented;
- the final public artifact has a valid timestamped Authenticode signature.

The build fails if the ICO asset or packaged `voicecode/static/index.html` is missing. Release CI now runs the non-GUI automated installer smoke before uploading the Windows artifact and its `verification.json` report.

## Installed-model download behavior

Packaged launches use the selected installation directory for model files and set conservative Hugging Face network defaults: Xet/CAS is disabled unless explicitly re-enabled, metadata timeout is 10 seconds, and file response timeout is 30 seconds. First launch waits for the onboarding model choice instead of automatically starting `base`; later launches load the model saved in `config.json`. Progress and structured failure details are available in both Settings and Models.

## Current validation expectations

Installer validation checks static assets, all three language catalogs, health PID ownership, embedded pip, and HTTP status. Model loading is disabled during installer smoke verification to avoid treating network availability as an installer result.
