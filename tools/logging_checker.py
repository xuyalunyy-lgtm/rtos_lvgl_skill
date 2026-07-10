#!/usr/bin/env python3
"""
C14 Logging specification heuristic checker.

Checks:
  C14.1 — Bare printf/puts instead of LOG_* macros
  C14.3 — Log calls inside ISR/HAL Callback

Usage:
    python tools/logging_checker.py <file.c> [file2.c ...]
    python tools/logging_checker.py --dir src/
"""

from __future__ import annotations

import re
from pathlib import Path

from checker_io import make_issue, read_file, run_checker

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
    result = read_file(path)
    if result is None:
        return []

    lines, _text = result
    issues: list[dict] = []
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
            context = " in ISR" if in_isr else ""
            cid = "C14.3" if in_isr else "C14.1"
            issues.append(make_issue(path, i, cid, severity, f"Bare printf/puts{context}, should use LOG_* macros"))

    return issues


if __name__ == "__main__":
    raise SystemExit(run_checker(check_file, "C14 Logging Specification Checker", ("C14",)))