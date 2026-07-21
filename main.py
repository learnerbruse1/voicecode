"""Compatibility wrapper for running VoiceCode from the source tree.

Use ``python -m voicecode`` for the packaged entry point. This file delegates to
``voicecode.main`` so there is only one authoritative desktop implementation.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

_module = importlib.import_module("voicecode.main")
main = _module.main
run = _module.run


if __name__ == "__main__":
    run()
