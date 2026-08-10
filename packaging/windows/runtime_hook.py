"""Runtime hook that reserves a writable runtime directory beside VoiceCode.exe."""

from __future__ import annotations

import contextlib
import os
import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    exe_dir = Path(sys.executable).resolve().parent
    runtime_dir = exe_dir / "runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("VOICECODE_RUNTIME_DIR", str(runtime_dir))
    os.environ.setdefault("VOICECODE_MODEL_DIR", str(runtime_dir / "models"))
    os.environ.setdefault("VOICECODE_DEP_DIR", str(runtime_dir / "dependencies"))

    # Make the bundled NVIDIA CUDA runtime discoverable. CTranslate2 delay-loads
    # cuBLAS and the CUDA runtime (cublas64_12.dll, cublasLt64_12.dll,
    # cudart64_12.dll) only when GPU inference starts, using the standard DLL
    # search order. That order includes PATH but not directories registered
    # solely through os.add_dll_directory(), so prepend the bundle directory to
    # PATH before any inference library is imported.
    nvidia_bin = Path(getattr(sys, "_MEIPASS", exe_dir)) / "nvidia" / "bin"
    if nvidia_bin.is_dir():
        os.environ["PATH"] = str(nvidia_bin) + os.pathsep + os.environ.get("PATH", "")
        with contextlib.suppress(AttributeError, OSError):
            os.add_dll_directory(str(nvidia_bin))
