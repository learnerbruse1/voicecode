# PyInstaller one-folder build for the Windows installer.
# Usage from repository root:
#   pyinstaller packaging/installer/voicecode-onedir.spec --noconfirm --distpath packaging/installer/dist --workpath packaging/installer/build

from pathlib import Path

from PyInstaller.utils.hooks import collect_all

ROOT = Path.cwd()
APP_NAME = "VoiceCode"

binaries = []
datas = [(str(ROOT / "src" / "voicecode" / "static"), "voicecode/static")]
hiddenimports = []

# Collect package data, metadata, dynamic libraries, and hidden imports for the bundled app.
# This keeps Python dependencies inside the installed folder instead of requiring users to
# install Python packages manually.
for package_name in [
    "ctranslate2",
    "faster_whisper",
    "flask",
    "huggingface_hub",
    "numpy",
    "psutil",
    "pynput",
    "sounddevice",
    "tokenizers",
    "waitress",
    "webview",
]:
    package_datas, package_binaries, package_hiddenimports = collect_all(package_name)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hiddenimports

a = Analysis(
    [str(ROOT / "src" / "voicecode" / "__main__.py")],
    pathex=[str(ROOT / "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "mypy", "ruff", "pre_commit"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name=APP_NAME,
)
