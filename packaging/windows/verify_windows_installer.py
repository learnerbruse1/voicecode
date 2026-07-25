"""Install and verify a VoiceCode Windows installer on a disposable test machine."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import time
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PORT = 7788
REQUIRED_FILES = (
    "VoiceCode.exe",
    "LICENSE",
    "README.md",
    "README_zh.md",
    "README_ja.md",
    "_internal/voicecode/static/index.html",
    "_internal/voicecode/static/voicecode-icon.png",
    "_internal/voicecode/static/i18n/en.json",
    "_internal/voicecode/static/i18n/zh.json",
    "_internal/voicecode/static/i18n/ja.json",
    "runtime/python/python.exe",
)


def run(command: list[str], *, timeout: int = 300) -> subprocess.CompletedProcess[str]:
    print("Running:", subprocess.list2cmdline(command))
    result = subprocess.run(
        command,
        check=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
    )
    if result.stdout:
        print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
    return result


def read_json(url: str, *, timeout: float = 10) -> dict[str, Any]:
    with urlopen(url, timeout=timeout) as response:  # nosec B310: fixed loopback URL
        if response.status != 200:
            raise RuntimeError(f"{url} returned HTTP {response.status}.")
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"{url} did not return a JSON object.")
    return payload


def wait_for_health(pid: int, port: int, timeout_seconds: int) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    url = f"http://127.0.0.1:{port}/health"
    last_error: BaseException | None = None
    while time.monotonic() < deadline:
        try:
            payload = read_json(url, timeout=2)
            if payload.get("pid") != pid:
                raise RuntimeError(
                    f"Health PID mismatch: expected {pid}, received {payload.get('pid')}."
                )
            return payload
        except (OSError, URLError, ValueError, RuntimeError) as exc:
            last_error = exc
        time.sleep(0.25)
    raise RuntimeError(f"VoiceCode did not become healthy: {last_error}")


def verify_layout(install_dir: Path) -> dict[str, Any]:
    missing = [name for name in REQUIRED_FILES if not (install_dir / name).is_file()]
    if missing:
        raise RuntimeError("Installed files are missing: " + ", ".join(missing))

    catalogs: dict[str, int] = {}
    for language in ("en", "zh", "ja"):
        catalog_path = (
            install_dir / "_internal" / "voicecode" / "static" / "i18n" / f"{language}.json"
        )
        payload = json.loads(catalog_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or not payload:
            raise RuntimeError(f"Catalog is empty or invalid: {catalog_path}")
        catalogs[language] = len(payload)

    icon = install_dir / "_internal" / "voicecode" / "static" / "voicecode-icon.png"
    if not icon.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"):
        raise RuntimeError(f"Installed icon is not a PNG file: {icon}")

    runtime_dirs = [install_dir / "runtime" / name for name in ("cache", "dependencies", "models")]
    missing_dirs = [str(path) for path in runtime_dirs if not path.is_dir()]
    if missing_dirs:
        raise RuntimeError("Runtime directories are missing: " + ", ".join(missing_dirs))

    pip_result = run(
        [str(install_dir / "runtime" / "python" / "python.exe"), "-m", "pip", "--version"],
        timeout=60,
    )
    return {
        "catalog_entries": catalogs,
        "embedded_pip": pip_result.stdout.strip(),
        "required_files": len(REQUIRED_FILES),
    }


def verify_http(port: int, version: str) -> dict[str, Any]:
    base_url = f"http://127.0.0.1:{port}"
    paths = (
        "/",
        "/status",
        "/static/voicecode-icon.png",
        "/static/i18n/en.json",
        "/static/i18n/zh.json",
        "/static/i18n/ja.json",
    )
    sizes: dict[str, int] = {}
    for path in paths:
        with urlopen(base_url + path, timeout=15) as response:  # nosec B310: fixed loopback URL
            body = response.read()
            if response.status != 200:
                raise RuntimeError(f"{path} returned HTTP {response.status}.")
            sizes[path] = len(body)
    status = read_json(base_url + "/status")
    if status.get("version") != version:
        raise RuntimeError(
            f"Installed version mismatch: expected {version}, received {status.get('version')}."
        )
    return {"response_bytes": sizes, "status": status}


def stop_process(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    subprocess.run(
        ["taskkill", "/PID", str(process.pid), "/T", "/F"],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        process.kill()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--installer", type=Path, required=True)
    parser.add_argument("--install-dir", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--skip-launch", action="store_true")
    parser.add_argument("--uninstall", action="store_true")
    parser.add_argument("--report", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if os.name != "nt":
        raise RuntimeError("Windows installer verification must run on Windows.")
    installer = args.installer.expanduser().resolve()
    install_dir = args.install_dir.expanduser().resolve()
    if not installer.is_file():
        raise RuntimeError(f"Installer was not found: {installer}")
    if install_dir.parent == install_dir:
        raise RuntimeError("Refusing to install into a filesystem root.")

    install_dir.parent.mkdir(parents=True, exist_ok=True)
    install_log = install_dir.parent / "voicecode-install.log"
    run(
        [
            str(installer),
            "/VERYSILENT",
            "/SUPPRESSMSGBOXES",
            "/NORESTART",
            "/SP-",
            f"/DIR={install_dir}",
            f"/LOG={install_log}",
        ],
        timeout=600,
    )

    report: dict[str, Any] = {
        "installer": str(installer),
        "install_dir": str(install_dir),
        "version": args.version,
        "layout": verify_layout(install_dir),
    }
    process: subprocess.Popen[bytes] | None = None
    try:
        if not args.skip_launch:
            launch_env = os.environ.copy()
            launch_env["VOICECODE_SKIP_MODEL_LOAD"] = "1"
            launch_env["VOICECODE_CONFIG_FILE"] = str(
                install_dir / "runtime" / "verify-config.json"
            )
            process = subprocess.Popen([str(install_dir / "VoiceCode.exe")], env=launch_env)
            report["health"] = wait_for_health(process.pid, args.port, 90)
            report["http"] = verify_http(args.port, args.version)
    finally:
        if process is not None:
            stop_process(process)

    if args.uninstall:
        uninstallers = sorted(install_dir.glob("unins*.exe"))
        if not uninstallers:
            raise RuntimeError(f"Uninstaller was not found below {install_dir}.")
        uninstall_log = install_dir.parent / "voicecode-uninstall.log"
        run(
            [
                str(uninstallers[0]),
                "/VERYSILENT",
                "/SUPPRESSMSGBOXES",
                "/NORESTART",
                f"/LOG={uninstall_log}",
            ],
            timeout=300,
        )
        if (install_dir / "VoiceCode.exe").exists():
            raise RuntimeError("VoiceCode.exe remained after uninstall.")
        report["uninstall"] = "passed"

    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    print(rendered)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
