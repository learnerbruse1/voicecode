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
    last_transcribe_kwargs = None

    def __init__(self, *args, **kwargs):
        if self.__class__.fail_load:
            raise RuntimeError("model load failed")
        self.args = args
        self.kwargs = kwargs

    def transcribe(self, audio, **kwargs):
        self.__class__.last_transcribe_kwargs = kwargs

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
    monkeypatch.setenv("VOICECODE_DEP_DIR", str(Path(tempfile.mkdtemp()) / "VOICE_DEP"))
    monkeypatch.setenv("VOICECODE_MODEL_DIR", str(Path(tempfile.mkdtemp()) / "models"))
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
    module.app.config["TESTING"] = True
    module.CONFIG_FILE = os.path.join(tempfile.mkdtemp(), "config.json")
    module.model = DummyWhisperModel("base", device="cpu", compute_type="int8")
    module._set_model_state("ready")
    DummyStream.fail_start = False
    DummyWhisperModel.fail_load = False
    DummyWhisperModel.last_transcribe_kwargs = None
    module._recorder.stop_and_get()
    yield module
    module._recorder.stop_and_get()
    sys.modules.pop("app", None)


@pytest.fixture()
def client(app_module):
    return app_module.app.test_client()


def test_unknown_route_returns_json_error(client):
    response = client.get("/not-a-real-route")

    assert response.status_code == 404
    body = response.get_json()
    assert "error" in body
    assert "request_id" in body
    assert response.headers.get("X-VoiceCode-Request-ID") == body["request_id"]


def test_index_injects_local_api_token(client):
    response = client.get("/")

    assert response.status_code == 200
    assert 'name="voicecode-api-token"' in response.get_data(as_text=True)
    assert response.headers.get("Cache-Control") == "no-store"


def test_mutating_api_can_require_local_api_token(client, app_module):
    app_module.app.config["VOICECODE_FORCE_API_TOKEN"] = True
    try:
        missing = client.post("/config", json={})
        assert missing.status_code == 403
        assert "local API token" in missing.get_json()["error"]

        accepted = client.post(
            "/config",
            json={},
            headers={"X-VoiceCode-Token": app_module._API_TOKEN},
        )
        assert accepted.status_code == 200
    finally:
        app_module.app.config.pop("VOICECODE_FORCE_API_TOKEN", None)


def test_config_post_handles_empty_and_rejects_unknown_keys(client):
    response = client.post("/config")
    assert response.status_code == 200
    body = response.get_json()
    assert body["model"] == "base"
    assert body["ui_language"] == "en"

    response = client.post("/config", json={"unknown": 1})
    assert response.status_code == 400
    assert "Unknown config keys" in response.get_json()["error"]


def test_config_reset_restores_defaults(client):
    response = client.post("/config", json={"model": "small", "device": "cpu"})
    assert response.status_code == 200

    response = client.post("/config/reset")

    assert response.status_code == 200
    body = response.get_json()
    assert body["model"] == "base"
    assert body["device"] == "auto"
    assert body["extensions"]["hotwords"]["enabled"] is True


def test_reload_model_validates_input(client):
    response = client.post("/reload_model", json={"model": "bad-model"})
    assert response.status_code == 400
    assert response.get_json()["error"] == "Unsupported model: bad-model"


def test_models_endpoint_reports_cache_directory(client):
    response = client.get("/models")

    assert response.status_code == 200
    body = response.get_json()
    assert body["cache_dir"].endswith("models")
    assert "base" in body["cache"]
    assert body["cache"]["base"]["cached"] is False


def test_model_cache_delete_requires_confirmation_and_keeps_active_model(client, app_module):
    cache_dir = Path(app_module._model_cache_dir())
    base_dir = cache_dir / "base"
    base_dir.mkdir(parents=True)
    (base_dir / "config.json").write_text("{}", encoding="utf-8")

    response = client.post("/models/base/cache", json={})
    assert response.status_code == 400
    assert "confirm=true" in response.get_json()["error"]

    response = client.delete("/models/base/cache", json={"confirm": True})
    assert response.status_code == 409
    assert "currently loaded" in response.get_json()["error"]
    assert base_dir.exists()


