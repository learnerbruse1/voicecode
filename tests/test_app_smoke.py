import importlib
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import types

import numpy as np
import pytest


class DummyCT:
    @staticmethod
    def get_cuda_device_count():
        return 0


class DummyWhisperModel:
    fail_load = False

    def __init__(self, *args, **kwargs):
        if self.__class__.fail_load:
            raise RuntimeError("model load failed")
        self.args = args
        self.kwargs = kwargs

    def transcribe(self, audio, **kwargs):
        class Seg:
            text = "hello"

        class Info:
            language = "en"

        return [Seg()], Info()


class DummyStream:
    fail_start = False

    def __init__(self, *args, **kwargs):
        self.callback = kwargs.get("callback")

    def start(self):
        if self.__class__.fail_start:
            raise RuntimeError("audio device unavailable")
        if self.callback:
            self.callback(np.ones((4, 1), dtype=np.float32), 4, None, None)

    def stop(self):
        pass

    def close(self):
        pass


@pytest.fixture()
def app_module(monkeypatch):
    monkeypatch.setitem(sys.modules, "ctranslate2", DummyCT)
    faster_whisper = types.ModuleType("faster_whisper")
    faster_whisper.WhisperModel = DummyWhisperModel
    monkeypatch.setitem(sys.modules, "faster_whisper", faster_whisper)
    sounddevice = types.ModuleType("sounddevice")
    sounddevice.InputStream = DummyStream
    sounddevice.query_devices = lambda: [
        {"name": "Dummy Microphone", "max_input_channels": 1, "default_samplerate": 16000.0},
        {"name": "Dummy Speaker", "max_input_channels": 0, "default_samplerate": 48000.0},
    ]
    sounddevice.default = types.SimpleNamespace(device=(0, None))
    monkeypatch.setitem(sys.modules, "sounddevice", sounddevice)

    sys.modules.pop("app", None)
    module = importlib.import_module("app")
    module.CONFIG_FILE = os.path.join(tempfile.mkdtemp(), "config.json")
    module.model = DummyWhisperModel("base", device="cpu", compute_type="int8")
    module._set_model_state("ready")
    DummyStream.fail_start = False
    DummyWhisperModel.fail_load = False
    yield module
    sys.modules.pop("app", None)


@pytest.fixture()
def client(app_module):
    return app_module.app.test_client()


def test_config_post_handles_empty_and_rejects_unknown_keys(client):
    response = client.post("/config")
    assert response.status_code == 200
    body = response.get_json()
    assert body["model"] == "base"
    assert body["ui_language"] == "en"

    response = client.post("/config", json={"unknown": 1})
    assert response.status_code == 400
    assert "Unknown config keys" in response.get_json()["error"]


def test_reload_model_validates_input(client):
    response = client.post("/reload_model", json={"model": "bad-model"})
    assert response.status_code == 400
    assert response.get_json()["error"] == "Unsupported model: bad-model"


def test_record_start_failure_does_not_leave_recorder_active(client, app_module):
    DummyStream.fail_start = True
    response = client.post("/record/start", json={"language": "en"})

    assert response.status_code == 503
    assert "Failed to start recording" in response.get_json()["error"]
    assert app_module._recorder.is_recording() is False


def test_record_stop_transcribes_with_dummy_audio(client):
    response = client.post("/record/start", json={"language": "auto"})
    assert response.status_code == 200

    response = client.post("/record/stop", json={"language": "en"})
    assert response.status_code == 200
    assert response.get_json() == {"language": "en", "text": "hello"}


def test_record_cancel_clears_pending_audio_and_stop_is_empty(client):
    response = client.post("/record/start", json={"language": "auto"})
    assert response.status_code == 200

    response = client.post("/record/cancel")
    assert response.status_code == 200
    assert response.get_json()["status"] == "cancelled"

    response = client.post("/record/stop", json={"language": "en"})
    assert response.status_code == 200
    assert response.get_json() == {"language": "en", "text": ""}


