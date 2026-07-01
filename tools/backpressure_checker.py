#!/usr/bin/env python3
"""
C37 背压与降级策略启发式检查器。

检查项:
  C37.2 — 满队列禁止无限等待

用法:
    python tools/backpressure_checker.py <file.c> [file2.c ...]
    python tools/backpressure_checker.py --dir src/
"""

from __future__ import annotations

import re
from pathlib import Path

from checker_io import make_issue, read_file, run_checker

QUEUE_SEND_APIS = ["xQueueSend", "xQueueSendToBack", "xQueueSendToFront", "xQueueGenericSend"]
MAX_DELAY_RE = re.compile(r'portMAX_DELAY|WAIT_FOREVER|0xFFFFFFFF')


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

        for api in QUEUE_SEND_APIS:
            if api + "(" in stripped:
                if MAX_DELAY_RE.search(stripped):
                    issues.append(make_issue(path, i, "C37.2", "P0",
                        f"{api} with portMAX_DELAY (blocks forever on full queue)"))
                elif api != "xQueueOverwrite":
                    has_timeout = any(
                        "pdMS_TO_TICKS" in lines[j] or "timeout" in lines[j].lower()
                        for j in range(max(0, i - 3), min(len(lines), i + 2))
                    )
                    if not has_timeout:
                        issues.append(make_issue(path, i, "C37.2", "P1",
                            f"{api} without explicit timeout"))

    return issues


if __name__ == "__main__":
    raise SystemExit(run_checker(check_file, "C37 背压检查器", ("C37",)))
