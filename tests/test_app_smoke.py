from concurrent.futures import Future, ThreadPoolExecutor
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


def test_partial_model_cache_is_not_reported_as_complete(app_module):
    root = Path(os.environ["VOICECODE_MODEL_DIR"])
    snapshot = root / "models--Systran--faster-whisper-base" / "snapshots" / "revision"
    snapshot.mkdir(parents=True)
    (snapshot / "model.bin").write_bytes(b"partial")

    partial = app_module._model_cache_status("base", force=True)

    assert partial["partial"] is True
    assert partial["complete"] is False
    assert partial["cached"] is False

    (snapshot / "config.json").write_text("{}", encoding="utf-8")
    (snapshot / "tokenizer.json").write_text("{}", encoding="utf-8")
    (snapshot / "vocabulary.txt").write_text("token", encoding="utf-8")
    with (snapshot / "model.bin").open("r+b") as model_file:
        model_file.truncate(app_module._minimum_model_bytes("base"))
    complete = app_module._model_cache_status("base", force=True)

    assert complete["partial"] is False
    assert complete["complete"] is True
    assert complete["cached"] is True


def test_huggingface_endpoint_selector_falls_back_to_reachable_mirror(app_module, monkeypatch):
    calls: list[str] = []

    class Response:
        def __init__(self, status_code):
            self.status_code = status_code

    class Client:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url, params):
            calls.append(url)
            if url.startswith("https://huggingface.co"):
                raise TimeoutError("official endpoint unavailable")
            return Response(200)

    fake_httpx = types.SimpleNamespace(Client=Client)
    original_import_module = app_module.importlib.import_module

    def fake_import_module(name):
        if name == "httpx":
            return fake_httpx
        return original_import_module(name)

    monkeypatch.delenv("HF_ENDPOINT", raising=False)
    monkeypatch.setattr(app_module.importlib, "import_module", fake_import_module)

    endpoint = app_module._select_reachable_huggingface_endpoint()

    assert endpoint == "https://hf-mirror.com"
    assert calls == [
        "https://huggingface.co/api/models",
        "https://hf-mirror.com/api/models",
    ]
    assert os.environ["HF_ENDPOINT"] == endpoint


def test_cached_whisper_model_uses_local_files_only(app_module):
    cache_root = app_module._model_cache_dir()
    snapshot = cache_root / "models--Systran--faster-whisper-base" / "snapshots" / "test-revision"
    snapshot.mkdir(parents=True)
    for name in ("config.json", "model.bin", "tokenizer.json", "vocabulary.txt"):
        (snapshot / name).write_bytes(b"cached")
    with (snapshot / "model.bin").open("r+b") as model_file:
        model_file.truncate(app_module._minimum_model_bytes("base"))

    kwargs = app_module._whisper_model_kwargs("cpu", "int8", 2, "base")

    assert kwargs["local_files_only"] is True
    assert kwargs["download_root"] == str(cache_root)


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

    assert voicecode.__version__ == "0.2.0"
    assert callable(launcher.main)
    static_root = resources.files("voicecode").joinpath("static")
    assert static_root.joinpath("index.html").is_file()
    assert static_root.joinpath("css", "app.css").is_file()
    assert static_root.joinpath("voicecode-icon.png").is_file()
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


def test_application_icon_assets_are_valid_and_documented():
    from PIL import Image

    repo_root = Path(__file__).resolve().parents[1]
    png_path = repo_root / "assets" / "voicecode-icon.png"
    ico_path = repo_root / "assets" / "voicecode-icon.ico"
    svg_path = repo_root / "assets" / "voicecode-icon.svg"

    with Image.open(png_path) as image:
        assert image.size == (1024, 1024)
        assert image.mode == "RGBA"
    with Image.open(ico_path) as image:
        assert image.format == "ICO"
        assert (256, 256) in image.info["sizes"]
    assert "<svg" in svg_path.read_text(encoding="utf-8")
    assert "voicecode-icon.png" in (repo_root / "README.md").read_text(encoding="utf-8")


def test_runtime_paths_keep_download_caches_under_runtime_dir(tmp_path, monkeypatch):
    from voicecode.runtime import configure_runtime_paths

    for name in [
        "VOICECODE_RUNTIME_DIR",
        "VOICECODE_MODEL_DIR",
        "VOICECODE_DEP_DIR",
        "HF_HOME",
        "HF_HUB_CACHE",
        "HUGGINGFACE_HUB_CACHE",
        "TRANSFORMERS_CACHE",
        "PIP_CACHE_DIR",
        "XDG_CACHE_HOME",
    ]:
        monkeypatch.delenv(name, raising=False)

    runtime_dir = configure_runtime_paths(tmp_path / "install" / "runtime")

    assert runtime_dir == (tmp_path / "install" / "runtime").resolve()
    for name in [
        "VOICECODE_MODEL_DIR",
        "VOICECODE_DEP_DIR",
        "HF_HOME",
        "HF_HUB_CACHE",
        "HUGGINGFACE_HUB_CACHE",
        "TRANSFORMERS_CACHE",
        "PIP_CACHE_DIR",
        "XDG_CACHE_HOME",
    ]:
        assert Path(os.environ[name]).is_relative_to(runtime_dir)
        assert Path(os.environ[name]).exists()


