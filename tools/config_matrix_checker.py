#!/usr/bin/env python3
"""
C39 配置矩阵启发式检查器。

检查项:
  C39.3 — #ifdef 必须归类 platform/board/feature/debug，禁止无名散落

用法:
    python tools/config_matrix_checker.py <file.c> [file2.c ...]
    python tools/config_matrix_checker.py --dir src/
"""

from __future__ import annotations

import re
from pathlib import Path

from checker_io import make_issue, read_file, run_checker

KNOWN_PREFIXES = [
    "CONFIG_", "BOARD_", "PLATFORM_", "FEATURE_", "DEBUG_",
    "APP_TEST_MODE_", "SDK_", "__",
]


def check_file(path: Path) -> list[dict]:
    result = read_file(path)
    if result is None:
        return []

    lines, text = result
    issues = []

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        match = re.match(r'#\s*if(?:def|ndef)?\s+(\w+)', stripped)
        if match:
            macro = match.group(1)
            if macro.startswith("__") or macro in ("_H", "H", "TRUE", "FALSE", "NULL"):
                continue
            is_known = any(macro.startswith(p) for p in KNOWN_PREFIXES)
            if not is_known:
                issues.append(make_issue(path, i, "C39.3", "P1",
                    f"#ifdef {macro} not classified as platform/board/feature/debug"))

    return issues


if __name__ == "__main__":
    raise SystemExit(run_checker(check_file, "C39 配置矩阵检查器", ("C39",), {".c", ".h"}))