def test_record_start_is_idempotent_while_already_recording(client, app_module):
    first = client.post("/record/start", json={"language": "auto"})
    assert first.status_code == 200
    assert first.get_json() == {"status": "recording", "started": True}

    second = client.post("/record/start", json={"language": "auto"})
    assert second.status_code == 200
    assert second.get_json() == {"status": "recording", "started": False}
    assert app_module._recorder.is_recording() is True

    client.post("/record/cancel")


def test_save_config_creates_parent_directory(tmp_path, app_module):
    app_module.CONFIG_FILE = str(tmp_path / "nested" / "config.json")

    app_module.save_config(app_module.DEFAULT_CONFIG)

    assert (tmp_path / "nested" / "config.json").is_file()


def test_package_launcher_and_static_asset_are_importable():
    import importlib.resources as resources

    import voicecode
    import voicecode.__main__ as launcher

    assert voicecode.__version__ == "0.1.0"
    assert callable(launcher.main)
    static_root = resources.files("voicecode").joinpath("static")
    assert static_root.joinpath("index.html").is_file()
    assert static_root.joinpath("css", "app.css").is_file()
    for script in [
        "i18n.js",
        "dom.js",
        "modal.js",
        "api.js",
        "config.js",
        "hotkey.js",
        "settings.js",
        "recorder.js",
        "history.js",
        "status.js",
        "app.js",
    ]:
        assert static_root.joinpath("js", script).is_file()


def test_runtime_paths_keep_download_caches_under_runtime_dir(tmp_path, monkeypatch):
    from voicecode.runtime import configure_runtime_paths

    for name in [
        "VOICECODE_RUNTIME_DIR",
        "VOICECODE_MODEL_DIR",
        "HF_HOME",
        "HF_HUB_CACHE",
        "HUGGINGFACE_HUB_CACHE",
        "TRANSFORMERS_CACHE",
        "XDG_CACHE_HOME",
    ]:
        monkeypatch.delenv(name, raising=False)

    runtime_dir = configure_runtime_paths(tmp_path / "install" / "runtime")

    assert runtime_dir == (tmp_path / "install" / "runtime").resolve()
    for name in [
        "VOICECODE_MODEL_DIR",
        "HF_HOME",
        "HF_HUB_CACHE",
        "HUGGINGFACE_HUB_CACHE",
        "TRANSFORMERS_CACHE",
        "XDG_CACHE_HOME",
    ]:
        assert Path(os.environ[name]).is_relative_to(runtime_dir)
        assert Path(os.environ[name]).exists()


def test_root_wrappers_delegate_to_package_modules():
    import app as root_app
    import main as root_main
    import voicecode.app as package_app
    import voicecode.main as package_main

    assert root_app is package_app
    assert sys.modules["app"] is package_app
    assert root_main.main is package_main.main
    assert root_main.run is package_main.run


def test_distribution_static_assets_stay_synchronized():
    repo_root = Path(__file__).resolve().parents[1]

    for asset in [
        Path("static/index.html"),
        Path("static/css/app.css"),
        Path("static/js/i18n.js"),
        Path("static/js/dom.js"),
        Path("static/js/modal.js"),
        Path("static/js/api.js"),
        Path("static/js/config.js"),
        Path("static/js/hotkey.js"),
        Path("static/js/settings.js"),
        Path("static/js/recorder.js"),
        Path("static/js/history.js"),
        Path("static/js/status.js"),
        Path("static/js/app.js"),
    ]:
        assert (repo_root / asset).read_text(encoding="utf-8") == (
            repo_root / "src" / "voicecode" / asset
        ).read_text(encoding="utf-8")


def test_record_start_reports_model_unavailable(client, app_module):
    app_module.model = None
    app_module._set_model_state("error", "Model download failed")

    response = client.post("/record/start", json={"language": "auto"})

    assert response.status_code == 503
    assert "Cannot start recording" in response.get_json()["error"]
    assert "Model download failed" in response.get_json()["error"]


