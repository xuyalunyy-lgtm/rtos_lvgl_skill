#!/usr/bin/env python3
"""
C11 Coding style heuristic checker.

Checks:
  C11.1 — Filename must not contain Chinese characters or spaces
  C11.5 — Single function <= 80 lines

Usage:
    python tools/coding_style_checker.py <file.c> [file2.c ...]
    python tools/coding_style_checker.py --dir src/
"""

from __future__ import annotations

import re
from pathlib import Path

from checker_io import make_issue, read_file, run_checker


def check_file(path: Path) -> list[dict]:
    issues = []

    # C11.1: filename
    name = path.name
    if re.search(r'[一-鿿]', name):
        issues.append(make_issue(path, 1, "C11.1", "P2", f"filename contains Chinese: {name}"))
    if ' ' in name:
        issues.append(make_issue(path, 1, "C11.1", "P2", f"filename contains space: {name}"))

    result = read_file(path)
    if result is None:
        return issues

    lines, text = result

    # C11.5: function length
    func_start = None
    func_name = ""
    brace_depth = 0

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        match = re.match(
            r'^(?:static\s+)?(?:void|int|esp_err_t|bool|float|double|char|uint\w+|int\w+|size_t|BaseType_t)\s+(\w+)\s*\(',
            stripped
        )
        if match and '{' in stripped:
            func_start = i
            func_name = match.group(1)
            brace_depth = 1
            continue

        if func_start is not None:
            brace_depth += stripped.count('{') - stripped.count('}')
            if brace_depth <= 0:
                length = i - func_start
                if length > 80:
                    issues.append(make_issue(path, func_start, "C11.5", "P1",
                        f"function {func_name} is {length} lines (>80)"))
                func_start = None

    return issues


if __name__ == "__main__":
    raise SystemExit(run_checker(check_file, "C11 Coding style checker", ("C11",), {".c", ".h"}))