def test_frozen_runtime_migrates_existing_whisper_cache(tmp_path, monkeypatch):
    import voicecode.runtime as runtime

    executable = tmp_path / "install" / "VoiceCode.exe"
    target = executable.parent / "runtime" / "models"
    legacy_root = tmp_path / "legacy-huggingface"
    legacy_model = legacy_root / "models--Systran--faster-whisper-base"
    (legacy_model / "snapshots" / "revision").mkdir(parents=True)
    (legacy_model / "snapshots" / "revision" / "model.bin").write_bytes(b"model")
    executable.parent.mkdir(parents=True, exist_ok=True)
    executable.touch()
    monkeypatch.setattr(runtime.sys, "frozen", True, raising=False)
    monkeypatch.setattr(runtime.sys, "executable", str(executable))
    monkeypatch.setenv("VOICECODE_MODEL_DIR", str(target))

    migrated = runtime.migrate_legacy_model_cache("base", (legacy_root,))

    assert migrated == target / legacy_model.name
    assert (migrated / "snapshots" / "revision" / "model.bin").read_bytes() == b"model"


def test_frozen_runtime_uses_bundled_python_for_optional_dependency_installs(tmp_path, monkeypatch):
    import voicecode.runtime as runtime

    executable = tmp_path / "VoiceCode" / "VoiceCode.exe"
    bundled_python = executable.parent / "runtime" / "python" / "python.exe"
    bundled_python.parent.mkdir(parents=True)
    executable.touch()
    bundled_python.touch()
    monkeypatch.setattr(runtime.sys, "frozen", True, raising=False)
    monkeypatch.setattr(runtime.sys, "executable", str(executable))

    assert runtime.pip_python_executable() == bundled_python


def test_frozen_runtime_reports_missing_bundled_dependency_python(tmp_path, monkeypatch):
    import voicecode.runtime as runtime

    executable = tmp_path / "VoiceCode" / "VoiceCode.exe"
    executable.parent.mkdir(parents=True)
    executable.touch()
    monkeypatch.setattr(runtime.sys, "frozen", True, raising=False)
    monkeypatch.setattr(runtime.sys, "executable", str(executable))

    with pytest.raises(RuntimeError, match="bundled dependency installer"):
        runtime.pip_python_executable()


def test_root_wrappers_delegate_to_package_modules():
    import app as root_app
    import main as root_main
    import voicecode.app as package_app
    import voicecode.main as package_main

    assert root_app is package_app
    assert sys.modules["app"] is package_app
    assert root_main.main is package_main.main
    assert root_main.run is package_main.run


def test_package_launcher_configures_runtime_and_static_assets(monkeypatch):
    import voicecode.__main__ as launcher
    import voicecode.main as desktop_main
    import voicecode.runtime as runtime

    calls: list[str] = []
    monkeypatch.delenv("VOICECODE_STATIC_DIR", raising=False)
    monkeypatch.setattr(runtime, "configure_runtime_paths", lambda: calls.append("runtime"))
    monkeypatch.setattr(desktop_main, "run", lambda: calls.append("desktop") or True)

    launcher.main()

    assert calls == ["runtime", "desktop"]
    assert Path(os.environ["VOICECODE_STATIC_DIR"]).name == "static"


def test_package_launcher_exits_when_desktop_startup_fails(monkeypatch):
    import voicecode.__main__ as launcher
    import voicecode.main as desktop_main
    import voicecode.runtime as runtime

    monkeypatch.setattr(runtime, "configure_runtime_paths", lambda: None)
    monkeypatch.setattr(desktop_main, "run", lambda: False)

    with pytest.raises(SystemExit) as exc_info:
        launcher.main()

    assert exc_info.value.code == 1


