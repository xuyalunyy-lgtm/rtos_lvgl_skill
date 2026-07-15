#!/usr/bin/env python3
"""Detect FreeRTOS and Zephyr native API mixing inside one module function."""
from __future__ import annotations

import re
from pathlib import Path

from checker_io import extract_functions, make_issue, read_file, run_checker, strip_comments

FREERTOS_RE = re.compile(
    r"\b(?:xTaskCreate|vTaskDelete|vTaskDelay(?:Until)?|xQueue(?:Send|Receive)|"
    r"xSemaphore(?:Take|Give)|xTimer(?:Create|Start|Stop))\s*\(",
)
ZEPHYR_RE = re.compile(
    r"\b(?:k_thread_create|k_thread_abort|k_(?:m)?sleep|k_msgq_(?:put|get)|"
    r"k_sem_(?:take|give)|k_mutex_(?:lock|unlock)|k_timer_(?:start|stop))\s*\(",
)


def check_file(path: Path) -> list[dict]:
    result = read_file(path)
    if result is None:
        return []
    _lines, raw = result
    code = strip_comments(raw)
    issues: list[dict] = []
    for function in extract_functions(code):
        if "RTOS_NATIVE_BRIDGE" in function.body:
            continue
        if FREERTOS_RE.search(function.body) and ZEPHYR_RE.search(function.body):
            issues.append(make_issue(
                path, function.line, "C29.12", "P1",
                f"[{function.name}] mixes FreeRTOS and Zephyr native APIs; route through the RTOS abstraction or annotate a narrow RTOS_NATIVE_BRIDGE",
            ))
    return issues


if __name__ == "__main__":
    raise SystemExit(run_checker(check_file, "FreeRTOS/Zephyr abstraction checker", ("C29",)))