def test_model_cache_delete_removes_only_selected_model(client, app_module):
    cache_dir = Path(app_module._model_cache_dir())
    tiny_dir = cache_dir / "tiny"
    small_dir = cache_dir / "small"
    tiny_dir.mkdir(parents=True)
    small_dir.mkdir(parents=True)
    (tiny_dir / "model.bin").write_bytes(b"tiny")
    (small_dir / "model.bin").write_bytes(b"small")

    response = client.delete("/models/tiny/cache", json={"confirm": True})

    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "deleted"
    assert not tiny_dir.exists()
    assert small_dir.exists()


def test_dependencies_endpoint_reports_isolated_directory(client):
    response = client.get("/dependencies")

    assert response.status_code == 200
    body = response.get_json()
    assert body["install_dir"].endswith("VOICE_DEP")
    dependency_ids = {item["id"] for item in body["dependencies"]}
    assert {"whisper-runtime", "audio-capture", "opencc-python-reimplemented"} <= dependency_ids


def test_dependency_uninstall_requires_double_confirm(client):
    response = client.post("/dependencies/jiwer/uninstall", json={})

    assert response.status_code == 400
    assert "confirm=true" in response.get_json()["error"]


def test_unknown_dependency_task_returns_json_404(client):
    response = client.get("/dependencies/tasks/not-a-task")

    assert response.status_code == 404
    assert "Unknown dependency task" in response.get_json()["error"]


def test_malformed_json_request_is_rejected_without_side_effects(client, app_module, monkeypatch):
    load_called = False

    def fail_if_called(*args, **kwargs):
        nonlocal load_called
        load_called = True
        raise AssertionError("malformed JSON must not trigger model loading")

    monkeypatch.setattr(app_module, "_load_model_sync", fail_if_called)

    response = client.post("/reload_model", data="{", content_type="application/json")

    assert response.status_code == 400
    assert "JSON payload" in response.get_json()["error"]
    assert load_called is False

    response = client.post("/record/start", data="{", content_type="application/json")

    assert response.status_code == 400
    assert "JSON payload" in response.get_json()["error"]
    assert app_module._recorder.is_recording() is False


def test_json_null_request_is_rejected_without_side_effects(client, app_module, monkeypatch):
    load_called = False

    def fail_if_called(*args, **kwargs):
        nonlocal load_called
        load_called = True
        raise AssertionError("JSON null must not trigger model loading")

    monkeypatch.setattr(app_module, "_load_model_sync", fail_if_called)

    response = client.post("/reload_model", data="null", content_type="application/json")

    assert response.status_code == 400
    assert response.get_json()["error"] == "JSON payload must be an object."
    assert load_called is False

    response = client.post("/record/start", data="null", content_type="application/json")

    assert response.status_code == 400
    assert response.get_json()["error"] == "JSON payload must be an object."
    assert app_module._recorder.is_recording() is False


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


def test_save_config_accepts_relative_filename(tmp_path, app_module, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app_module.CONFIG_FILE = "config.json"

    app_module.save_config(app_module.DEFAULT_CONFIG)

    assert (tmp_path / "config.json").is_file()


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
        "accessibility.js",
        "dom.js",
        "modal.js",
        "api.js",
        "config.js",
        "hotkey.js",
        "settings.js",
        "recorder.js",
        "history.js",
        "models.js",
        "dependencies.js",
        "extensions.js",
        "onboarding.js",
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
        Path("static/js/accessibility.js"),
        Path("static/js/dom.js"),
        Path("static/js/modal.js"),
        Path("static/js/api.js"),
        Path("static/js/config.js"),
        Path("static/js/hotkey.js"),
        Path("static/js/settings.js"),
        Path("static/js/recorder.js"),
        Path("static/js/history.js"),
        Path("static/js/models.js"),
        Path("static/js/dependencies.js"),
        Path("static/js/extensions.js"),
        Path("static/js/onboarding.js"),
        Path("static/i18n/en.json"),
        Path("static/i18n/zh.json"),
        Path("static/i18n/ja.json"),
        Path("static/js/status.js"),
        Path("static/js/app.js"),
    ]:
        assert (repo_root / asset).read_text(encoding="utf-8") == (
            repo_root / "src" / "voicecode" / asset
        ).read_text(encoding="utf-8")


