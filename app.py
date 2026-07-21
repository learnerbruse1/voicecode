"""Compatibility wrapper for running VoiceCode from the source tree.

The installable package under :mod:`voicecode` is the authoritative implementation.
This module remains so older commands such as ``python -c "import app; app.start_server()"``
and tests that import ``app`` keep working, including access to internal test hooks.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

_module = importlib.import_module("voicecode.app")
sys.modules[__name__] = _module
