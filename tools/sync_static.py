"""Synchronize the source-tree static mirror from packaged assets."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src" / "voicecode" / "static"
TARGET = ROOT / "static"


def relative_files(root: Path) -> set[Path]:
    return {path.relative_to(root) for path in root.rglob("*") if path.is_file()}


def differences() -> list[str]:
    source_files = relative_files(SOURCE)
    target_files = relative_files(TARGET) if TARGET.exists() else set()
    messages = [f"missing mirror file: {path}" for path in sorted(source_files - target_files)]
    messages += [f"unexpected mirror file: {path}" for path in sorted(target_files - source_files)]
    for relative in sorted(source_files & target_files):
        if (SOURCE / relative).read_bytes() != (TARGET / relative).read_bytes():
            messages.append(f"different content: {relative}")
    return messages


def sync() -> None:
    source = SOURCE.resolve()
    target = TARGET.resolve()
    if source == target or ROOT.resolve() not in target.parents:
        raise RuntimeError(f"Unsafe static mirror target: {target}")
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        found = differences()
        if found:
            print("Static mirror is out of date:", file=sys.stderr)
            print("\n".join(found), file=sys.stderr)
            return 1
        print("Static mirror is synchronized.")
        return 0
    sync()
    print(f"Synchronized {SOURCE} -> {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
