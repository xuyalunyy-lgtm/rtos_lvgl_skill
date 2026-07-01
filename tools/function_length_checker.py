#!/usr/bin/env python3
"""
C11.5 函数长度启发式检查器。

检查项:
  C11.5 — 单函数 ≤80 行，超限须拆分或注释说明原因

用法:
    python tools/function_length_checker.py <file.c> [file2.c ...]
    python tools/function_length_checker.py --dir src/
"""

from __future__ import annotations

from pathlib import Path

from checker_io import extract_functions, make_issue, read_file, run_checker, strip_comments

DEFAULT_MAX_LINES = 80


def check_file(path: Path) -> list[dict]:
    """Check a single .c/.h file for functions exceeding max_lines."""
    result = read_file(path)
    if result is None:
        return []

    _lines, text = result
    clean = strip_comments(text)
    issues: list[dict] = []

    for func in extract_functions(clean):
        func_length = len(func.body.splitlines())
        if func_length > DEFAULT_MAX_LINES:
            issues.append(make_issue(path, func.line, "C11.5", "P1",
                f"函数 {func.name}() 共 {func_length} 行（上限 {DEFAULT_MAX_LINES}）"))

    return issues


if __name__ == "__main__":
    raise SystemExit(run_checker(check_file, "C11.5 函数长度检查器", ("C11.5",)))