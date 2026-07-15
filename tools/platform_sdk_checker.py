#!/usr/bin/env python3
"""Platform-specific SDK checks for STM32, JL, and BK projects.

The checker intentionally covers only SDK contracts with a clear local signal:
STM32 HAL callbacks must not delay, and JL/BK applications should use their
SDK task wrappers rather than raw FreeRTOS task APIs.  It is inactive unless
``SDK_PLATFORM`` names one of those targets.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

from checker_io import extract_functions, make_issue, read_file, run_checker, strip_comments

RAW_TASK_API_RE = re.compile(r"\b(?:xTaskCreate|vTaskDelay|vTaskDelayUntil)\s*\(")
STM32_ISR_NAME_RE = re.compile(r"(?:IRQHandler|Callback)")


def check_file(path: Path) -> list[dict]:
    result = read_file(path)
    if result is None:
        return []
    _lines, raw = result
    code = strip_comments(raw)
    platform = os.environ.get("SDK_PLATFORM", "").lower()
    issues: list[dict] = []

    if platform == "stm32":
        for function in extract_functions(code):
            if STM32_ISR_NAME_RE.search(function.name) and re.search(r"\bHAL_Delay\s*\(", function.body):
                issues.append(make_issue(
                    path, function.line, "C4.9", "P0",
                    f"[{function.name}] HAL_Delay in HAL/IRQ callback can block interrupt progress; defer work to a task",
                ))
    elif platform == "jl":
        for match in RAW_TASK_API_RE.finditer(code):
            issues.append(make_issue(
                path, code.count("\n", 0, match.start()) + 1, "C30.6", "P1",
                "JL application uses raw FreeRTOS task API; use thread_fork/os_task_create and register task metadata",
            ))
    elif platform == "bk":
        for match in RAW_TASK_API_RE.finditer(code):
            issues.append(make_issue(
                path, code.count("\n", 0, match.start()) + 1, "C30.7", "P1",
                "BK application uses raw FreeRTOS task API; use rtos_create_thread/rtos_delay_milliseconds",
            ))
    return issues


if __name__ == "__main__":
    raise SystemExit(run_checker(check_file, "STM32/JL/BK platform SDK checker", ("C4", "C30")))
