# Windows Packaging

The recommended Windows release flow lives in `packaging/installer/`.

```powershell
.\packaging\installer\build-installer.ps1
```

That flow builds a PyInstaller one-folder application and, when Inno Setup 6 is available, a standard installer that lets users choose the installation directory.

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