def test_development_runtime_uses_current_python_and_no_implicit_runtime_dir(monkeypatch):
    import voicecode.runtime as runtime

    monkeypatch.setattr(runtime.sys, "frozen", False, raising=False)
    monkeypatch.delenv("VOICECODE_RUNTIME_DIR", raising=False)
    monkeypatch.delenv("HF_HUB_ETAG_TIMEOUT", raising=False)
    monkeypatch.delenv("HF_HUB_DOWNLOAD_TIMEOUT", raising=False)
    monkeypatch.delenv("HF_HUB_DISABLE_XET", raising=False)

    assert runtime.configure_runtime_paths() is None
    assert os.environ["HF_HUB_ETAG_TIMEOUT"] == "10"
    assert os.environ["HF_HUB_DOWNLOAD_TIMEOUT"] == "30"
    assert os.environ["HF_HUB_DISABLE_XET"] == "1"
    assert runtime.pip_python_executable() == Path(runtime.sys.executable).resolve()
    assert runtime.migrate_legacy_model_cache("base") is None


def test_distribution_static_assets_stay_synchronized():
    repo_root = Path(__file__).resolve().parents[1]

    for asset in [
        Path("static/index.html"),
        Path("static/voicecode-icon.png"),
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
        Path("static/js/games.js"),
        Path("static/js/app.js"),
    ]:
        source_asset = repo_root / "src" / "voicecode" / asset
        mirror_asset = repo_root / asset
        if asset.suffix == ".png":
            assert mirror_asset.read_bytes() == source_asset.read_bytes()
        else:
            assert mirror_asset.read_text(encoding="utf-8") == source_asset.read_text(
                encoding="utf-8"
            )


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
    assert 'src="/js/games.js"' in html
    assert 'id="game-minesweeper"' in html
    assert "solitaire" not in html.lower()
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


def test_windows_installer_configuration_keeps_runtime_data_beside_the_app():
    repo_root = Path(__file__).resolve().parents[1]
    packaging_dir = repo_root / "packaging" / "windows"
    installer = (packaging_dir / "VoiceCode.iss").read_text(encoding="utf-8")
    builder = (packaging_dir / "build_windows_installer.py").read_text(encoding="utf-8")
    runtime_hook = (packaging_dir / "runtime_hook.py").read_text(encoding="utf-8")

    assert "DefaultDirName={localappdata}\\Programs\\{#AppName}" in installer
    assert "PrivilegesRequired=lowest" in installer
    assert "{app}\\runtime\\dependencies" in installer
    assert "{app}\\runtime\\models" in installer
    assert "PyInstaller" in builder
    assert "voicecode/static" in builder
    assert "voicecode-icon.ico" in builder
    assert "SetupIconFile={#IconFile}" in installer
    assert "packaged_index.is_file()" in builder
    assert "verify_minesweeper_static_assets" in builder
    assert "js/games.js" in (packaging_dir / "verify_windows_installer.py").read_text(
        encoding="utf-8"
    )
    assert "get-pip.py" in builder
    assert "VOICECODE_RUNTIME_DIR" in runtime_hook
    assert "VOICECODE_DEP_DIR" in runtime_hook


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

    with pytest.raises(
        main_module.VoiceCodeAlreadyRunningError, match="VoiceCode is already running.*5678"
    ):
        main_module._wait_for_server(timeout_seconds=0.1)


def test_wait_for_server_rejects_missing_ui_assets(monkeypatch):
    from urllib.error import HTTPError

    import voicecode.main as main_module

    monkeypatch.setattr(main_module.server, "PORT", 8899)
    monkeypatch.setattr(main_module.os, "getpid", lambda: 1234)

    def fake_urlopen(url, *args, **kwargs):
        if url.endswith("/health"):
            return FakeHealthResponse(b'{"status":"ok","pid":1234}')
        raise HTTPError(url, 404, "not found", {}, None)

    monkeypatch.setattr(main_module, "urlopen", fake_urlopen)

    with pytest.raises(RuntimeError, match="UI assets are unavailable.*404"):
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


def test_initial_model_load_waits_for_onboarding_selection(app_module, monkeypatch):
    monkeypatch.setattr(
        app_module,
        "load_config",
        lambda: {"model": "small", "onboarding": {"completed": False}},
    )
    monkeypatch.setattr(
        app_module._model_runtime,
        "submit",
        lambda *args, **kwargs: pytest.fail("model load started before onboarding completion"),
    )

    app_module._start_initial_model_load()

    with app_module._model_state_lock:
        state = dict(app_module._model_state)
    assert state["status"] == "awaiting_selection"
    assert state["target_model"] == "small"
    assert state["phase"] == "selection"


