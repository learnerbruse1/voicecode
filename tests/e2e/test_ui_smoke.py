from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
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


def _start_server(tmp_path, *, complete_onboarding: bool = False) -> tuple[int, subprocess.Popen]:
    if complete_onboarding:
        config_path = tmp_path / "config.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(
            json.dumps(
                {
                    "config_version": 2,
                    "onboarding": {
                        "completed": True,
                        "completed_version": "0.2.0",
                        "skipped": False,
                    },
                    "ui_language": "en",
                }
            ),
            encoding="utf-8",
        )
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
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        try:
            with urlopen(f"http://127.0.0.1:{port}/health", timeout=1) as response:
                if response.status == 200:
                    return port, process
        except Exception:
            time.sleep(0.2)
    process.terminate()
    process.wait(timeout=10)
    raise AssertionError("VoiceCode test server did not start.")


def _assert_setting_round_trip(page, selector: str, value: str) -> None:
    page.click("button[data-view='settings']")
    page.locator("#view-settings.active").wait_for(state="visible")
    page.select_option(selector, value)
    page.wait_for_timeout(500)
    page.reload(wait_until="networkidle")
    page.click("button[data-view='settings']")
    page.wait_for_function(
        f"() => document.getElementById('{selector.lstrip('#')}')?.value === '{value}'",
        timeout=5000,
    )


def test_idle_status_polling_is_not_every_three_seconds(tmp_path):
    playwright = pytest.importorskip("playwright.sync_api")
    port, process = _start_server(tmp_path)
    try:
        with playwright.sync_playwright() as runtime:
            browser = runtime.chromium.launch()
            page = browser.new_page()
            status_times: list[float] = []

            def record(request):
                if request.url.endswith("/status"):
                    status_times.append(time.monotonic())

            page.on("request", record)
            page.goto(f"http://127.0.0.1:{port}/", wait_until="networkidle")
            page.wait_for_timeout(13000)
            gaps = [b - a for a, b in zip(status_times, status_times[1:], strict=False)]
            assert gaps, "expected at least two /status requests"
            assert max(gaps) >= 8.0, f"idle polling too frequent: {gaps}"
            browser.close()
    finally:
        process.terminate()
        process.wait(timeout=10)


def test_settings_round_trip_persists_decode_preset(tmp_path):
    playwright = pytest.importorskip("playwright.sync_api")
    port, process = _start_server(tmp_path, complete_onboarding=True)
    try:
        with playwright.sync_playwright() as runtime:
            browser = runtime.chromium.launch()
            page = browser.new_page()
            page.goto(f"http://127.0.0.1:{port}/", wait_until="networkidle")
            _assert_setting_round_trip(page, "#decode-preset", "fast")
            browser.close()
    finally:
        process.terminate()
        process.wait(timeout=10)


def test_settings_round_trip_persists_partial_preview(tmp_path):
    playwright = pytest.importorskip("playwright.sync_api")
    port, process = _start_server(tmp_path, complete_onboarding=True)
    try:
        with playwright.sync_playwright() as runtime:
            browser = runtime.chromium.launch()
            page = browser.new_page()
            page.goto(f"http://127.0.0.1:{port}/", wait_until="networkidle")
            _assert_setting_round_trip(page, "#partial-results", "false")
            browser.close()
    finally:
        process.terminate()
        process.wait(timeout=10)


