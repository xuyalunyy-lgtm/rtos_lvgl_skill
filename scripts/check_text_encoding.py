#!/usr/bin/env python3
"""Detect common UTF-8/GBK mojibake in human-facing text files."""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
TEXT_SUFFIXES = {".md", ".txt", ".yaml", ".yml"}
SKIP_DIRS = {".git", "archive", "artifacts", "__pycache__", ".pytest_cache"}
MOJIBAKE_MARKERS = (
    "\ufffd",  # replacement character
    "\ufeff",  # visible BOM inside text
    "鈥",
    "馃",
    "锘",
    "锛",
    "銆",
    "鐢",
    "瑙",
    "瀹",
    "杞",
    "绾",
)


def iter_text_files(root: Path, max_files: int = 500) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        if any(part in SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        files.append(path)
        if len(files) >= max_files:
            break
    return sorted(files)


def check_file(path: Path) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        return [f"not valid UTF-8: {exc}"]
    issues: list[str] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        markers = [marker for marker in MOJIBAKE_MARKERS if marker in line]
        if markers:
            preview = line.strip()[:120]
            issues.append(f"line {line_no}: marker(s) {markers!r}: {preview}")
    return issues


def check_root(root: Path) -> list[str]:
    errors: list[str] = []
    for path in iter_text_files(root):
        issues = check_file(path)
        for issue in issues:
            errors.append(f"{path.relative_to(root).as_posix()}: {issue}")
    return errors


def run_self_test() -> int:
    with tempfile.TemporaryDirectory(prefix="encoding-check-") as tmp:
        root = Path(tmp)
        good = root / "good.md"
        bad = root / "bad.md"
        good.write_text("# Good\n\nUse UTF-8 text.\n", encoding="utf-8")
        bad.write_text("# Bad\n\nLVGL 鈥?broken\n", encoding="utf-8")
        good_issues = check_file(good)
        bad_issues = check_file(bad)
        assert not good_issues, good_issues
        assert bad_issues and "鈥" in bad_issues[0], bad_issues
    print("[text-encoding:self-test] all fixtures passed")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Check docs for UTF-8 decode errors and common mojibake markers")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return run_self_test()

    errors = check_root(args.root.resolve())
    if errors:
        print("[text-encoding] failed:")
        for error in errors:
            print(f"  - {error}")
        return 1
    print("[text-encoding] UTF-8 text files OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
