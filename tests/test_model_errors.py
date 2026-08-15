"""Tests for structured model-failure classification and suggestions."""

from __future__ import annotations

import importlib
import sys
import tempfile
import types
from pathlib import Path

import pytest


class DummyCT:
    @staticmethod
    def get_cuda_device_count():
        return 0


class DummyWhisperModel:
    def __init__(self, *args, **kwargs):
        pass


@pytest.fixture()
def app_module(monkeypatch):
    monkeypatch.setenv("VOICECODE_DEP_DIR", str(Path(tempfile.mkdtemp()) / "VOICE_DEP"))
    monkeypatch.setenv("VOICECODE_MODEL_DIR", str(Path(tempfile.mkdtemp()) / "models"))
    monkeypatch.setitem(sys.modules, "ctranslate2", DummyCT)
    faster_whisper = types.ModuleType("faster_whisper")
    faster_whisper.WhisperModel = DummyWhisperModel
    monkeypatch.setitem(sys.modules, "faster_whisper", faster_whisper)
    sys.modules.pop("app", None)
    module = importlib.import_module("app")
    yield module
    sys.modules.pop("app", None)


def test_offline_cache_missing_classified(app_module):
    failure = app_module._model_failure_details(
        RuntimeError("outgoing traffic has been disabled"), "small"
    )
    assert failure["error_code"] == "model_offline_cache_missing"
    assert "disable_offline" in failure["suggestions"]


def test_timeout_precedes_generic_connection_error(app_module):
    failure = app_module._model_failure_details(
        RuntimeError("Connection to huggingface.co read timed out"), "small"
    )
    assert failure["error_code"] == "model_network_timeout"


def test_network_unreachable_classified(app_module):
    failure = app_module._model_failure_details(RuntimeError("Network is unreachable"), "small")
    assert failure["error_code"] == "model_network_unreachable"
    assert "check_network" in failure["suggestions"]


def test_cache_incomplete_classified(app_module):
    failure = app_module._model_failure_details(
        RuntimeError("File model.bin reconstruction failed"), "small"
    )
    assert failure["error_code"] == "model_cache_incomplete"
    assert "delete_partial_cache" in failure["suggestions"]


def test_disk_full_classified(app_module):
    failure = app_module._model_failure_details(RuntimeError("No space left on device"), "small")
    assert failure["error_code"] == "model_disk_full"
    assert failure["retryable"] is False


def test_permission_denied_classified(app_module):
    failure = app_module._model_failure_details(RuntimeError("Permission denied: cache"), "small")
    assert failure["error_code"] == "model_cache_not_writable"
    assert failure["retryable"] is False


def test_generic_failure_falls_back_to_load_failed(app_module):
    failure = app_module._model_failure_details(RuntimeError("something unexpected"), "small")
    assert failure["error_code"] == "model_load_failed"
    assert "switch_to_cpu" in failure["suggestions"]
    assert "retry" in failure["suggestions"]
