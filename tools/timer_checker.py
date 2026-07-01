#!/usr/bin/env python3
"""
C16 定时器管理启发式检查器。

检查项:
  C16.1 — 软件定时器回调禁止阻塞
  C16.2 — 动态创建 timer 须有 stop + delete 路径
"""

from __future__ import annotations

import re
from pathlib import Path

from checker_io import make_issue, read_file, run_checker

# Blocking APIs that MUST NOT be in timer callback
BLOCKING_APIS_IN_TIMER = [
    "vTaskDelay",
    "xSemaphoreTake",
    "xQueueReceive",
    "xQueueSend",
    "recv",
    "send",
    "connect",
    "mbedtls_ssl_read",
    "mbedtls_ssl_write",
    "printf",
    "LOG_E",
    "LOG_W",
    "LOG_I",
    "LOG_D",
]


def check_timer_callback_blocking(path: Path, lines: list[str]) -> list[dict]:
    """C16.1 — timer 回调中禁止阻塞操作"""
    issues = []
    in_timer_cb = False
    cb_start_line = 0
    cb_name = ""
    brace_depth = 0

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("/*"):
            continue

        # Detect timer callback (TimerHandle_t parameter)
        cb_match = re.search(
            r"(?:static\s+)?void\s+(\w+)\s*\(\s*TimerHandle_t\s+\w+\s*\)",
            stripped,
        )
        if cb_match:
            in_timer_cb = True
            cb_start_line = i
            cb_name = cb_match.group(1)
            brace_depth = 0
            if "{" in stripped:
                brace_depth = stripped.count("{") - stripped.count("}")
        elif in_timer_cb:
            brace_depth += stripped.count("{") - stripped.count("}")

            # Check for blocking APIs
            for api in BLOCKING_APIS_IN_TIMER:
                if api + "(" in stripped:
                    issues.append(make_issue(
                        path, i, "C16.1", "P0",
                        f"timer 回调 {cb_name} 中调用阻塞 API {api}",
                    ))

            # Timer callback end
            if brace_depth <= 0:
                in_timer_cb = False

    return issues


def check_timer_lifecycle(path: Path, lines: list[str]) -> list[dict]:
    """C16.2 — 动态创建 timer 须有 stop + delete 路径"""
    issues = []
    timer_creates = []
    timer_deletes = []
    timer_stops = []

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("/*"):
            continue

        # Find xTimerCreate calls
        if "xTimerCreate" in stripped:
            # Extract timer variable name
            var_match = re.search(r"(\w+)\s*=\s*xTimerCreate", stripped)
            if var_match:
                timer_creates.append((i, var_match.group(1)))

        # Find xTimerDelete calls
        if "xTimerDelete" in stripped:
            timer_deletes.append(i)

        # Find xTimerStop calls
        if "xTimerStop" in stripped:
            timer_stops.append(i)

    # Check if created timers have delete path
    for create_line, timer_name in timer_creates:
        has_delete = False
        for delete_line in timer_deletes:
            # Check if delete is within 100 lines of create
            if abs(delete_line - create_line) < 100:
                has_delete = True
                break

        if not has_delete:
            issues.append(make_issue(
                path, create_line, "C16.2", "P1",
                f"timer {timer_name} 动态创建但未见 delete 路径",
            ))

    return issues


def check_file(path: Path) -> list[dict]:
    result = read_file(path)
    if result is None:
        return []

    lines, _text = result
    issues: list[dict] = []
    issues.extend(check_timer_callback_blocking(path, lines))
    issues.extend(check_timer_lifecycle(path, lines))
    return issues


if __name__ == "__main__":
    raise SystemExit(run_checker(check_file, "C16 定时器管理检查器", ("C16",)))