def test_initial_model_load_uses_configured_model(app_module, monkeypatch):
    calls = []
    completed = Future()
    completed.set_result(app_module.model)
    monkeypatch.setattr(
        app_module,
        "load_config",
        lambda: {"model": "small", "onboarding": {"completed": True}},
    )
    monkeypatch.setattr(app_module, "_cached_model_complete", lambda name: True)
    monkeypatch.setattr(app_module, "_start_model_download_monitor", lambda *args: None)
    monkeypatch.setattr(
        app_module._model_runtime,
        "submit",
        lambda function, model_name: calls.append((function, model_name)) or completed,
    )
    app_module._set_model_state("ready")

    app_module._start_initial_model_load()

    assert calls == [(app_module._load_model_sync, "small")]
    with app_module._model_state_lock:
        assert app_module._model_state["target_model"] == "small"
        assert app_module._model_state["status"] == "ready"


def test_model_network_failure_is_structured_and_redacts_signed_urls(app_module):
    failure = app_module._model_failure_details(
        TimeoutError(
            "The read operation timed out at "
            "https://cas-bridge.xethub.hf.co/model.bin?X-Amz-Signature=secret"
        ),
        "small",
    )

    assert failure["error_code"] == "model_network_timeout"
    assert failure["retryable"] is True
    assert failure["target_model"] == "small"
    assert "<redacted>" in failure["technical_details"]
    assert "secret" not in failure["technical_details"]
    assert {"retry", "check_network", "check_proxy"} <= set(failure["suggestions"])


def test_network_download_error_does_not_retry_model_on_cpu(app_module, monkeypatch):
    calls = []

    class TimeoutWhisperModel:
        def __init__(self, model_name, **kwargs):
            calls.append((model_name, kwargs["device"]))
            raise TimeoutError("The read operation timed out")

    monkeypatch.setattr(
        app_module,
        "load_config",
        lambda: {"device": "cuda", "compute_type": "auto"},
    )
    monkeypatch.setattr(app_module, "_resolve_device_profile", lambda *args: ("cuda", "float16", 4))
    monkeypatch.setattr(app_module, "_gpu_has_enough_vram", lambda name: (True, 8192, 2.0))
    monkeypatch.setattr(app_module, "migrate_legacy_model_cache", lambda name: None)
    monkeypatch.setattr(app_module, "_cached_model_complete", lambda name: False)
    monkeypatch.setattr(app_module, "_select_reachable_huggingface_endpoint", lambda: None)
    monkeypatch.setattr(app_module, "_load_whisper_model_class", lambda: TimeoutWhisperModel)

    with pytest.raises(RuntimeError, match="timed out"):
        app_module._load_model_sync("small")

    assert calls == [("small", "cuda")]


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
        if state == "error" and error:
            break
        time.sleep(0.01)

    assert state == "error"
    assert error is not None and "could not be downloaded or initialized" in error
    with app_module._model_state_lock:
        assert app_module._model_state["error_code"] == "model_load_failed"
        assert app_module._model_state["active_model_available"] is True
        assert "simulated reload failure" in app_module._model_state["technical_details"]

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
    second_body = second.get_json()
    assert second_body["error_code"] == "model_operation_busy"
    assert second_body["model_state"]["target_model"] == "tiny"
    assert second_body["requested_model"] == "small"

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

    dependency_installer = importlib.import_module("voicecode.dependency_installer")
    monkeypatch.setattr(dependency_installer, "_run_pip_install", fake_pip_install)

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

    dependency_installer = importlib.import_module("voicecode.dependency_installer")
    monkeypatch.setattr(dependency_installer, "_run_pip_install", cancellable_install)
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
        assert all("??" not in value for value in catalogs[language].values())
        assert any(
            any(ord(character) > 127 for character in value)
            for value in catalogs[language].values()
        )

    for readme_name in ("README_zh.md", "README_ja.md"):
        readme = (repo_root / readme_name).read_text(encoding="utf-8")
        assert "??" not in readme
        assert "v0.2.0" in readme

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


@pytest.mark.parametrize(
    ("body", "content_type"),
    [
        ("{", "application/json"),
        ("[]", "application/json"),
        ("{}", "text/plain"),
    ],
)
def test_config_reset_rejects_invalid_nonempty_bodies_without_side_effects(
    client, body, content_type
):
    saved = client.post("/config", json={"language": "en"})
    assert saved.status_code == 200

    response = client.post("/config/reset", data=body, content_type=content_type)

    assert response.status_code == 400
    assert client.get("/config").get_json()["language"] == "en"


@pytest.mark.parametrize(
    ("body", "content_type"),
    [
        ("{", "application/json"),
        ("[]", "application/json"),
        ("{}", "text/plain"),
    ],
)
def test_client_log_rejects_invalid_nonempty_bodies(client, body, content_type):
    response = client.post("/log", data=body, content_type=content_type)

    assert response.status_code == 400
    assert "JSON payload" in response.get_json()["error"]


