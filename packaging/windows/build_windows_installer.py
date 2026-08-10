"""Build the Windows x64 installer for VoiceCode.

The resulting installer is self-contained: the PyInstaller application, its core Python
packages, and a small embedded CPython + pip runtime are all copied below the selected
installation directory.  Models, Hugging Face caches, and optional packages installed by
VoiceCode are kept below ``<install-dir>/runtime``.

Requirements on the release machine:
* CPython 3.12 x64 with the project's ``runtime`` and ``dev`` extras installed.
* PyInstaller (included by the ``dev`` extra).
* Inno Setup 6 (``ISCC.exe``), configured through ``ISCC`` or installed normally.
"""

from __future__ import annotations

import argparse
import json
import platform
import re
import shutil
import subprocess
import sys
import time
import zipfile
from collections.abc import Iterable
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[2]
WINDOWS_DIR = Path(__file__).resolve().parent
PACKAGE_BUILD_DIR = ROOT / "build" / "windows"
DOWNLOAD_CACHE_DIR = PACKAGE_BUILD_DIR / "downloads"
PYINSTALLER_WORK_DIR = PACKAGE_BUILD_DIR / "work"
PYINSTALLER_SPEC_DIR = PACKAGE_BUILD_DIR / "spec"
PYINSTALLER_DIST_DIR = ROOT / "dist" / "windows" / "app"
INSTALLER_DIST_DIR = ROOT / "dist" / "windows" / "installer"
APP_NAME = "VoiceCode"
ICON_FILE = ROOT / "assets" / "voicecode-icon.ico"
APP_DIR = PYINSTALLER_DIST_DIR / APP_NAME
EMBEDDED_PYTHON_DIR = APP_DIR / "runtime" / "python"

CORE_PACKAGES = (
    "flask",
    "numpy",
    "requests",
    "webview",
    "pynput",
    "waitress",
    "psutil",
    "faster_whisper",
    "ctranslate2",
    "sounddevice",
    "pynvml",
    "pystray",
    "PIL",
)

NVIDIA_RUNTIME_WHEELS = {
    "nvidia-cublas-cu12": "12.4.5.8",
    "nvidia-cuda-runtime-cu12": "12.4.127",
}
REQUIRED_NVIDIA_DLLS = ("cublas64_12.dll", "cublasLt64_12.dll", "cudart64_12.dll")
NVIDIA_DLL_DIR = APP_DIR / "_internal" / "nvidia" / "bin"


def version() -> str:
    metadata_source = (ROOT / "src" / "voicecode" / "__init__.py").read_text(encoding="utf-8")
    match = re.search(r'^__version__\s*=\s*["\']([^"\']+)["\']', metadata_source, re.MULTILINE)
    if not match:
        raise RuntimeError("Unable to read the VoiceCode version from src/voicecode/__init__.py.")
    return match.group(1)


def require_windows_x64() -> None:
    if sys.platform != "win32":
        raise RuntimeError("Windows installers must be built on Windows.")
    if platform.architecture()[0] != "64bit":
        raise RuntimeError("Build the Windows installer with 64-bit CPython.")
    if sys.version_info[:2] != (3, 12):
        raise RuntimeError("Use CPython 3.12 x64 so the embedded Python matches the bundle.")


def require_modules(modules: Iterable[str]) -> None:
    missing: list[str] = []
    for module in modules:
        try:
            __import__(module)
        except Exception:
            missing.append(module)
    if missing:
        raise RuntimeError(
            "The release environment is missing bundled runtime modules: "
            + ", ".join(missing)
            + ". Install the project's runtime extra before building."
        )


def remove_tree(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)


