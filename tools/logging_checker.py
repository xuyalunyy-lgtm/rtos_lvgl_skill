#!/usr/bin/env python3
"""
C14 日志规范启发式检查器。

检查项:
  C14.1 — 裸 printf/puts 而非 LOG_* 宏
  C14.3 — ISR/HAL Callback 中的日志调用

用法:
    python tools/logging_checker.py <file.c> [file2.c ...]
    python tools/logging_checker.py --dir src/
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# ISR function patterns
ISR_PATTERN = re.compile(
    r"(?:void\s+)?(?:\w+_IRQHandler|HAL_\w+_Callback|ISR\w*)\s*\(",
    re.IGNORECASE,
)

# Bare printf/puts (not inside LOG_* wrapper)
PRINTF_PATTERN = re.compile(r"(?<!\w)(?:printf|puts|fprintf\s*\(\s*stderr)\s*\(")

# LOG macro pattern (these are OK)
LOG_PATTERN = re.compile(r"\bLOG_[EWID]\s*\(")


def check_file(path: Path) -> list[dict]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    issues: list[dict] = []
    lines = text.splitlines()
    in_isr = False

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("/*"):
            continue

        # Track ISR context
        if ISR_PATTERN.search(line):
            in_isr = True
        if in_isr and stripped == "}":
            in_isr = False

        # Check for bare printf
        if PRINTF_PATTERN.search(line) and not LOG_PATTERN.search(line):
            severity = "P0" if in_isr else "P1"
            context = "ISR 中" if in_isr else ""
            issues.append({
                "id": "C14.1" if not in_isr else "C14.3",
                "file": f"{path}:{i}",
                "issue": f"裸 printf/puts{context}，应改用 LOG_* 宏",
                "severity": severity,
                "line": stripped,
            })

    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="C14 日志规范检查器")
    parser.add_argument("files", nargs="*", help="待检查 .c 文件")
    parser.add_argument("--dir", "-d", help="递归检查目录")
    args = parser.parse_args()

    targets: list[Path] = []
    for f in args.files:
        p = Path(f)
        if p.is_file():
            targets.append(p)
        elif p.is_dir():
            targets.extend(sorted(p.rglob("*.c")))

    if args.dir:
        d = Path(args.dir)
        if d.is_dir():
            targets.extend(sorted(d.rglob("*.c")))

    seen: set[Path] = set()
    unique: list[Path] = []
    for t in targets:
        r = t.resolve()
        if r not in seen:
            seen.add(r)
            unique.append(r)

    if not unique:
        print("[logging_checker] 无文件可检查")
        return 0

    all_issues: list[dict] = []
    for path in unique:
        all_issues.extend(check_file(path))

    if not all_issues:
        print(f"[logging_checker] 已检查 {len(unique)} 个文件，未发现日志违规")
        return 0

    print(f"[logging_checker] 已检查 {len(unique)} 个文件，发现 {len(all_issues)} 个日志告警:\n")
    for issue in all_issues:
        print(f"  [{issue['severity']}] {issue['id']} — {issue['file']} — {issue['issue']}")
        print(f"    {issue['line']}")

    print(f"\nSummary: {len(all_issues)} C14 logging warnings")
    return 1


if __name__ == "__main__":
    sys.exit(main())