def test_record_start_validates_json_before_model_availability(client, app_module):
    app_module._set_model_state("error", "Model unavailable for test")

    response = client.post("/record/start", data="{", content_type="application/json")

    assert response.status_code == 400
    assert "JSON payload" in response.get_json()["error"]
    assert app_module._recorder.is_recording() is False


@pytest.mark.parametrize(
    "path",
    ["/config", "/config/reset", "/audio/test", "/record/start", "/transcribe"],
)
def test_oversized_request_bodies_preserve_http_413(client, app_module, path):
    previous_limit = app_module.app.config["MAX_CONTENT_LENGTH"]
    app_module.app.config["MAX_CONTENT_LENGTH"] = 128
    try:
        response = client.post(path, data=b"x" * 129, content_type="application/json")
    finally:
        app_module.app.config["MAX_CONTENT_LENGTH"] = previous_limit

    assert response.status_code == 413
    assert response.is_json


def test_concurrent_config_updates_are_atomic(app_module):
    for _ in range(30):
        app_module.save_config(app_module.settings_store.default_config())

        def update(payload):
            with app_module.app.test_client() as concurrent_client:
                return concurrent_client.post("/config", json=payload).status_code

        with ThreadPoolExecutor(max_workers=2) as executor:
            statuses = list(executor.map(update, [{"language": "en"}, {"text_mode": "coding"}]))

        config = app_module.load_config()
        assert statuses == [200, 200]
        assert config["language"] == "en"
        assert config["text_mode"] == "coding"


def test_concurrent_history_deletes_are_serialized(tmp_path):
    history_store = importlib.import_module("voicecode.history")
    history_file = tmp_path / "history.jsonl"

    for _ in range(30):
        history_file.unlink(missing_ok=True)
        history_store.append_history(history_file, {"id": "a", "text": "first"})
        history_store.append_history(history_file, {"id": "b", "text": "second"})

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(
                executor.map(
                    lambda entry_id: history_store.delete_history_entry(history_file, entry_id),
                    ["a", "b"],
                )
            )

        assert results == [True, True]
        assert history_store.read_all_history(history_file) == []
        assert not list(tmp_path.glob(".*.tmp"))


def test_frontend_uses_shared_html_escape_and_clean_progress_separators():
    repo_root = Path(__file__).resolve().parents[1]
    static_js = repo_root / "src" / "voicecode" / "static" / "js"
    dom_source = (static_js / "dom.js").read_text(encoding="utf-8")
    models_source = (static_js / "models.js").read_text(encoding="utf-8")

    assert "function htmlEscape(value)" in dom_source
    assert "escapeHtml(" not in models_source

    for filename in (
        "dependencies.js",
        "extensions.js",
        "models.js",
        "onboarding.js",
        "settings.js",
    ):
        source = (static_js / filename).read_text(encoding="utf-8")
        assert "} ? ${" not in source


def test_frontend_dialog_stack_and_onboarding_warning_guards():
    repo_root = Path(__file__).resolve().parents[1]
    static_root = repo_root / "src" / "voicecode" / "static"
    accessibility = (static_root / "js" / "accessibility.js").read_text(encoding="utf-8")
    app_source = (static_root / "js" / "app.js").read_text(encoding="utf-8")
    dependencies = (static_root / "js" / "dependencies.js").read_text(encoding="utf-8")
    styles = (static_root / "css" / "app.css").read_text(encoding="utf-8")

    assert "const activeDialogs = []" in accessibility
    assert "activeDialogs[activeDialogs.length - 1]" in accessibility
    assert 'document.body.classList.toggle("dialog-open", hasActiveDialog)' in accessibility
    assert "const onboardingVisible = await loadOnboarding(false)" in app_source
    assert "if (!onboardingVisible) await warnMissingDependenciesOnce()" in app_source
    assert "if (onboardingVisible) return false" in dependencies
    onboarding = (static_root / "js" / "onboarding.js").read_text(encoding="utf-8")
    completion = onboarding.split("async function completeOnboarding", 1)[1].split(
        "export function setupOnboarding", 1
    )[0]
    language_handler = onboarding.split("languageSelect.onchange", 1)[1].split("} else if", 1)[0]
    assert "captureOnboardingStep();" in language_handler
    assert (
        'const selectedLanguage = onboardingState.config.ui_language || "en";' in language_handler
    )
    assert "deactivateDialog(overlay);" in completion
    assert "await warnMissingDependenciesOnce();" in completion
    assert completion.index("deactivateDialog(overlay);") < completion.index(
        "await warnMissingDependenciesOnce();"
    )
    assert ".modal-backdrop" in styles and "z-index:1400" in styles
    models_script = (static_root / "js" / "models.js").read_text(encoding="utf-8")
    settings_script = (static_root / "js" / "settings.js").read_text(encoding="utf-8")
    dom_script = (static_root / "js" / "dom.js").read_text(encoding="utf-8")
    assert (
        "modelOperationProgress" in models_script and "modelOperationErrorMessage" in models_script
    )
    assert "modelOperationProgress" in settings_script and "suppressPopup: true" in settings_script
    assert "model_download_stalled" in dom_script and "progressBar.classList.add" in dom_script


