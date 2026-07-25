"""Runtime hook that reserves a writable runtime directory beside VoiceCode.exe."""

from __future__ import annotations

import os
from pathlib import Path
import sys


if getattr(sys, "frozen", False):
    runtime_dir = Path(sys.executable).resolve().parent / "runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("VOICECODE_RUNTIME_DIR", str(runtime_dir))
    os.environ.setdefault("VOICECODE_MODEL_DIR", str(runtime_dir / "models"))
    os.environ.setdefault("VOICECODE_DEP_DIR", str(runtime_dir / "dependencies"))
