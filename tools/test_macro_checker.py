#!/usr/bin/env python3
"""
C5 测试宏启发式检查器。

检查项:
  C5.2 — 测试宏须在 app_test_config.h 集中定义

用法:
    python tools/test_macro_checker.py <file.c> [file2.c ...]
    python tools/test_macro_checker.py --dir src/
"""

from __future__ import annotations

import re
from pathlib import Path

from checker_io import make_issue, read_file, run_checker


def check_file(path: Path) -> list[dict]:
    result = read_file(path)
    if result is None:
        return []

    lines, text = result
    issues = []

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        match = re.match(r'#\s*if(?:def|ndef)?\s+(APP_TEST_MODE_\w+)', stripped)
        if match and path.name != "app_test_config.h":
            issues.append(make_issue(path, i, "C5.2", "P2",
                f"test macro {match.group(1)} should be in app_test_config.h"))

    return issues


if __name__ == "__main__":
    raise SystemExit(run_checker(check_file, "C5 测试宏检查器", ("C5",), {".c", ".h"}))