def test_manifest_recursively_includes_all_python_tests():
    repo_root = Path(__file__).resolve().parents[1]
    manifest = (repo_root / "MANIFEST.in").read_text(encoding="utf-8")

    assert "recursive-include tests *.py" in manifest


def test_desktop_hotkey_listener_and_transcription_delivery(monkeypatch):
    main_module = importlib.import_module("voicecode.main")
    scripts: list[str] = []

    class FakeWindow:
        def evaluate_js(self, script):
            scripts.append(script)

    class FakeKey:
        alt_l = object()
        alt_r = object()
        ctrl_l = object()
        ctrl_r = object()
        shift_l = object()
        shift_r = object()
        space = object()

    class FakeListener:
        def __init__(self, on_press, on_release):
            self.on_press = on_press
            self.on_release = on_release
            self.started = False

        def start(self):
            self.started = True

    fake_kb = types.SimpleNamespace(Key=FakeKey, Listener=FakeListener)
    monkeypatch.setattr(main_module, "kb", fake_kb)
    monkeypatch.setattr(
        main_module,
        "_MOD_MAP",
        {
            "alt": (FakeKey.alt_l, FakeKey.alt_r),
            "ctrl": (FakeKey.ctrl_l, FakeKey.ctrl_r),
            "shift": (FakeKey.shift_l, FakeKey.shift_r),
        },
    )
    monkeypatch.setattr(main_module, "_window", FakeWindow())

    listener = main_module._start_listener({"modifiers": ["alt"], "key": "z"})
    key_z = types.SimpleNamespace(char="z")
    listener.on_press(FakeKey.alt_l)
    listener.on_press(key_z)
    listener.on_release(key_z)
    listener.on_release(FakeKey.alt_l)

    typed: list[str] = []
    monkeypatch.setattr(main_module, "_type_text", typed.append)
    main_module._set_typing_from_global(True)
    main_module._on_transcription('hello "VoiceCode"')

    assert listener.started is True
    assert scripts[:2] == [
        "window._recStart && window._recStart()",
        "window._recStop && window._recStop()",
    ]
    assert typed == ['hello "VoiceCode"']
    assert "window._appendText" in scripts[-1]
    assert '\\"VoiceCode\\"' in scripts[-1]


def test_desktop_window_api_fallbacks_and_hotkey_update(monkeypatch):
    main_module = importlib.import_module("voicecode.main")
    calls: list[str] = []

    class FakeWindow:
        def minimize(self):
            calls.append("minimize")

        def toggle_fullscreen(self):
            calls.append("toggle")

        def destroy(self):
            calls.append("destroy")

    class OldListener:
        def stop(self):
            calls.append("listener-stop")

        def join(self, timeout):
            calls.append(f"listener-join-{timeout}")

    replacement_listener = object()
    monkeypatch.setattr(main_module, "_window", FakeWindow())
    monkeypatch.setattr(main_module.os, "name", "posix")
    monkeypatch.setattr(main_module, "_listener", OldListener())
    monkeypatch.setattr(main_module, "_start_listener", lambda config: replacement_listener)

    api = main_module.Api()
    assert api.minimize_window() is True
    assert api.toggle_maximize_window() is True
    assert api.close_window() is True
    assert api.set_on_top(True) is False
    assert api.update_hotkey({"modifiers": ["ctrl"], "key": "space"}) is True
    main_module._set_typing_from_global(True)
    assert api.rec_stopped_from_ui() is True
    assert main_module._consume_typing_from_global() is False
    assert main_module._listener is replacement_listener
    assert calls == ["minimize", "toggle", "destroy", "listener-stop", "listener-join-1"]