def test_config_accepts_inference_controls_and_hardware_endpoint(client):
    response = client.post(
        "/config",
        json={
            "device": "cpu",
            "compute_type": "int8",
            "beam_size": 3,
            "vad_filter": False,
        },
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["device"] == "cpu"
    assert body["compute_type"] == "int8"
    assert body["beam_size"] == 3
    assert body["vad_filter"] is False

    response = client.get("/hardware")

    assert response.status_code == 200
    hardware = response.get_json()
    assert hardware["cuda_available"] is False
    assert "cpu" in hardware["supported_devices"]


def test_transcribe_endpoint_accepts_json_audio_samples(client):
    response = client.post("/transcribe", json={"audio": [0.0, 0.1, -0.1], "language": "en"})

    assert response.status_code == 200
    assert response.get_json()["text"] == "hello"


def test_extensions_endpoint_lists_default_extensions(client):
    response = client.get("/extensions")

    assert response.status_code == 200
    extensions = {item["id"]: item for item in response.get_json()["extensions"]}
    assert extensions["audio_io"]["enabled"] is True
    assert extensions["exporters"]["enabled"] is True
    assert extensions["hotwords"]["enabled"] is True
    assert extensions["vad"]["enabled"] is True
    assert extensions["zh_normalizer"]["enabled"] is False
    assert extensions["quality"]["enabled"] is False
    assert extensions["diarization"]["enabled"] is False
    assert extensions["punctuation"]["enabled"] is False


def test_extension_endpoint_updates_real_config(client):
    response = client.post(
        "/extensions/hotwords",
        json={"config": {"enabled": False, "phrases": ["Voice Code", "pytest"]}},
    )

    assert response.status_code == 200
    extension = response.get_json()["extension"]
    assert extension["enabled"] is False
    assert extension["config"]["phrases"] == ["Voice Code", "pytest"]

    config = client.get("/config").get_json()
    assert config["extensions"]["hotwords"]["enabled"] is False


def test_onboarding_status_complete_and_reset(client):
    response = client.get("/onboarding")
    assert response.status_code == 200
    assert response.get_json()["required"] is True
    assert set(response.get_json()["steps"]) == {"runtime", "audio", "model"}

    response = client.post(
        "/onboarding/complete",
        json={"config": {"ui_language": "zh", "model": "tiny"}, "skipped": False},
    )
    assert response.status_code == 200
    assert response.get_json()["config"]["onboarding"]["completed"] is True

    response = client.get("/onboarding")
    assert response.get_json()["required"] is False
    assert response.get_json()["config"]["ui_language"] == "zh"

    response = client.post("/onboarding/reset", json={})
    assert response.status_code == 200
    assert response.get_json()["onboarding"]["completed"] is False


def test_extension_dependency_install_starts_catalog_tasks(client, app_module, monkeypatch):
    started = []

    class Task:
        def __init__(self, dependency_id):
            self.dependency_id = dependency_id

        def public_dict(self):
            return {"id": "task-1", "dependency_id": self.dependency_id, "status": "queued"}

    monkeypatch.setattr(
        app_module.dependency_manager,
        "dependencies_for_feature_status",
        lambda feature_id: (
            [{"id": "jiwer", "installed_in_voice_dep": False, "installed": False}]
            if feature_id == "quality"
            else []
        ),
    )
    monkeypatch.setattr(
        app_module.dependency_manager,
        "start_install",
        lambda dependency_id: started.append(dependency_id) or Task(dependency_id),
    )

    response = client.post("/extensions/quality/install", json={})

    assert response.status_code == 202
    assert started == ["jiwer"]
    assert response.get_json()["tasks"][0]["dependency_id"] == "jiwer"


@pytest.mark.parametrize(
    "path",
    [
        "/extensions/quality",
        "/extensions/quality/install",
        "/dependencies/install-required",
        "/dependencies/jiwer/uninstall",
        "/onboarding/complete",
        "/onboarding/reset",
        "/history/clear",
    ],
)
def test_new_mutating_routes_reject_malformed_json(client, path):
    response = client.post(path, data="{", content_type="application/json")

    assert response.status_code == 400
    assert "JSON payload" in response.get_json()["error"]


def test_config_validates_extension_ids_and_keys(client):
    response = client.post("/config", json={"extensions": {"missing": {"enabled": True}}})
    assert response.status_code == 400
    assert "Unknown extension ids" in response.get_json()["error"]

    response = client.post("/config", json={"extensions": {"hotwords": {"bad": True}}})
    assert response.status_code == 400
    assert "Unknown config keys for extension 'hotwords'" in response.get_json()["error"]


def test_hotwords_and_vad_extensions_feed_transcription_kwargs(client):
    response = client.post(
        "/config",
        json={
            "extensions": {
                "hotwords": {"enabled": True, "phrases": [" FastAPI ", "CTranslate2"]},
                "vad": {
                    "enabled": True,
                    "engine": "faster_whisper",
                    "min_silence_duration_ms": 1000,
                },
            }
        },
    )
    assert response.status_code == 200

    response = client.post("/transcribe", json={"audio": [0.0, 0.1, -0.1], "language": "en"})

    assert response.status_code == 200
    kwargs = DummyWhisperModel.last_transcribe_kwargs
    assert kwargs is not None
    assert "FastAPI" in kwargs["initial_prompt"]
    assert "CTranslate2" in kwargs["initial_prompt"]
    assert kwargs["vad_filter"] is True
    assert kwargs["vad_parameters"] == {"min_silence_duration_ms": 1000}


def test_transcribe_endpoint_exports_text_formats(client):
    response = client.post(
        "/transcribe", json={"audio": [0.0, 0.1, -0.1], "language": "en", "output_format": "srt"}
    )

    assert response.status_code == 200
    assert response.mimetype == "application/x-subrip"
    assert "hello" in response.get_data(as_text=True)


def test_exporters_extension_can_be_disabled(client):
    response = client.post("/config", json={"extensions": {"exporters": {"enabled": False}}})
    assert response.status_code == 200

    response = client.post(
        "/transcribe", json={"audio": [0.0, 0.1, -0.1], "language": "en", "output_format": "txt"}
    )

    assert response.status_code == 409
    assert "exporters extension is disabled" in response.get_json()["error"]


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
    assert 'type="module" src="/js/app.js"' in html
    assert 'import {initializeI18n} from "./i18n.js"' in (
        repo_root / "static" / "js" / "app.js"
    ).read_text(encoding="utf-8")
    assert 'src="/js/dom.js"' in html
    assert 'import "./api.js"' in (repo_root / "static" / "js" / "app.js").read_text(
        encoding="utf-8"
    )
    assert 'src="/js/recorder.js"' in html
    assert 'type="module" src="/js/app.js"' in html
    assert 'class="panel language-panel"' in html
    assert 'data-i18n="settings_language"' in html
    assert 'id="uilang"' in html
    for language in ('value="en"', 'value="zh"', 'value="ja"'):
        assert language in html
    assert 'data-i18n="ui_language_en"' in html
    assert 'data-i18n="label_ui_language"' in html
    assert 'data-i18n="lang_ja"' in html
    assert 'class="sidebar"' in html
    assert 'data-view="home"' in html
    assert 'data-view="models"' in html
    assert 'id="view-models"' in html
    assert 'src="/js/models.js"' in html
    assert 'id="content-scroll"' in html
    assert 'id="win-close"' in html
    assert 'id="auto-device-toggle"' in html
    assert 'id="device-manual-options"' in html
    assert 'id="progress-overlay"' in html
    assert 'value="large-v3-turbo"' in html
    assert 'id="model-description"' in html
    assert 'id="model-button-list"' in html
    assert 'id="reset-defaults-btn"' in html
    assert 'id="history-search"' in html
    assert 'id="history-language"' in html
    assert 'id="history-export-json"' in html
    assert 'id="mic-test-btn"' in html
    assert 'id="mic-level-bar"' in html


def test_localized_readmes_exist():
    repo_root = Path(__file__).resolve().parents[1]

    assert (repo_root / "README.md").is_file()
    assert (repo_root / "README_zh.md").is_file()
    assert (repo_root / "README_ja.md").is_file()


def test_models_endpoint_includes_latest_whisper_turbo_model(client):
    response = client.get("/models")

    assert response.status_code == 200
    body = response.get_json()
    models = body["models"]
    assert "large-v3-turbo" in models
    assert "Newest Whisper model" in models["large-v3-turbo"]["description"]
    assert body["compatibility"]["large-v3-turbo"]["vram_min_gb"] >= 1


def test_audio_devices_endpoint_lists_input_devices(client):
    response = client.get("/audio/devices")

    assert response.status_code == 200
    body = response.get_json()
    assert body["default_input"] == 0
    assert body["devices"][0]["name"] == "Dummy Microphone"


def test_audio_test_reports_microphone_level(client):
    response = client.post("/audio/test", json={"duration_ms": 50})

    assert response.status_code == 200
    body = response.get_json()
    assert body["samples"] > 0
    assert body["peak"] > 0
    assert body["level_percent"] == 100
    assert body["has_signal"] is True


def test_audio_test_validates_duration_and_recording_state(client):
    response = client.post("/audio/test", json={"duration_ms": True})
    assert response.status_code == 400
    assert "duration_ms" in response.get_json()["error"]

    response = client.post("/record/start", json={"language": "en"})
    assert response.status_code == 200
    response = client.post("/audio/test", json={"duration_ms": 50})
    assert response.status_code == 409
    assert "while recording" in response.get_json()["error"]
    response = client.post("/record/cancel")
    assert response.status_code == 200


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


def test_history_filters_export_and_entry_delete(client, app_module):
    history_file = app_module._history_file()
    app_module.history_store.append_history(
        history_file,
        {
            "created_at": "2026-01-01T00:00:00+00:00",
            "language": "en",
            "model": "base",
            "text": "hello world",
        },
    )
    app_module.history_store.append_history(
        history_file,
        {
            "created_at": "2026-01-02T00:00:00+00:00",
            "language": "zh",
            "model": "small",
            "text": "?? ??",
        },
    )

    response = client.get("/history?q=hello&language=en")
    assert response.status_code == 200
    body = response.get_json()
    assert body["total"] == 1
    assert body["entries"][0]["text"] == "hello world"
    entry_id = body["entries"][0]["id"]

    response = client.get("/history/export?format=txt&q=hello")
    assert response.status_code == 200
    assert response.mimetype == "text/plain"
    assert "hello world" in response.get_data(as_text=True)
    assert "?? ??" not in response.get_data(as_text=True)

    response = client.get("/history/export?format=md")
    assert response.status_code == 200
    assert response.mimetype == "text/markdown"
    assert "# VoiceCode History" in response.get_data(as_text=True)

    response = client.delete(f"/history/{entry_id}", json={})
    assert response.status_code == 400
    assert "confirm=true" in response.get_json()["error"]

    response = client.delete(f"/history/{entry_id}", json={"confirm": True})
    assert response.status_code == 200
    assert response.get_json()["status"] == "deleted"

    response = client.get("/history")
    assert response.status_code == 200
    remaining_texts = [entry["text"] for entry in response.get_json()["entries"]]
    assert "hello world" not in remaining_texts
    assert "?? ??" in remaining_texts


def test_history_rejects_non_integer_limit(client):
    response = client.get("/history?limit=abc")

    assert response.status_code == 400
    assert "limit" in response.get_json()["error"]


def test_one_click_installer_scripts_are_not_part_of_source_tree():
    repo_root = Path(__file__).resolve().parents[1]

    for path in [
        repo_root / "setup.ps1",
        repo_root / "setup.bat",
        repo_root / "run.ps1",
        repo_root / "run.bat",
        repo_root / "packaging" / "installer",
    ]:
        assert not path.exists()
    assert (repo_root / "pyproject.toml").is_file()
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
    body = response.get_json()
    assert "cpu" in body
    assert "process_memory_mb" in body
    assert "system_memory_total_mb" in body
    assert "driver" in body["gpu"]
    assert "Failed to collect GPU stats" not in caplog.text


def test_config_rejects_boolean_audio_device(client):
    response = client.post("/config", json={"audio_device": True})

    assert response.status_code == 400
    assert "audio_device" in response.get_json()["error"]


def test_config_rejects_boolean_history_limit(client):
    response = client.post("/config", json={"history_limit": True})

    assert response.status_code == 400
    assert "history_limit" in response.get_json()["error"]


@pytest.mark.parametrize(
    "hotkey,error_fragment",
    [
        ({"modifiers": ["cmd"], "key": "x"}, "Unsupported hotkey modifiers"),
        ({"modifiers": ["alt"], "key": "   "}, "hotkey.key"),
    ],
)
def test_config_rejects_invalid_hotkey_values(client, hotkey, error_fragment):
    response = client.post("/config", json={"hotkey": hotkey})

    assert response.status_code == 400
    assert error_fragment in response.get_json()["error"]


def test_config_normalizes_hotkey_values(client):
    response = client.post("/config", json={"hotkey": {"modifiers": [" Alt "], "key": " Z "}})

    assert response.status_code == 200
    assert response.get_json()["hotkey"] == {"modifiers": ["alt"], "key": "z"}


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
    first_body = first.get_json()
    assert first_body["status"] == "loading"
    assert first_body["model"] == "tiny"
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


def test_dependency_install_uses_catalog_pypi_spec_and_writes_manifest(app_module, monkeypatch):
    from voicecode import dependencies as dependency_manager

    dep_dir = dependency_manager.dependency_dir()
    calls = []

    def fake_pip_install(task, spec, candidate, attempt):
        calls.append((candidate, attempt))
        dep_dir.mkdir(parents=True, exist_ok=True)
        (dep_dir / "jiwer.py").write_text("VALUE = 1\n", encoding="utf-8")
        return True

    monkeypatch.setattr(dependency_manager, "_run_pip_install", fake_pip_install)

    task = dependency_manager.start_install("jiwer")
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline and task.status not in {"completed", "failed"}:
        time.sleep(0.01)

    assert task.status == "completed"
    assert calls == [("jiwer>=3,<5", 0)]
    manifest = dep_dir / ".voicecode" / "jiwer.json"
    assert manifest.exists()
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert "jiwer.py" in payload["paths"]
    assert payload["source"] == "jiwer>=3,<5"


def test_dependency_failed_attempt_cleanup_is_contained(tmp_path):
    from voicecode.dependency_environment import cleanup_new_entries, top_level_snapshot

    root = tmp_path / "dependencies"
    root.mkdir()
    existing = root / "existing"
    existing.mkdir()
    before = top_level_snapshot(root)
    partial = root / "partial-download"
    partial.mkdir()

    cleanup_new_entries(root, before)

    assert existing.exists()
    assert not partial.exists()


def test_dependency_task_can_be_cancelled(app_module, monkeypatch):
    from voicecode import dependencies as dependency_manager

    entered = threading.Event()

    def cancellable_install(task, spec, candidate, attempt):
        entered.set()
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline and not task.cancel_requested:
            time.sleep(0.01)
        return False

    monkeypatch.setattr(dependency_manager, "_run_pip_install", cancellable_install)
    task = dependency_manager.start_install("jiwer")
    assert entered.wait(timeout=1)
    dependency_manager.cancel_task(task.id)
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline and task.status not in {"cancelled", "failed"}:
        time.sleep(0.01)

    assert task.status == "cancelled"
    assert task.cancelled is True


def test_dependency_uninstall_uses_manifest_and_removes_transitives(app_module):
    from voicecode import dependencies as dependency_manager

    spec = dependency_manager.get_dependency_spec("jiwer")
    dep_dir = dependency_manager.dependency_dir()
    for name in ("jiwer.py", "jiwer-1.0.dist-info", "transitive_dep"):
        path = dep_dir / name
        if name.endswith(".py"):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("VALUE = 1\n", encoding="utf-8")
        else:
            path.mkdir(parents=True, exist_ok=True)
            (path / "METADATA").write_text("Name: test\n", encoding="utf-8")
    dependency_manager._write_manifest(
        spec, ["jiwer.py", "jiwer-1.0.dist-info", "transitive_dep"], "test-source"
    )

    result = dependency_manager.uninstall_dependency("jiwer", confirm=True)

    assert result["status"] == "uninstalled"
    assert not (dep_dir / "jiwer.py").exists()
    assert not (dep_dir / "jiwer-1.0.dist-info").exists()
    assert not (dep_dir / "transitive_dep").exists()
    assert not (dep_dir / ".voicecode" / "jiwer.json").exists()


def test_i18n_catalogs_cover_supported_languages_and_layout_hooks():
    repo_root = Path(__file__).resolve().parents[1]
    catalogs = {
        language: json.loads(
            (repo_root / "static" / "i18n" / f"{language}.json").read_text(encoding="utf-8")
        )
        for language in ("en", "zh", "ja")
    }
    loader = (repo_root / "static" / "js" / "i18n.js").read_text(encoding="utf-8")

    assert "ensureI18nCatalog" in loader
    english_keys = set(catalogs["en"])
    assert {"settings_language", "settings_language_hint", "onboarding_title"} <= english_keys
    for language in ("zh", "ja"):
        assert english_keys <= set(catalogs[language])
        assert catalogs[language]["settings_language"] != catalogs["en"]["settings_language"]

    css = (repo_root / "static" / "css" / "app.css").read_text(encoding="utf-8")
    assert 'html[data-ui-language="en"] .form-grid' in css
    assert 'html[data-ui-language="zh"] .form-grid' in css
    assert 'html[data-ui-language="ja"] .form-grid' in css


def test_security_headers_host_and_origin_protection(client):
    response = client.get("/health")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]

    response = client.get("/health", headers={"Host": "evil.example"})
    assert response.status_code == 421

    response = client.post(
        "/config",
        json={},
        headers={"Origin": "https://evil.example", "Host": "localhost"},
    )
    assert response.status_code == 403


