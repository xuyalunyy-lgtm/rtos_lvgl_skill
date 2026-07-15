#!/usr/bin/env python3
"""Zephyr-specific devicetree, Kconfig, and work queue checker."""
from __future__ import annotations

import os
import re
from pathlib import Path

from checker_io import extract_functions, make_issue, read_file, run_checker, strip_comments

DEVICE_GET_RE = re.compile(r"\bDEVICE_DT_GET(?:_OR_NULL)?\s*\(")
KCONFIG_DEFINE_RE = re.compile(r"^\s*#\s*(?:define|undef)\s+CONFIG_[A-Za-z0-9_]+\b", re.MULTILINE)
WORK_DEFINE_RE = re.compile(
    r"\bK_WORK(?:_DELAYABLE)?_DEFINE\s*\(\s*([A-Za-z_]\w*)\s*,\s*([A-Za-z_]\w*)",
)
BLOCKING_WORK_RE = re.compile(
    r"\bk_(?:sleep|msleep)\s*\(|"
    r"\bk_(?:sem_take|mutex_lock|msgq_get)\s*\([^;]*\bK_FOREVER\b",
)


def check_file(path: Path) -> list[dict]:
    if os.environ.get("SDK_PLATFORM", "").lower() != "zephyr":
        return []
    result = read_file(path)
    if result is None:
        return []
    _lines, raw = result
    code = strip_comments(raw)
    issues: list[dict] = []

    for match in KCONFIG_DEFINE_RE.finditer(code):
        issues.append(make_issue(
            path, code.count("\n", 0, match.start()) + 1, "C39.6", "P1",
            "application source must not define/undef CONFIG_*; own the symbol in Kconfig/prj.conf",
        ))

    functions = {function.name: function for function in extract_functions(code)}
    for function in functions.values():
        if DEVICE_GET_RE.search(function.body) and not re.search(r"\bdevice_is_ready\s*\(", function.body):
            issues.append(make_issue(
                path, function.line, "C18.7", "P0",
                f"[{function.name}] DEVICE_DT_GET result is used without device_is_ready()",
            ))

    for _work_name, handler_name in WORK_DEFINE_RE.findall(code):
        handler = functions.get(handler_name)
        if handler and BLOCKING_WORK_RE.search(handler.body):
            issues.append(make_issue(
                path, handler.line, "C31.6", "P1",
                f"[{handler_name}] shared Zephyr workqueue handler performs blocking wait/sleep; use a dedicated thread or delayable work",
            ))
    return issues


if __name__ == "__main__":
    raise SystemExit(run_checker(check_file, "Zephyr devicetree/Kconfig/workqueue checker", ("C18", "C31", "C39")))
