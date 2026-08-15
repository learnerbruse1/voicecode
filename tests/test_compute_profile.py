"""Tests for device/compute-type profile resolution (CPU fallback + Blackwell)."""

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

    @staticmethod
    def get_supported_compute_types(device: str):
        if device == "cuda":
            return ["float16", "int8_float16", "int8", "float32"]
        return ["int8", "int16", "float32", "int8_float32"]


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


def _patch_env(monkeypatch, app_module, *, cuda: bool, capability):
    monkeypatch.setattr(app_module, "_cuda_device_count", lambda: 1 if cuda else 0)
    monkeypatch.setattr(app_module, "_gpu_compute_capability", lambda: capability)
    monkeypatch.setattr(app_module, "_default_cpu_threads", lambda: 4)
    monkeypatch.delenv("WHISPER_DEVICE", raising=False)
    monkeypatch.delenv("WHISPER_COMPUTE_TYPE", raising=False)


def test_cpu_fallback_downgrades_gpu_only_compute_type(app_module, monkeypatch):
    _patch_env(monkeypatch, app_module, cuda=False, capability=None)
    device, compute, _threads = app_module._resolve_device_profile("auto", "float16")
    assert device == "cpu"
    assert compute == "int8"


def test_cpu_keeps_supported_compute_types(app_module, monkeypatch):
    _patch_env(monkeypatch, app_module, cuda=False, capability=None)
    device, compute, _threads = app_module._resolve_device_profile("auto", "int8")
    assert (device, compute) == ("cpu", "int8")
    device, compute, _threads = app_module._resolve_device_profile("auto", "float32")
    assert (device, compute) == ("cpu", "float32")


def test_cuda_auto_uses_float16(app_module, monkeypatch):
    _patch_env(monkeypatch, app_module, cuda=True, capability=(8, 9))
    device, compute, _threads = app_module._resolve_device_profile("auto", "auto")
    assert (device, compute) == ("cuda", "float16")


def test_cuda_explicit_float16_kept(app_module, monkeypatch):
    _patch_env(monkeypatch, app_module, cuda=True, capability=(8, 9))
    device, compute, _threads = app_module._resolve_device_profile("auto", "float16")
    assert (device, compute) == ("cuda", "float16")


def test_blackwell_filters_int8_supported(app_module, monkeypatch):
    _patch_env(monkeypatch, app_module, cuda=True, capability=(12, 0))
    supported = app_module._supported_compute_types("cuda")
    assert "int8" not in supported
    assert "int8_float16" not in supported
    assert "float16" in supported


def test_blackwell_downgrades_explicit_int8(app_module, monkeypatch):
    _patch_env(monkeypatch, app_module, cuda=True, capability=(12, 0))
    device, compute, _threads = app_module._resolve_device_profile("auto", "int8")
    assert (device, compute) == ("cuda", "float16")


def test_non_blackwell_keeps_int8(app_module, monkeypatch):
    _patch_env(monkeypatch, app_module, cuda=True, capability=(8, 9))
    device, compute, _threads = app_module._resolve_device_profile("auto", "int8")
    assert (device, compute) == ("cuda", "int8")


def test_gpu_capability_query_is_cached(app_module, monkeypatch):
    calls = {"init": 0}

    class FakeNVML:
        def nvmlInit(self):
            calls["init"] += 1

        def nvmlDeviceGetHandleByIndex(self, index):
            return object()

        def nvmlDeviceGetCudaComputeCapability(self, handle):
            return (12, 0)

    monkeypatch.setitem(sys.modules, "pynvml", FakeNVML())
    app_module._gpu_capability_cache = None
    assert app_module._gpu_compute_capability() == (12, 0)
    assert app_module._gpu_compute_capability() == (12, 0)
    assert calls["init"] == 1


def test_gpu_memory_total_is_cached(app_module, monkeypatch):
    calls = {"init": 0}

    class FakeNVML:
        def nvmlInit(self):
            calls["init"] += 1

        def nvmlDeviceGetHandleByIndex(self, index):
            return object()

        def nvmlDeviceGetMemoryInfo(self, handle):
            return types.SimpleNamespace(total=6 * 1024**3)

    monkeypatch.setitem(sys.modules, "pynvml", FakeNVML())
    app_module._gpu_memory_cache = None
    assert app_module._gpu_memory_total_mb() == 6144
    assert app_module._gpu_memory_total_mb() == 6144
    assert calls["init"] == 1


def test_model_compatibility_reports_missing_cuda_runtime(app_module, monkeypatch):
    monkeypatch.setattr(app_module, "_gpu_memory_total_mb", lambda: 8192)
    monkeypatch.setattr(app_module, "_cuda_device_count", lambda: 0)
    comp = app_module._model_compatibility()
    reason = comp["base"]["reason"] or ""
    assert "CUDA runtime" in reason


def test_model_compatibility_omits_reason_when_cuda_available(app_module, monkeypatch):
    monkeypatch.setattr(app_module, "_gpu_memory_total_mb", lambda: 8192)
    monkeypatch.setattr(app_module, "_cuda_device_count", lambda: 1)
    comp = app_module._model_compatibility()
    reason = comp["base"]["reason"] or ""
    assert "CUDA runtime" not in reason
