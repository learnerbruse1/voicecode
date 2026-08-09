from __future__ import annotations

import logging
import os
import sys
from pathlib import Path


def main() -> None:
    from .runtime import configure_runtime_paths

    configure_runtime_paths()

    package_root = Path(__file__).resolve().parent
    package_static = package_root / "static"
    if package_static.is_dir():
        os.environ.setdefault("VOICECODE_STATIC_DIR", str(package_static))

    from .main import run as run_main

    exit_code = 0 if run_main() else 1
    if getattr(sys, "frozen", False):
        logging.shutdown()
        os._exit(exit_code)
    if exit_code:
        raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
