#!/usr/bin/env python3
"""
C33 生命周期对称检查器。

检查项:
  C33.1 — init/open/start/enable 必须有 stop/disable/close/deinit
  C33.2 — alloc/create/register/attach 必须有 free/delete/unregister/detach

用法:
    python tools/lifecycle_checker.py <file.c> [file2.c ...]
    python tools/lifecycle_checker.py --dir src/
"""

from __future__ import annotations

import re
from pathlib import Path

from checker_io import make_issue, read_file, run_checker

# FreeRTOS lifecycle pairs
RTOS_PAIRS = [
    ("xTaskCreate", "vTaskDelete", "task create/delete"),
    ("xSemaphoreCreateMutex", "vSemaphoreDelete", "mutex create/delete"),
    ("xSemaphoreCreateBinary", "vSemaphoreDelete", "semaphore create/delete"),
    ("xQueueCreate", "vQueueDelete", "queue create/delete"),
    ("xTimerCreate", "xTimerDelete", "timer create/delete"),
    ("esp_event_handler_register", "esp_event_handler_unregister", "event handler register/unregister"),
]


def check_file(path: Path) -> list[dict]:
    result = read_file(path)
    if result is None:
        return []

    lines, text = result
    issues = []

    # Check RTOS pairs
    for acquire, release, desc in RTOS_PAIRS:
        acq_count = sum(1 for l in lines if acquire + "(" in l and not l.strip().startswith("//"))
        rel_count = sum(1 for l in lines if release + "(" in l and not l.strip().startswith("//"))

        if acq_count > 0 and rel_count == 0:
            issues.append(make_issue(path, 1, "C33.2", "P0",
                f"{acq_count}x {acquire} but no {release} ({desc} asymmetry)"))

    # Check generic lifecycle pairs
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("/*"):
            continue

        for pattern, replacement, desc in [
            (r'\b(\w+)_init\s*\(', r'\1_deinit', 'init/deinit'),
            (r'\b(\w+)_open\s*\(', r'\1_close', 'open/close'),
            (r'\b(\w+)_start\s*\(', r'\1_stop', 'start/stop'),
        ]:
            match = re.search(pattern, stripped)
            if match:
                func_name = match.group(0).split("(")[0].strip()
                release_func = re.sub(pattern, replacement, match.group(0)).split("(")[0].strip()
                has_release = any(release_func + "(" in l for l in lines)
                if not has_release:
                    issues.append(make_issue(path, i, "C33.1", "P0",
                        f"{func_name}() called but no {release_func}() ({desc} asymmetry)"))

    return issues


if __name__ == "__main__":
    raise SystemExit(run_checker(check_file, "C33 生命周期对称检查器", ("C33",)))