def test_desktop_main_lifecycle_with_fake_backends(monkeypatch):
    main_module = importlib.import_module("voicecode.main")
    calls: list[object] = []
    fake_window = object()
    fake_listener = object()

    class FakeThread:
        def __init__(self, target, daemon):
            self.target = target
            self.daemon = daemon

        def start(self):
            self.target()

    class FakeWebview:
        def create_window(self, title, url, **kwargs):
            calls.append(("window", title, url, kwargs["width"], kwargs["min_size"]))
            return fake_window

        def start(self, func):
            calls.append(("webview-start", func))
            func()

    monkeypatch.setattr(main_module, "webview", FakeWebview())
    monkeypatch.setattr(main_module, "_acquire_instance_mutex", lambda: True)
    monkeypatch.setattr(
        main_module, "_release_instance_mutex", lambda: calls.append("mutex-release")
    )
    monkeypatch.setattr(main_module.threading, "Thread", FakeThread)
    monkeypatch.setattr(main_module.server, "start_server", lambda: calls.append("server-start"))
    monkeypatch.setattr(main_module, "_wait_for_server", lambda: calls.append("server-ready"))
    monkeypatch.setattr(
        main_module.server,
        "load_config",
        lambda: {"hotkey": {"modifiers": ["alt"], "key": "z"}},
    )
    monkeypatch.setattr(main_module, "_start_listener", lambda config: fake_listener)
    monkeypatch.setattr(main_module, "_start_tray_icon", lambda: calls.append("tray"))
    monkeypatch.setattr(main_module, "_hide_console", lambda: calls.append("hide-console"))
    monkeypatch.setattr(
        main_module,
        "_apply_windows_window_icon_with_retry",
        lambda: calls.append("window-icon"),
    )
    monkeypatch.setattr(
        main_module.server,
        "shutdown_application",
        lambda: calls.append("server-shutdown"),
    )

    main_module.main()

    assert main_module._window is fake_window
    assert main_module._listener is None
    assert main_module.server.on_transcription is main_module._on_transcription
    assert calls[0:2] == ["server-start", "server-ready"]
    assert any(isinstance(call, tuple) and call[0] == "webview-start" for call in calls)
    assert "tray" in calls
    assert "hide-console" in calls
    assert "window-icon" in calls
    assert "server-shutdown" in calls
    assert "mutex-release" in calls


def test_desktop_helpers_handle_optional_ui_failures(monkeypatch):
    main_module = importlib.import_module("voicecode.main")

    monkeypatch.setenv("VOICECODE_TEST_FLAG", "yes")
    assert main_module._env_flag("VOICECODE_TEST_FLAG") is True

    monkeypatch.setattr(main_module, "_window", None)
    main_module._eval_js_safe("window.noop()")

    class BrokenWindow:
        def evaluate_js(self, script):
            raise RuntimeError(f"cannot evaluate {script}")

    monkeypatch.setattr(main_module, "_window", BrokenWindow())
    main_module._eval_js_safe("window.fail()")

    monkeypatch.setattr(main_module, "main", lambda: None)
    assert main_module.run() is True


def test_desktop_run_reports_startup_errors(monkeypatch):
    main_module = importlib.import_module("voicecode.main")
    reported: list[str] = []
    monkeypatch.setattr(
        main_module, "main", lambda: (_ for _ in ()).throw(RuntimeError("desktop failed"))
    )
    monkeypatch.setattr(main_module, "_show_startup_error", lambda exc: reported.append(str(exc)))

    assert main_module.run() is False
    assert reported == ["desktop failed"]


def test_second_desktop_launch_focuses_existing_instance_without_starting_server(monkeypatch):
    main_module = importlib.import_module("voicecode.main")
    calls: list[str] = []

    monkeypatch.setattr(main_module, "_acquire_instance_mutex", lambda: False)
    monkeypatch.setattr(
        main_module, "_focus_existing_window", lambda: calls.append("focus") or True
    )

    with pytest.raises(main_module.VoiceCodeAlreadyRunningError, match="already running"):
        main_module.main()

    assert calls == ["focus"]


def test_run_treats_second_desktop_launch_as_success(monkeypatch):
    main_module = importlib.import_module("voicecode.main")
    reported: list[str] = []

    monkeypatch.setattr(
        main_module,
        "main",
        lambda: (_ for _ in ()).throw(main_module.VoiceCodeAlreadyRunningError("already running")),
    )
    monkeypatch.setattr(main_module, "_focus_existing_window", lambda: True)
    monkeypatch.setattr(main_module, "_show_startup_error", lambda exc: reported.append(str(exc)))

    assert main_module.run() is True
    assert reported == []


