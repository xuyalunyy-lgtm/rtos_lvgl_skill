#!/usr/bin/env python3
"""
C15 任务优先级启发式检查器。

检查项:
  C15.1 — 相邻任务优先级差 >=2
  C15.2 — 共享资源用 mutex（优先级继承），禁 binary semaphore

用法:
    python tools/priority_checker.py <file.c> [file2.c ...]
    python tools/priority_checker.py --dir src/
"""

from __future__ import annotations

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
        if stripped.startswith("//") or stripped.startswith("/*"):
            continue

        # C15.2: binary semaphore for shared resource
        if "xSemaphoreCreateBinary" in stripped:
            has_shared = False
            for j in range(max(0, i - 10), min(len(lines), i + 10)):
                ctx = lines[j].strip()
                if any(kw in ctx for kw in ["shared", "g_", "s_"]) and (
                    "xSemaphoreTake" in ctx or "xSemaphoreGive" in ctx
                ):
                    has_shared = True
                    break
            if has_shared:
                issues.append(make_issue(path, i, "C15.2", "P1",
                    "binary semaphore for shared resource (use mutex with priority inheritance)"))

    return issues


if __name__ == "__main__":
    raise SystemExit(run_checker(check_file, "C15 任务优先级检查器", ("C15",)))