def test_config_migrates_legacy_version(tmp_path):
    from voicecode import settings

    path = tmp_path / "legacy.json"
    path.write_text(
        json.dumps({"model": "tiny", "extensions": {"vad": {"enabled": True}}}), encoding="utf-8"
    )

    config = settings.load_config(str(path))

    assert config["config_version"] == settings.CONFIG_VERSION
    assert config["model"] == "tiny"
    assert "threshold" in config["extensions"]["vad"]
    assert "onboarding" in config


def test_silero_vad_preprocesses_audio(monkeypatch):
    from voicecode.extensions import vad

    class Tensor:
        def __init__(self, values):
            self.values = np.asarray(values, dtype=np.float32)

        def detach(self):
            return self

        def cpu(self):
            return self

        def numpy(self):
            return self.values

    silero = types.ModuleType("silero_vad")
    silero.load_silero_vad = lambda: object()
    silero.get_speech_timestamps = lambda waveform, model, **kwargs: [{"start": 1, "end": 3}]
    silero.collect_chunks = lambda timestamps, waveform: Tensor([0.2, 0.3])
    torch = types.ModuleType("torch")
    torch.from_numpy = lambda values: Tensor(values)
    monkeypatch.setitem(sys.modules, "silero_vad", silero)
    monkeypatch.setitem(sys.modules, "torch", torch)
    vad.reset_runtime_cache()

    audio, metadata = vad.preprocess_audio(
        np.asarray([0.0, 0.2, 0.3, 0.0], dtype=np.float32),
        {"enabled": True, "engine": "silero"},
    )

    assert np.allclose(audio, [0.2, 0.3])
    assert metadata["engine"] == "silero"
    assert metadata["speech_segments"] == [{"start": 1, "end": 3}]


