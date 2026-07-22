# Windows Packaging

The recommended Windows release flow lives in `packaging/installer/`.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\packaging\installer\build-installer.ps1
```

That flow builds a PyInstaller one-folder application and, when Inno Setup 6 is available, a standard installer that lets users choose the installation directory. The installer defaults to non-admin per-user installation and can elevate when users intentionally choose a protected directory.

## Installer output

```text
packaging\installer\Output\VoiceCode-0.1.0-windows-x86_64-setup.exe
```

The installer defaults to a per-user path:

```text
%LOCALAPPDATA%\Programs\VoiceCode
```

The installed app keeps bundled dependencies under the selected folder and redirects future model/cache downloads to:

```text
<install-dir>\runtime\cache
<install-dir>\runtime\models
```

## Wheel

```powershell
python -m pip wheel . --no-deps -w dist
```

## Optional tray support

Tray support is disabled by default. To try it in development:

```powershell
python -m pip install -e ".[tray]"
$env:VOICECODE_ENABLE_TRAY = "1"
python -m voicecode
```
