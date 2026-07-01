#!/usr/bin/env python3
"""
C12 错误处理启发式检查器。

检查项:
  C12.1 — FreeRTOS API 返回值未检查
  C12.2 — pvPortMalloc 未检查即使用

用法:
    python tools/return_check_checker.py <file.c> [file2.c ...]
    python tools/return_check_checker.py --dir src/
"""

from __future__ import annotations

import re
from pathlib import Path

from checker_io import make_issue, read_file, run_checker

# Functions whose return value MUST be checked
CRITICAL_API = [
    "xTaskCreate",
    "xTaskCreateStatic",
    "xQueueCreate",
    "xQueueSend",
    "xQueueReceive",
    "xSemaphoreCreateMutex",
    "xSemaphoreCreateBinary",
    "xSemaphoreTake",
    "pvPortMalloc",
    "pvPortCalloc",
    "xTimerStart",
    "xTimerChangePeriod",
]

# Build pattern: these function calls
CALL_PATTERN = re.compile(
    r"(?:" + "|".join(re.escape(f) for f in CRITICAL_API) + r")\s*\("
)

# Pattern for checking if return is captured
CAPTURE_PATTERN = re.compile(
    r"(?:(?:\w+)\s*=\s*)?(" + "|".join(re.escape(f) for f in CRITICAL_API) + r")\s*\("
)

# NULL check patterns
NULL_CHECK_PATTERN = re.compile(r"(?:!=\s*NULL|==\s*NULL|if\s*\(\s*!\s*\w+|if\s*\(\s*\w+\s*\))")


def check_file(path: Path) -> list[dict]:
    result = read_file(path)
    if result is None:
        return []

    lines, text = result
    issues: list[dict] = []

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        # Skip comments
        if stripped.startswith("//") or stripped.startswith("/*"):
            continue

        # Find API calls
        for api in CRITICAL_API:
            if api + "(" not in stripped:
                continue

            # Check if return is captured (assigned to variable)
            assign_match = re.search(rf"(\w+)\s*=\s*{re.escape(api)}\s*\(", stripped)
            if assign_match:
                # Return is captured, check next few lines for NULL/error check
                var_name = assign_match.group(1)
                checked = False
                for j in range(i, min(i + 5, len(lines))):
                    next_line = lines[j]
                    if var_name in next_line and (
                        "if" in next_line
                        or "NULL" in next_line
                        or "!= pdPASS" in next_line
                        or "== pdPASS" in next_line
                        or "< 0" in next_line
                    ):
                        checked = True
                        break
                if not checked:
                    issues.append(make_issue(
                        path, i, "C12.1", "P0",
                        f"{api} 返回值已赋给 {var_name} 但未检查",
                    ))
            else:
                # Return value discarded entirely
                issues.append(make_issue(
                    path, i, "C12.1", "P0",
                    f"{api} 返回值未检查（直接调用无赋值）",
                ))

    return issues


if __name__ == "__main__":
    raise SystemExit(run_checker(check_file, "C12 错误处理检查器", ("C12",)))