def test_punctuation_adapter_runs_nemo_model(monkeypatch):
    from voicecode.extensions import punctuation

    class Model:
        @classmethod
        def from_pretrained(cls, model_name):
            return cls()

        def to(self, device):
            return self

        def eval(self):
            return None

        def add_punctuation_capitalization(self, values):
            return ["Hello, world!"]

    models = types.ModuleType("nemo.collections.nlp.models")
    models.PunctuationCapitalizationModel = Model
    monkeypatch.setitem(sys.modules, "nemo", types.ModuleType("nemo"))
    monkeypatch.setitem(sys.modules, "nemo.collections", types.ModuleType("nemo.collections"))
    monkeypatch.setitem(
        sys.modules, "nemo.collections.nlp", types.ModuleType("nemo.collections.nlp")
    )
    monkeypatch.setitem(sys.modules, "nemo.collections.nlp.models", models)
    punctuation.reset_runtime_cache()

    result = punctuation.restore(
        "hello world", "en", {"model_name": "test", "device": "cpu", "supported_languages": ["en"]}
    )

    assert result == "Hello, world!"


def test_diarization_adapter_assigns_maximum_overlap_speaker(monkeypatch):
    from voicecode.extensions import diarization

    class Segment:
        def __init__(self, start, end):
            self.start = start
            self.end = end

    class Annotation:
        def itertracks(self, yield_label=False):
            yield Segment(0.0, 1.5), None, "SPEAKER_00"
            yield Segment(1.5, 4.0), None, "SPEAKER_01"

    class Output:
        exclusive_speaker_diarization = Annotation()

    class PipelineInstance:
        def to(self, device):
            return None

        def __call__(self, audio, **kwargs):
            return Output()

    class Pipeline:
        @classmethod
        def from_pretrained(cls, model_name, **kwargs):
            return PipelineInstance()

    pyannote = types.ModuleType("pyannote.audio")
    pyannote.Pipeline = Pipeline
    torch = types.ModuleType("torch")
    torch.device = lambda value: value
    torch.from_numpy = lambda value: value
    torch.cuda = types.SimpleNamespace(is_available=lambda: False)
    monkeypatch.setitem(sys.modules, "pyannote", types.ModuleType("pyannote"))
    monkeypatch.setitem(sys.modules, "pyannote.audio", pyannote)
    monkeypatch.setitem(sys.modules, "torch", torch)
    monkeypatch.setenv("HF_TOKEN", "test-token")
    diarization.reset_runtime_cache()

    segments = diarization.assign_speakers(
        [{"start": 0.2, "end": 1.0, "text": "a"}, {"start": 2.0, "end": 3.0, "text": "b"}],
        "audio.wav",
        {
            "model_name": "test",
            "token_env": "HF_TOKEN",
            "device": "cpu",
            "min_speakers": 1,
            "max_speakers": 2,
            "exclusive": True,
        },
    )

    assert [segment["speaker"] for segment in segments] == ["SPEAKER_00", "SPEAKER_01"]


