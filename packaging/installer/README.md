# VoiceCode Windows Installer Packaging

This folder contains the release packaging project for a user-friendly Windows installer.

## What this produces

- A PyInstaller **one-folder** desktop app at `packaging/installer/dist/VoiceCode/`.
- An optional Inno Setup installer at `packaging/installer/Output/VoiceCodeSetup-0.1.0.exe`.
- The installer lets users choose the installation path.
- The default path is per-user: `%LOCALAPPDATA%\Programs\VoiceCode`, so normal users can run it without admin rights.
- Python, native libraries, and Python package dependencies are bundled inside the install folder.
- Future Hugging Face / faster-whisper model downloads are redirected to `<install-dir>\runtime\cache` and `<install-dir>\runtime\models` by the packaged launcher.

## Prerequisites

```powershell
python -m pip install -e ".[build]"
```

To build the `.exe` installer, install [Inno Setup 6](https://jrsoftware.org/isinfo.php).

## Build

From the repository root:

```powershell
.\packaging\installer\build-installer.ps1
```

If Inno Setup is not installed, build only the one-folder app:

```powershell
.\packaging\installer\build-installer.ps1 -SkipInno
```

## Release testing checklist

1. Install to the default path.
2. Install to a custom user-writable path.
3. Start VoiceCode and verify the HTTP server binds only to `127.0.0.1`.
4. Trigger first model load/download and verify cache files appear under `<install-dir>\runtime`.
5. Verify uninstall removes the app folder. If users downloaded models, they may choose to delete the remaining runtime folder manually.
6. Test on a clean Windows VM with microphone access.