def test_dependency_task_persistence_pruning_and_restart_recovery(tmp_path, monkeypatch):
    installer = importlib.import_module("voicecode.dependency_installer")
    task_file = tmp_path / "tasks.json"
    monkeypatch.setattr(installer, "task_state_path", lambda: task_file)
    monkeypatch.setattr(installer, "_tasks", {})
    monkeypatch.setattr(installer, "_active_by_dependency", {})
    monkeypatch.setattr(installer, "_MAX_REMEMBERED_TASKS", 2)
    monkeypatch.setenv("VOICECODE_DEP_INSTALL_TIMEOUT_SECONDS", "invalid")
    assert installer._task_timeout_seconds() == 1800
    monkeypatch.setenv("VOICECODE_DEP_INSTALL_TIMEOUT_SECONDS", "10")
    assert installer._task_timeout_seconds() == 60

    for index in range(3):
        task = installer.DependencyTask(
            id=f"done-{index}",
            dependency_id="jiwer",
            action="install",
            status="completed",
            finished_at=float(index + 1),
        )
        installer._tasks[task.id] = task
    installer._prune_finished_tasks_locked()
    assert sorted(installer._tasks) == ["done-1", "done-2"]
    installer._save_tasks_locked()

    payload = json.loads(task_file.read_text(encoding="utf-8"))
    payload.append(
        installer.DependencyTask(
            id="interrupted",
            dependency_id="jiwer",
            action="install",
            status="running",
            process_id=123,
        ).public_dict()
    )
    task_file.write_text(json.dumps(payload), encoding="utf-8")
    installer._tasks.clear()
    installer._load_tasks()

    interrupted = installer._tasks["interrupted"]
    assert interrupted.status == "failed"
    assert interrupted.process_id is None
    assert "interrupted" in interrupted.error.lower()

    monkeypatch.setattr(installer, "_persist_tasks", lambda: None)
    for index in range(405):
        installer._append_task_log(interrupted, f"line {index}")
    assert len(interrupted.log) == 400
    assert interrupted.log[0] == "line 5"
    assert interrupted.message == "line 404"


def test_dependency_cross_process_lock_handles_busy_and_stale_files(tmp_path, monkeypatch):
    installer = importlib.import_module("voicecode.dependency_installer")
    lock_path = tmp_path / "install.lock"
    monkeypatch.setattr(installer, "install_lock_path", lambda: lock_path)

    with installer._cross_process_install_lock(60):
        assert lock_path.is_file()
    assert not lock_path.exists()

    lock_path.write_text("busy", encoding="utf-8")
    with pytest.raises(RuntimeError, match="already modifying"):
        with installer._cross_process_install_lock(60):
            pass

    old_time = time.time() - 1000
    os.utime(lock_path, (old_time, old_time))
    with installer._cross_process_install_lock(60):
        assert "pid=" in lock_path.read_text(encoding="utf-8")
    assert not lock_path.exists()


def test_dependency_pip_runner_streams_output_and_cleans_state(tmp_path, monkeypatch):
    installer = importlib.import_module("voicecode.dependency_installer")
    task = installer.DependencyTask(id="pip-task", dependency_id="jiwer", action="install")
    spec = installer.get_dependency_spec("jiwer")
    captured: dict[str, object] = {}

    class ImmediateThread:
        def __init__(self, target, daemon):
            self.target = target
            self.daemon = daemon

        def start(self):
            self.target()

    class FakeProcess:
        pid = 4321
        stdout = iter(["collecting dependency\n", "installing dependency\n"])

        def poll(self):
            return 0

        def wait(self, timeout):
            captured["wait_timeout"] = timeout
            return 0

    def fake_popen(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return FakeProcess()

    monkeypatch.setattr(installer, "dependency_dir", lambda: tmp_path / "dependencies")
    monkeypatch.setattr(installer.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(installer.threading, "Thread", ImmediateThread)
    monkeypatch.setattr(installer, "_save_tasks_locked", lambda: None)
    monkeypatch.setattr(installer, "_processes", {})

    assert installer._run_pip_install(task, spec, spec.pip_spec, 0) is True
    assert task.status == "running"
    assert task.process_id is None
    assert task.source == spec.pip_spec
    assert task.progress >= 13
    assert "collecting dependency" in task.log
    assert task.log[-1] == "pip install completed successfully."
    assert installer._processes == {}
    assert captured["wait_timeout"] == 10
    command = captured["command"]
    assert isinstance(command, list)
    assert "--target" in command
    assert spec.pip_spec == command[-1]


def test_dependency_process_termination_falls_back_to_kill(monkeypatch):
    installer = importlib.import_module("voicecode.dependency_installer")
    calls: list[str] = []

    class FakeProcess:
        pid = 99

        def poll(self):
            return None

        def terminate(self):
            calls.append("terminate")
            raise RuntimeError("terminate failed")

        def wait(self, timeout):
            calls.append(f"wait-{timeout}")

        def kill(self):
            calls.append("kill")

    original_import_module = installer.importlib.import_module

    def fail_psutil(name):
        if name == "psutil":
            raise ImportError("missing psutil")
        return original_import_module(name)

    monkeypatch.setattr(installer.importlib, "import_module", fail_psutil)
    installer._terminate_process(FakeProcess())

    assert calls == ["terminate", "kill"]