def test_config_schema_and_dynamic_version_metadata(client):
    import voicecode

    response = client.get("/config/schema")
    assert response.status_code == 200
    assert response.get_json()["version"] >= 2
    assert "model" in response.get_json()["fields"]

    response = client.get("/")
    html = response.get_data(as_text=True)
    assert f'name="voicecode-version" content="{voicecode.__version__}"' in html

    response = client.get("/status")
    assert response.get_json()["version"] == voicecode.__version__


def test_diagnostics_export_is_redacted_zip(client):
    import io
    import zipfile

    response = client.get("/diagnostics/export")

    assert response.status_code == 200
    assert response.mimetype == "application/zip"
    with zipfile.ZipFile(io.BytesIO(response.data)) as archive:
        assert {"diagnostics.json", "config-redacted.json", "dependency-tasks.json"} <= set(
            archive.namelist()
        )
        config = json.loads(archive.read("config-redacted.json"))
        assert config["hotkey"]["key"] == "<redacted>"


def test_dependency_manifest_ignores_paths_outside_root(tmp_path, monkeypatch):
    from voicecode import dependency_environment

    root = tmp_path / "dependencies"
    outside = tmp_path / "outside.txt"
    outside.write_text("keep", encoding="utf-8")
    monkeypatch.setenv("VOICECODE_DEP_DIR", str(root))
    manifest = root / ".voicecode" / "jiwer.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps(
            {
                "dependency_id": "jiwer",
                "paths": ["../outside.txt"],
                "source": "test",
            }
        ),
        encoding="utf-8",
    )

    result = dependency_environment.uninstall_dependency("jiwer", confirm=True)

    assert result["removed"] == []
    assert outside.read_text(encoding="utf-8") == "keep"


def test_dependency_task_list_endpoint(client):
    response = client.get("/dependencies/tasks")
    assert response.status_code == 200
    assert isinstance(response.get_json()["tasks"], list)
