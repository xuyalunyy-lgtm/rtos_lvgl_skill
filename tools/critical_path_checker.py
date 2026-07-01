#!/usr/bin/env python3
"""
C35 关键路径预算表启发式检查器。

检查项:
  C35.2 — 每个关键阶段必须声明 owner、timeout、fallback 和 metric

用法:
    python tools/critical_path_checker.py <file.c> [file2.c ...]
    python tools/critical_path_checker.py --dir src/
"""

from __future__ import annotations

import re
from pathlib import Path

from checker_io import make_issue, read_file, run_checker

CRITICAL_FUNCS = ['boot', 'startup', 'init', 'connect', 'handshake',
                  'audio', 'video', 'display', 'ota', 'upgrade', 'sleep', 'wakeup']


def check_file(path: Path) -> list[dict]:
    result = read_file(path)
    if result is None:
        return []

    lines, text = result
    issues = []

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("/*"):
            continue

        if "vTaskDelay" in stripped and "portMAX_DELAY" in stripped:
            func_ctx = ""
            for j in range(max(0, i - 20), i):
                m = re.match(r'^(?:static\s+)?(?:void|int|esp_err_t|bool)\s+(\w+)\s*\(', lines[j].strip())
                if m:
                    func_ctx = m.group(1)
                    break

            is_critical = any(pat in func_ctx for pat in CRITICAL_FUNCS)
            if is_critical:
                issues.append(make_issue(path, i, "C35.2", "P0",
                    f"vTaskDelay(portMAX_DELAY) in critical path {func_ctx}()"))
            else:
                issues.append(make_issue(path, i, "C35.2", "P1",
                    "vTaskDelay(portMAX_DELAY) without deadline/fallback"))

    return issues


if __name__ == "__main__":
    raise SystemExit(run_checker(check_file, "C35 关键路径检查器", ("C35",)))
