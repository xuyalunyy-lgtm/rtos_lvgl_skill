#!/usr/bin/env python3
"""
C24 外设关闭安全启发式检查器。

检查项:
  C24.1 — 异常退出路径必须与正常路径调用相同收尾函数

用法:
    python tools/peripheral_shutdown_checker.py <file.c> [file2.c ...]
    python tools/peripheral_shutdown_checker.py --dir src/
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
    lower = text.lower()
    if not any(kw in lower for kw in ["gpio", "ledc", "i2s", "spi", "pwm", "power", "shutdown", "deinit"]):
        return []

    issues = []

    has_deinit = any(re.search(r'\b\w+_deinit\b', l) or re.search(r'\b\w+_close\b', l) or re.search(r'\b\w+_stop\b', l) for l in lines)
    has_init = any(re.search(r'\b\w+_init\b', l) or re.search(r'\b\w+_open\b', l) or re.search(r'\b\w+_start\b', l) for l in lines)

    if has_init and not has_deinit:
        issues.append(make_issue(path, 1, "C24.1", "P0",
            "has init/start/open but no deinit/stop/close (exception path may skip cleanup)"))

    return issues


if __name__ == "__main__":
    raise SystemExit(run_checker(check_file, "C24 外设关闭安全检查器", ("C24",)))
