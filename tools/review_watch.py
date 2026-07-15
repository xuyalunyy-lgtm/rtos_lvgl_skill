#!/usr/bin/env python3
"""Poll a source tree and rerun ``run_review`` for saved C/C++ files."""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

SOURCE_SUFFIXES = {".c", ".h", ".cc", ".cpp", ".hpp"}


def snapshot(root: Path) -> dict[Path, tuple[int, int]]:
    return {
        path: (path.stat().st_mtime_ns, path.stat().st_size)
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in SOURCE_SUFFIXES
    }


def without_directory_args(argv: list[str]) -> list[str]:
    result: list[str] = []
    index = 0
    while index < len(argv):
        token = argv[index]
        if token in {"--dir", "-d"}:
            index += 2
            continue
        if token.startswith("--dir="):
            index += 1
            continue
        result.append(token)
        index += 1
    return result


def run_review(arguments: list[str]) -> int:
    return subprocess.run([sys.executable, str(Path(__file__).with_name("run_review.py")), *arguments]).returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--interval", type=float, default=0.75)
    parser.add_argument("--once", action="store_true", help="Run the initial full review once, then exit")
    parser.add_argument("review_args", nargs=argparse.REMAINDER, help="Arguments forwarded to run_review after --")
    args = parser.parse_args()
    if args.interval <= 0:
        parser.error("--interval must be positive")
    root = args.root.resolve()
    if not root.is_dir():
        parser.error(f"watch root does not exist: {root}")
    forwarded = args.review_args[1:] if args.review_args[:1] == ["--"] else args.review_args
    if not forwarded:
        parser.error("supply run_review arguments after --")

    print(f"[watch] initial review: {root}", flush=True)
    last_exit = run_review(forwarded)
    if args.once:
        return last_exit
    previous = snapshot(root)
    incremental = without_directory_args(forwarded)
    print(f"[watch] polling every {args.interval:g}s; press Ctrl+C to stop", flush=True)
    try:
        while True:
            time.sleep(args.interval)
            current = snapshot(root)
            changed = sorted(path for path in set(previous) | set(current) if previous.get(path) != current.get(path) and path in current)
            previous = current
            if not changed:
                continue
            print("[watch] changed: " + ", ".join(str(path) for path in changed), flush=True)
            last_exit = run_review([*(str(path) for path in changed), *incremental])
    except KeyboardInterrupt:
        print("\n[watch] stopped", flush=True)
        return last_exit


if __name__ == "__main__":
    raise SystemExit(main())