def test_first_start_ui_loads_external_catalog_and_has_no_console_errors(tmp_path):
    playwright = pytest.importorskip("playwright.sync_api")
    port, process = _start_server(tmp_path)
    try:
        errors: list[str] = []
        console_errors: list[str] = []
        http_errors: list[str] = []
        with playwright.sync_playwright() as runtime:
            browser = runtime.chromium.launch()
            page = browser.new_page()
            missing_dependency = {
                "id": "faster-whisper",
                "name": "Whisper runtime",
                "description": "Speech recognition runtime.",
                "notes": "Required for transcription.",
                "installed": False,
                "installed_in_voice_dep": False,
                "missing_modules": ["faster_whisper", "ctranslate2"],
                "feature_ids": [],
                "github_preferred": False,
            }
            page.route(
                f"http://127.0.0.1:{port}/dependencies",
                lambda route: route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps(
                        {
                            "install_dir": str(tmp_path / "dependencies"),
                            "dependencies": [missing_dependency],
                            "missing": [missing_dependency],
                            "action_required_missing": [missing_dependency],
                        }
                    ),
                ),
            )
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on(
                "console",
                lambda message: (
                    console_errors.append(message.text) if message.type == "error" else None
                ),
            )
            page.on(
                "response",
                lambda response: (
                    http_errors.append(
                        f"{response.request.method} {response.status} {response.url}"
                    )
                    if response.status >= 400
                    else None
                ),
            )
            page.goto(f"http://127.0.0.1:{port}/", wait_until="networkidle")
            page.locator("#onboarding-overlay.show").wait_for(state="visible")
            assert page.locator("#onboarding-step-title").inner_text()
            assert page.locator("#error-modal.show").count() == 0
            assert page.evaluate("document.activeElement?.id") == "onboarding-step-title"
            assert page.locator("#sidebar-version").inner_text().startswith("VoiceCode ")
            assert page.locator(".app-shell").get_attribute("inert") == ""
            assert page.locator("body").evaluate(
                "element => element.classList.contains('dialog-open')"
            )
            for language, expected_title in (
                ("zh", "界面和转写语言"),
                ("ja", "表示言語と文字起こし言語"),
                ("en", "Interface and transcription language"),
            ):
                page.locator("#onboarding-ui-language").select_option(language)
                page.locator("#onboarding-step-title").filter(has_text=expected_title).wait_for()
                assert page.locator("#onboarding-ui-language").input_value() == language

            for language in ("en", "zh", "ja"):
                catalog = page.request.get(f"http://127.0.0.1:{port}/static/i18n/{language}.json")
                assert catalog.ok
                assert isinstance(catalog.json(), dict)
                assert all("??" not in value for value in catalog.json().values())

            page.evaluate("showError('Synthetic error', 'Dialog stack regression')")
            page.locator("#error-modal.show").wait_for(state="visible")
            assert page.evaluate("document.activeElement?.id") == "error-close"
            assert page.locator(".app-shell").get_attribute("inert") == ""
            assert page.locator("body").evaluate(
                "element => element.classList.contains('dialog-open')"
            )
            page.evaluate("closeError()")
            page.locator("#error-modal").wait_for(state="hidden")
            assert page.locator("#onboarding-overlay.show").count() == 1
            assert page.evaluate("document.activeElement?.id") == "onboarding-step-title"
            assert page.locator(".app-shell").get_attribute("inert") == ""
            assert page.locator("body").evaluate(
                "element => element.classList.contains('dialog-open')"
            )

            page.locator("#onboarding-skip").click()
            page.locator("#onboarding-overlay").wait_for(state="hidden")
            page.locator("#error-modal.show").wait_for(state="visible")
            assert page.locator("#error-title").inner_text() in {
                "Missing dependencies",
                "Whisper model unavailable",
            }
            assert page.locator("#error-message").inner_text()
            assert page.evaluate("document.activeElement?.id") == "error-close"
            assert page.locator(".app-shell").get_attribute("inert") == ""
            assert page.locator("body").evaluate(
                "element => element.classList.contains('dialog-open')"
            )
            page.locator("#error-close").click()
            page.locator("#error-modal").wait_for(state="hidden")
            assert page.locator(".app-shell").get_attribute("inert") is None
            assert not page.locator("body").evaluate(
                "element => element.classList.contains('dialog-open')"
            )

            view_expectations = {
                "home": None,
                "settings": None,
                "models": ".managed-model-card",
                "extensions": ".extension-card",
                "dependencies": ".dependency-card",
                "history": "#history-list",
                "diagnostics": "#diagnostics-output",
                "about": "#rerun-onboarding",
            }
            for view_name, content_selector in view_expectations.items():
                page.locator(f'.nav-item[data-view="{view_name}"]').click()
                page.locator(f"#view-{view_name}.active").wait_for(state="visible")
                assert page.locator(f'.nav-item.active[data-view="{view_name}"]').count() == 1
                if content_selector:
                    page.locator(content_selector).first.wait_for(state="visible")
                assert page.locator("#error-modal.show").count() == 0

            assert errors == []
            assert console_errors == [], http_errors
            assert http_errors == []
            browser.close()
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
