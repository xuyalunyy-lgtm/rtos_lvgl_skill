#!/usr/bin/env python3
"""
C32 可观测性优先启发式检查器。

检查项:
  C32.1 — 关键模块必须暴露 state、last_error、last_error_line
  C32.2 — 关键链路必须计数 timeout/drop/retry/reconnect/overflow/underrun

用法:
    python tools/observability_checker.py <file.c> [file2.c ...]
    python tools/observability_checker.py --dir src/
"""

from __future__ import annotations

import re
from pathlib import Path

from checker_io import line_at, make_issue, read_file, run_checker, strip_comments


DISPLAY_RUNTIME = re.compile(
    r"\b(?:lv_timer_handler|lv_(?:disp|display)_flush_ready)\s*\(|\b[A-Za-z_]\w*flush_cb\s*\(",
    re.IGNORECASE,
)
DISPLAY_TIMING_METRIC = re.compile(
    r"\b(?:flush|render|frame)_(?:max|last|time|latency|ms|p95)(?:_(?:ms|time|latency))?\b"
    r"|\b(?:max|last)_(?:flush|render|frame)_(?:ms|time|latency)\b",
    re.IGNORECASE,
)
EXTERNAL_DISPLAY_TELEMETRY = "LVGL_PERF_TELEMETRY_EXTERNAL"


def check_file(path: Path) -> list[dict]:
    result = read_file(path)
    if result is None:
        return []

    lines, text = result
    issues = []

    in_struct = False
    struct_fields = []
    brace_depth = 0

    for i, line in enumerate(lines, 1):
        stripped = line.strip()

        if re.match(r'typedef\s+struct\s*\{', stripped):
            in_struct = True
            struct_fields = []
            brace_depth = 1
            continue

        if in_struct:
            brace_depth += stripped.count("{") - stripped.count("}")
            if brace_depth <= 0:
                in_struct = False
                if any(ind in " ".join(struct_fields).lower() for ind in ["state", "error", "count"]):
                    has_error = any("error" in f.lower() for f in struct_fields)
                    has_state = any("state" in f.lower() or "status" in f.lower() for f in struct_fields)
                    has_count = any("count" in f.lower() for f in struct_fields)

                    if not (has_error and has_state):
                        issues.append(make_issue(path, i, "C32.1", "P1",
                            "status struct missing last_error or state field"))
                    if not has_count:
                        issues.append(make_issue(path, i, "C32.2", "P1",
                            "status struct missing timeout/drop/retry counters"))
                continue

            field_match = re.match(r'\w+\s+(\w+)\s*;', stripped)
            if field_match:
                struct_fields.append(field_match.group(1))

    runtime_code = strip_comments(text)
    display_runtime = DISPLAY_RUNTIME.search(runtime_code)
    if display_runtime and not DISPLAY_TIMING_METRIC.search(runtime_code) and EXTERNAL_DISPLAY_TELEMETRY not in text:
        issues.append(make_issue(
            path, line_at(runtime_code, display_runtime.start()), "C32.4", "P2",
            "LVGL render/flush path has no visible frame, render, or flush timing metric; add a max/last duration or document the external telemetry owner",
        ))

    return issues


if __name__ == "__main__":
    raise SystemExit(run_checker(check_file, "C32 可观测性检查器", ("C32",)))
