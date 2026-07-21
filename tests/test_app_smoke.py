import importlib
import os
from pathlib import Path
import sys
import tempfile
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
    monkeypatch.setitem(sys.modules, "sounddevice", sounddevice)

    sys.modules.pop("app", None)
    module = importlib.import_module("app")
    module.CONFIG_FILE = os.path.join(tempfile.mkdtemp(), "config.json")
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
    assert response.get_json()["model"] == "base"

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
    assert resources.files("voicecode").joinpath("static", "index.html").is_file()


def test_distribution_sources_stay_synchronized():
    repo_root = Path(__file__).resolve().parents[1]

    assert (repo_root / "app.py").read_text(encoding="utf-8") == (
        repo_root / "src" / "voicecode" / "app.py"
    ).read_text(encoding="utf-8")

    root_main = (repo_root / "main.py").read_text(encoding="utf-8")
    package_main = (repo_root / "src" / "voicecode" / "main.py").read_text(encoding="utf-8")
    normalized_root_main = root_main.replace("import app as server", "from . import app as server")
    assert normalized_root_main == package_main

    assert (repo_root / "static" / "index.html").read_text(encoding="utf-8") == (
        repo_root / "src" / "voicecode" / "static" / "index.html"
    ).read_text(encoding="utf-8")