def download(
    url: str,
    destination: Path,
    *,
    attempts: int = 3,
    timeout_seconds: int = 300,
) -> None:
    """Download a release prerequisite atomically with bounded retries."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(f"{destination.name}.part")
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        partial.unlink(missing_ok=True)
        print(f"Downloading {url} (attempt {attempt}/{attempts})")
        try:
            with (
                urlopen(  # nosec B310: fixed official release URLs
                    url, timeout=timeout_seconds
                ) as response,
                partial.open("wb") as output,
            ):
                shutil.copyfileobj(response, output, length=1024 * 1024)
            if partial.stat().st_size == 0:
                raise RuntimeError(f"Downloaded file is empty: {url}")
            partial.replace(destination)
            return
        except Exception as exc:
            last_error = exc
            partial.unlink(missing_ok=True)
            if attempt < attempts:
                delay = attempt * 2
                print(f"Download failed: {exc}. Retrying in {delay}s.")
                time.sleep(delay)
    raise RuntimeError(f"Unable to download {url} after {attempts} attempts: {last_error}")


def _pypi_wheel_url(package: str, version: str) -> str:
    """Resolve the Windows x64 wheel URL for a pinned NVIDIA runtime package."""
    metadata_url = f"https://pypi.org/pypi/{package}/{version}/json"
    with urlopen(metadata_url, timeout=60) as response:
        payload = json.load(response)
    prefix = package.replace("-", "_") + "-"
    for item in payload.get("urls", []):
        filename = item.get("filename", "")
        if filename.startswith(prefix) and filename.endswith("win_amd64.whl"):
            return str(item["url"])
    raise RuntimeError(f"No Windows x64 wheel found for {package}=={version}.")


def bundle_nvidia_runtime() -> None:
    """Bundle the CUDA libraries CTranslate2 loads at GPU inference time.

    CTranslate2's Windows wheel delay-loads cuBLAS and the CUDA runtime
    (cublas64_12.dll, cublasLt64_12.dll, cudart64_12.dll) only when GPU
    inference starts. Those libraries are not part of the wheel, so without
    them GPU mode fails on any machine without a system-wide CUDA install.
    Bundle the matching CUDA 12.4 wheels so GPU dictation works out of the box.
    """
    NVIDIA_DLL_DIR.mkdir(parents=True, exist_ok=True)
    wheel_dir = DOWNLOAD_CACHE_DIR / "nvidia"
    wheel_dir.mkdir(parents=True, exist_ok=True)
    for package, version in NVIDIA_RUNTIME_WHEELS.items():
        wheel = wheel_dir / f"{package.replace('-', '_')}-{version}-py3-none-win_amd64.whl"
        if not wheel.is_file():
            download(_pypi_wheel_url(package, version), wheel)
        if not zipfile.is_zipfile(wheel):
            raise RuntimeError(f"NVIDIA runtime wheel is invalid: {wheel}")
        with zipfile.ZipFile(wheel) as archive:
            for member in archive.namelist():
                name = Path(member).name
                if name in REQUIRED_NVIDIA_DLLS:
                    destination = NVIDIA_DLL_DIR / name
                    if not destination.is_file():
                        with archive.open(member) as source, destination.open("wb") as output:
                            shutil.copyfileobj(source, output)
    missing = [name for name in REQUIRED_NVIDIA_DLLS if not (NVIDIA_DLL_DIR / name).is_file()]
    if missing:
        raise RuntimeError("Bundled NVIDIA CUDA runtime is incomplete: " + ", ".join(missing))
    total_mb = sum((NVIDIA_DLL_DIR / name).stat().st_size for name in REQUIRED_NVIDIA_DLLS) / (
        1024 * 1024
    )
    print(f"Bundled NVIDIA CUDA runtime ({total_mb:.1f} MB): " + ", ".join(REQUIRED_NVIDIA_DLLS))


def embedded_python_filename() -> str:
    return f"python-{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}-embed-amd64.zip"


def ensure_embedded_python_assets() -> tuple[Path, Path]:
    """Download and cache embedded-Python bootstrap files before the expensive app build."""
    DOWNLOAD_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    archive = DOWNLOAD_CACHE_DIR / embedded_python_filename()
    version_string = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    if archive.exists() and not zipfile.is_zipfile(archive):
        archive.unlink()
    if not archive.exists():
        download(f"https://www.python.org/ftp/python/{version_string}/{archive.name}", archive)
    if not zipfile.is_zipfile(archive):
        raise RuntimeError(f"Embedded Python archive is invalid: {archive}")

    get_pip = DOWNLOAD_CACHE_DIR / "get-pip.py"
    if get_pip.exists() and get_pip.stat().st_size < 100_000:
        get_pip.unlink()
    if not get_pip.exists():
        download("https://bootstrap.pypa.io/get-pip.py", get_pip)
    return archive, get_pip


def prepare_embedded_python(archive: Path, get_pip: Path) -> None:
    remove_tree(EMBEDDED_PYTHON_DIR)
    EMBEDDED_PYTHON_DIR.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as contents:
        contents.extractall(EMBEDDED_PYTHON_DIR)

    pth_file = EMBEDDED_PYTHON_DIR / f"python{sys.version_info.major}{sys.version_info.minor}._pth"
    if not pth_file.is_file():
        raise RuntimeError(f"Embedded Python path file was not found: {pth_file}")
    pth_file.write_text(
        f".\npython{sys.version_info.major}{sys.version_info.minor}.zip\n"
        "Lib\\site-packages\nimport site\n",
        encoding="utf-8",
        newline="\n",
    )

    python = EMBEDDED_PYTHON_DIR / "python.exe"
    subprocess.run(
        [str(python), str(get_pip), "--no-warn-script-location"],
        check=True,
        cwd=EMBEDDED_PYTHON_DIR,
    )
    subprocess.run([str(python), "-m", "pip", "--version"], check=True)


def verify_minesweeper_static_assets(static_dir: Path) -> None:
    """Reject packaged UI payloads that omit Minesweeper or retain removed card-game code."""
    assets = {
        "index": static_dir / "index.html",
        "script": static_dir / "js" / "games.js",
        "styles": static_dir / "css" / "app.css",
    }
    missing = [name for name, path in assets.items() if not path.is_file()]
    if missing:
        raise RuntimeError("Packaged Minesweeper assets are missing: " + ", ".join(missing))

    payload = "\n".join(path.read_text(encoding="utf-8") for path in assets.values()).lower()
    required_markers = ("game-minesweeper", "newminesweeper", "mine-board")
    missing_markers = [marker for marker in required_markers if marker not in payload]
    if missing_markers:
        raise RuntimeError(
            "Packaged Minesweeper assets are incomplete: " + ", ".join(missing_markers)
        )

    removed_markers = ("solitaire", "card-slot", "game-tabs")
    retained_markers = [marker for marker in removed_markers if marker in payload]
    if retained_markers:
        raise RuntimeError(
            "Packaged UI still contains removed card-game content: " + ", ".join(retained_markers)
        )


def build_app() -> None:
    remove_tree(PYINSTALLER_WORK_DIR)
    remove_tree(PYINSTALLER_SPEC_DIR)
    remove_tree(PYINSTALLER_DIST_DIR)
    PYINSTALLER_WORK_DIR.mkdir(parents=True, exist_ok=True)
    PYINSTALLER_SPEC_DIR.mkdir(parents=True, exist_ok=True)
    PYINSTALLER_DIST_DIR.mkdir(parents=True, exist_ok=True)
    if not ICON_FILE.is_file():
        raise RuntimeError(f"VoiceCode icon is missing: {ICON_FILE}")
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--onedir",
        "--name",
        APP_NAME,
        "--icon",
        str(ICON_FILE),
        "--paths",
        str(ROOT / "src"),
        "--distpath",
        str(PYINSTALLER_DIST_DIR),
        "--workpath",
        str(PYINSTALLER_WORK_DIR),
        "--specpath",
        str(PYINSTALLER_SPEC_DIR),
        "--runtime-hook",
        str(WINDOWS_DIR / "runtime_hook.py"),
        "--add-data",
        f"{ROOT / 'src' / 'voicecode' / 'static'};voicecode/static",
    ]
    for package in CORE_PACKAGES:
        command.extend(("--collect-all", package))
    command.extend(
        (
            "--hidden-import",
            "webview.platforms.winforms",
            "--hidden-import",
            "webview.platforms.edgechromium",
            str(WINDOWS_DIR / "launcher.py"),
        )
    )
    subprocess.run(command, check=True, cwd=ROOT)
    if not (APP_DIR / f"{APP_NAME}.exe").is_file():
        raise RuntimeError("PyInstaller did not produce VoiceCode.exe.")
    packaged_index = APP_DIR / "_internal" / "voicecode" / "static" / "index.html"
    if not packaged_index.is_file():
        raise RuntimeError(f"PyInstaller did not include the frontend assets: {packaged_index}")
    verify_minesweeper_static_assets(packaged_index.parent)
    for name in ("LICENSE", "README.md", "README_zh.md", "README_ja.md"):
        shutil.copy2(ROOT / name, APP_DIR / name)


def locate_iscc(configured: str | None) -> Path:
    candidates = [
        configured,
        shutil.which("ISCC.exe"),
        str(Path.home() / "AppData" / "Local" / "Programs" / "Inno Setup 6" / "ISCC.exe"),
        r"C:\\Program Files (x86)\\Inno Setup 6\\ISCC.exe",
        r"C:\\Program Files\\Inno Setup 6\\ISCC.exe",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return Path(candidate)
    raise RuntimeError(
        "Inno Setup 6 was not found. Install it or set ISCC to the full path of ISCC.exe."
    )


def build_installer(iscc: Path) -> Path:
    remove_tree(INSTALLER_DIST_DIR)
    INSTALLER_DIST_DIR.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            str(iscc),
            f"/DSourceDir={APP_DIR}",
            f"/DOutputDir={INSTALLER_DIST_DIR}",
            f"/DAppVersion={version()}",
            f"/DIconFile={ICON_FILE}",
            str(WINDOWS_DIR / "VoiceCode.iss"),
        ],
        check=True,
        cwd=ROOT,
    )
    installer = INSTALLER_DIST_DIR / f"VoiceCode-v{version()}-Windows-x64-Setup.exe"
    if not installer.is_file():
        raise RuntimeError(f"Inno Setup did not produce {installer.name}.")
    return installer


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-installer",
        action="store_true",
        help="Build only the PyInstaller application directory.",
    )
    parser.add_argument("--iscc", help="Path to the Inno Setup compiler (ISCC.exe).")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    require_windows_x64()
    require_modules(CORE_PACKAGES)
    archive, get_pip = ensure_embedded_python_assets()
    build_app()
    bundle_nvidia_runtime()
    prepare_embedded_python(archive, get_pip)
    runtime = APP_DIR / "runtime"
    for directory in (runtime / "dependencies", runtime / "models", runtime / "cache"):
        directory.mkdir(parents=True, exist_ok=True)
    if args.skip_installer:
        print(f"Built application directory: {APP_DIR}")
        return 0
    installer = build_installer(locate_iscc(args.iscc))
    print(f"Built installer: {installer}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
