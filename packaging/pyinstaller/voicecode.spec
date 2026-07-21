# PyInstaller spec for VoiceCode.
# Usage from repository root:
#   python -m pip install -e ".[build]"
#   pyinstaller packaging/pyinstaller/voicecode.spec

from pathlib import Path

ROOT = Path.cwd()

a = Analysis(
    [str(ROOT / "src" / "voicecode" / "__main__.py")],
    pathex=[str(ROOT / "src")],
    binaries=[],
    datas=[(str(ROOT / "src" / "voicecode" / "static"), "voicecode/static")],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="VoiceCode",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)
