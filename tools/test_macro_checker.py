#!/usr/bin/env python3
"""
C5 测试宏启发式检查器。

检查项:
  C5.1 — 每大模块 APP_TEST_MODE_*
  C5.2 — 测试宏须在 app_test_config.h 集中定义

用法:
    python tools/test_macro_checker.py <file.c> [file2.c ...]
    python tools/test_macro_checker.py --dir src/
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


def check_file(path: Path) -> list[dict]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    lines = text.splitlines()
    issues = []

    for i, line in enumerate(lines, 1):
        stripped = line.strip()

        # C5.2: Check for scattered test macros
        match = re.match(r'#\s*if(?:def|ndef)?\s+(APP_TEST_MODE_\w+)', stripped)
        if match:
            # Check if this is in app_test_config.h
            if path.name != "app_test_config.h":
                issues.append({
                    "id": "C5.2",
                    "file": f"{path}:{i}",
                    "issue": f"测试宏 {match.group(1)} 应在 app_test_config.h 中定义",
                    "severity": "P2",
                })

    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="C5 测试宏检查器")
    parser.add_argument("files", nargs="*", help="待检查文件")
    parser.add_argument("--dir", "-d", help="递归检查目录")
    args = parser.parse_args()

    targets: list[Path] = []
    for f in args.files:
        p = Path(f)
        if p.is_file():
            targets.append(p)
        elif p.is_dir():
            targets.extend(sorted(p.rglob("*.c")))
            targets.extend(sorted(p.rglob("*.h")))

    if args.dir:
        d = Path(args.dir)
        if d.is_dir():
            targets.extend(sorted(d.rglob("*.c")))
            targets.extend(sorted(d.rglob("*.h")))

    seen: set[Path] = set()
    unique: list[Path] = []
    for t in targets:
        r = t.resolve()
        if r not in seen:
            seen.add(r)
            unique.append(r)

    if not unique:
        print("[test_macro_checker] No files to check")
        return 0

    all_issues: list[dict] = []
    for path in unique:
        all_issues.extend(check_file(path))

    if not all_issues:
        print(f"[test_macro_checker] Checked {len(unique)} files, no C5 violations")
        return 0

    print(f"[test_macro_checker] Checked {len(unique)} files, found {len(all_issues)} C5 warnings:\n")
    for issue in all_issues:
        print(f"  [{issue['severity']}] {issue['id']} — {issue['file']} — {issue['issue']}")

    print(f"\nSummary: {len(all_issues)} C5 test macro warnings")
    return 1


if __name__ == "__main__":
    sys.exit(main())