def test_config_accepts_ui_language_and_japanese_transcription(client):
    response = client.post("/config", json={"ui_language": "ja"})
    assert response.status_code == 200
    assert response.get_json()["ui_language"] == "ja"

    response = client.post("/record/start", json={"language": "ja"})
    assert response.status_code == 200


def test_static_ui_exposes_three_language_controls():
    repo_root = Path(__file__).resolve().parents[1]
    html = (repo_root / "static" / "index.html").read_text(encoding="utf-8")

    assert 'href="/css/app.css"' in html
    assert 'src="/js/i18n.js"' in html
    assert 'src="/js/dom.js"' in html
    assert 'src="/js/api.js"' in html
    assert 'src="/js/recorder.js"' in html
    assert 'src="/js/app.js"' in html
    assert 'id="uilang"' in html
    for language in ('value="en"', 'value="zh"', 'value="ja"'):
        assert language in html
    assert 'data-i18n="label_ui_language"' in html
    assert 'data-i18n="lang_ja"' in html


def test_localized_readmes_exist():
    repo_root = Path(__file__).resolve().parents[1]

    assert (repo_root / "README.md").is_file()
    assert (repo_root / "README_zh.md").is_file()
    assert (repo_root / "README_ja.md").is_file()


def test_audio_devices_endpoint_lists_input_devices(client):
    response = client.get("/audio/devices")

    assert response.status_code == 200
    body = response.get_json()
    assert body["default_input"] == 0
    assert body["devices"][0]["name"] == "Dummy Microphone"


def test_text_post_processing_modes(app_module):
    assert app_module._post_process_text("open parenthesis equals", "coding") == "( ="
    assert (
        app_module._post_process_text("heading one release notes", "markdown") == "# release notes"
    )
    assert app_module._post_process_text("write better docs", "prompt") == "write better docs."


def test_history_and_diagnostics_endpoints(client):
    response = client.post("/record/start", json={"language": "auto"})
    assert response.status_code == 200
    response = client.post("/record/stop", json={"language": "en"})
    assert response.status_code == 200

    response = client.get("/history")
    assert response.status_code == 200
    assert response.get_json()["entries"][-1]["text"] == "hello"

    response = client.get("/diagnostics")
    assert response.status_code == 200
    assert response.get_json()["app"] == "VoiceCode"

    response = client.post("/history/clear")
    assert response.status_code == 200
    assert response.get_json()["status"] == "cleared"


def test_packaging_files_exist():
    repo_root = Path(__file__).resolve().parents[1]

    assert (repo_root / "packaging" / "pyinstaller" / "voicecode.spec").is_file()
    assert (repo_root / "packaging" / "windows" / "README.md").is_file()
    assert (repo_root / ".github" / "workflows" / "release.yml").is_file()


def test_skip_model_load_blocks_reload(client, app_module, monkeypatch):
    monkeypatch.setenv("VOICECODE_SKIP_MODEL_LOAD", "1")

    response = client.post("/reload_model", json={"model": "tiny"})

    assert response.status_code == 409
    assert "VOICECODE_SKIP_MODEL_LOAD" in response.get_json()["error"]


def test_stats_without_pynvml_does_not_log_warning(client, app_module, monkeypatch, caplog):
    monkeypatch.setattr(app_module.ctranslate2, "get_cuda_device_count", lambda: 1)
    app_module._device = "cuda"
    monkeypatch.delitem(sys.modules, "pynvml", raising=False)

    response = client.get("/stats")

    assert response.status_code == 200
    assert "Failed to collect GPU stats" not in caplog.text


def test_config_rejects_boolean_audio_device(client):
    response = client.post("/config", json={"audio_device": True})

    assert response.status_code == 400
    assert "audio_device" in response.get_json()["error"]


