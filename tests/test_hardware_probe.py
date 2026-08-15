"""Tests for hardware probes (nvidia-smi, WMI) and the Windows app identity."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from voicecode import system_api  # noqa: E402


class FakeCompleted:
    def __init__(self, stdout: str) -> None:
        self.stdout = stdout
        self.returncode = 0


def _patch_run(monkeypatch, output: str, *, raise_exc: type[Exception] | None = None):
    def fake_run(cmd, **kwargs):  # noqa: ARG001
        if raise_exc is not None:
            raise raise_exc("simulated failure")
        return FakeCompleted(output)

    monkeypatch.setattr(system_api.subprocess, "run", fake_run)


def test_nvidia_smi_gpu_info_parses_rows(monkeypatch):
    output = "0, NVIDIA GeForce RTX 4050 Laptop GPU, 610.88, 10, 1540, 6141\n"
    _patch_run(monkeypatch, output)
    info = system_api._nvidia_smi_gpu_info()
    assert info is not None
    assert info["name"] == "NVIDIA GeForce RTX 4050 Laptop GPU"
    assert info["driver"] == "610.88"
    assert info["mem_total"] == 6141
    assert info["mem_used"] == 1540
    assert info["vendor"] == "NVIDIA"
    assert info["source"] == "nvidia-smi"


def test_nvidia_smi_missing_returns_none(monkeypatch):
    _patch_run(monkeypatch, "", raise_exc=FileNotFoundError)
    assert system_api._nvidia_smi_gpu_info() is None


def test_windows_video_controller_parses_nvidia(monkeypatch):
    payload = [
        {
            "Name": "Intel(R) UHD Graphics",
            "AdapterRAM": 1073741824,
            "DriverVersion": "31.0.101",
        },
        {
            "Name": "NVIDIA GeForce RTX 4050 Laptop GPU",
            "AdapterRAM": 6442450944,
            "DriverVersion": "610.88",
        },
    ]
    _patch_run(monkeypatch, json.dumps(payload))
    info = system_api._windows_video_controller_info()
    assert info is not None
    assert info["name"] == "NVIDIA GeForce RTX 4050 Laptop GPU"
    assert info["vendor"] == "NVIDIA"
    assert info["mem_total"] == round(6442450944 / 1024**2)


def test_windows_video_controller_picks_first_without_nvidia(monkeypatch):
    payload = [{"Name": "Intel(R) UHD Graphics", "AdapterRAM": 1073741824}]
    _patch_run(monkeypatch, json.dumps(payload))
    info = system_api._windows_video_controller_info()
    assert info is not None
    assert info["vendor"] == "Intel"
    assert info["source"] == "windows-cim"


def test_windows_video_controller_failure_returns_none(monkeypatch):
    _patch_run(monkeypatch, "", raise_exc=OSError)
    if sys.platform == "win32":
        assert system_api._windows_video_controller_info() is None


def test_gpu_info_falls_back_from_nvml_to_nvidia_smi(monkeypatch):
    def fake_run(cmd, **kwargs):  # noqa: ARG001
        return FakeCompleted("0, Fallback GPU, 1.0, 0, 0, 1024\n")

    monkeypatch.setattr(system_api, "_nvml_gpu_info", lambda: None)
    monkeypatch.setattr(system_api.subprocess, "run", fake_run)
    info = system_api._gpu_info()
    assert info is not None
    assert info["source"] == "nvidia-smi"
    assert info["name"] == "Fallback GPU"


def test_main_app_user_model_id_follows_version():
    from voicecode import main as main_module

    app_id = main_module._app_user_model_id()
    assert app_id.startswith("VoiceCode.Desktop.")
    assert "0.3" in app_id
