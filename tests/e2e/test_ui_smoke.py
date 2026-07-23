from __future__ import annotations

import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.request import urlopen

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("VOICECODE_RUN_E2E") != "1",
    reason="Set VOICECODE_RUN_E2E=1 and install the e2e extra.",
)


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def test_first_start_ui_loads_external_catalog_and_has_no_console_errors(tmp_path):
    playwright = pytest.importorskip("playwright.sync_api")
    port = _free_port()
    env = os.environ.copy()
    env.update(
        {
            "PORT": str(port),
            "VOICECODE_SKIP_MODEL_LOAD": "1",
            "VOICECODE_CONFIG_FILE": str(tmp_path / "config.json"),
            "VOICECODE_DEP_DIR": str(tmp_path / "dependencies"),
            "VOICECODE_MODEL_DIR": str(tmp_path / "models"),
            "PYTHONUTF8": "1",
        }
    )
    source_dir = str(Path(__file__).resolve().parents[2] / "src")
    env["PYTHONPATH"] = os.pathsep.join(filter(None, (source_dir, env.get("PYTHONPATH"))))
    process = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "from voicecode.app import start_server; start_server()",
        ],
        env=env,
        cwd=Path(__file__).resolve().parents[2],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            try:
                with urlopen(f"http://127.0.0.1:{port}/health", timeout=1) as response:
                    if response.status == 200:
                        break
            except Exception:
                time.sleep(0.2)
        else:
            raise AssertionError("VoiceCode test server did not start.")

        errors: list[str] = []
        with playwright.sync_playwright() as runtime:
            browser = runtime.chromium.launch()
            page = browser.new_page()
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(f"http://127.0.0.1:{port}/", wait_until="networkidle")
            page.locator("#onboarding-overlay.show").wait_for(state="visible")
            assert page.locator("#onboarding-step-title").inner_text()
            assert page.locator("#error-modal.show").count() == 0
            assert page.evaluate("document.activeElement?.id") == "onboarding-step-title"
            assert page.locator("#sidebar-version").inner_text().startswith("VoiceCode ")
            catalog = page.request.get(f"http://127.0.0.1:{port}/static/i18n/en.json")
            assert catalog.ok
            assert isinstance(catalog.json(), dict)
            assert errors == []
            browser.close()
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