def test_load_config_ignores_semantically_invalid_file(client, app_module, tmp_path):
    app_module.CONFIG_FILE = str(tmp_path / "config.json")
    Path(app_module.CONFIG_FILE).write_text(
        json.dumps({"history_limit": 9999, "ui_language": "xx"}),
        encoding="utf-8",
    )

    response = client.get("/config")

    assert response.status_code == 200
    assert response.get_json()["history_limit"] == app_module.DEFAULT_CONFIG["history_limit"]
    assert response.get_json()["ui_language"] == app_module.DEFAULT_CONFIG["ui_language"]


class FakeHealthResponse:
    def __init__(self, body: bytes):
        self.status = 200
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self._body


def test_wait_for_server_rejects_other_voicecode_process(monkeypatch):
    import voicecode.main as main_module

    monkeypatch.setattr(main_module.server, "PORT", 8899)
    monkeypatch.setattr(main_module.os, "getpid", lambda: 1234)
    monkeypatch.setattr(
        main_module,
        "urlopen",
        lambda *args, **kwargs: FakeHealthResponse(b'{"status":"ok","pid":5678}'),
    )

    with pytest.raises(RuntimeError, match="another VoiceCode process.*5678"):
        main_module._wait_for_server(timeout_seconds=0.1)


def test_wait_for_server_rejects_unrelated_health_endpoint(monkeypatch):
    import voicecode.main as main_module

    monkeypatch.setattr(main_module.server, "PORT", 8899)
    monkeypatch.setattr(main_module.os, "getpid", lambda: 1234)
    monkeypatch.setattr(
        main_module,
        "urlopen",
        lambda *args, **kwargs: FakeHealthResponse(b'{"status":"ok"}'),
    )

    with pytest.raises(RuntimeError, match="does not identify itself as VoiceCode"):
        main_module._wait_for_server(timeout_seconds=0.1)


def test_reload_model_recovers_after_failed_reload(client, app_module, monkeypatch):
    calls = []

    def flaky_load_model(size, *, allow_cpu_fallback=True):
        calls.append(size)
        if len(calls) == 1:
            raise RuntimeError("simulated reload failure")
        return app_module.model

    monkeypatch.setattr(app_module, "_load_model_sync", flaky_load_model)

    first = client.post("/reload_model", json={"model": "tiny"})
    assert first.status_code == 200

    deadline = time.monotonic() + 2
    state = None
    error = None
    while time.monotonic() < deadline:
        with app_module._model_state_lock:
            state = app_module._model_state["status"]
            error = app_module._model_state["error"]
        if state == "ready" and error:
            break
        time.sleep(0.01)

    assert state == "ready"
    assert error is not None and "simulated reload failure" in error

    second = client.post("/reload_model", json={"model": "small"})
    assert second.status_code == 200

    deadline = time.monotonic() + 2
    state = None
    while time.monotonic() < deadline:
        with app_module._model_state_lock:
            state = app_module._model_state["status"]
        if state == "ready":
            break
        time.sleep(0.01)

    assert state == "ready"
    assert calls == ["tiny", "small"]


def test_reload_model_rejects_second_request_while_load_is_in_progress(
    client, app_module, monkeypatch
):
    started = threading.Event()
    release = threading.Event()
    calls = []

    def slow_load_model(size, *, allow_cpu_fallback=True):
        calls.append((size, allow_cpu_fallback))
        started.set()
        assert release.wait(timeout=2), "timed out waiting to release simulated model load"
        return app_module.model

    monkeypatch.setattr(app_module, "_load_model_sync", slow_load_model)

    first = client.post("/reload_model", json={"model": "tiny"})
    assert first.status_code == 200
    assert first.get_json() == {"status": "loading", "model": "tiny"}
    assert started.wait(timeout=1)

    second = client.post("/reload_model", json={"model": "small"})
    assert second.status_code == 409
    assert second.get_json()["error"] == "A model reload is already in progress."

    release.set()
    deadline = time.monotonic() + 2
    state = None
    while time.monotonic() < deadline:
        with app_module._model_state_lock:
            state = app_module._model_state["status"]
        if state == "ready":
            break
        time.sleep(0.01)

    assert state == "ready"
    assert calls == [("tiny", True)]
