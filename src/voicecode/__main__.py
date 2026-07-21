from __future__ import annotations

import os
from pathlib import Path


def main() -> None:
    package_root = Path(__file__).resolve().parent
    package_static = package_root / "static"
    if package_static.is_dir():
        os.environ.setdefault("VOICECODE_STATIC_DIR", str(package_static))

    from .main import main as run_main

    run_main()


if __name__ == "__main__":
    main()
