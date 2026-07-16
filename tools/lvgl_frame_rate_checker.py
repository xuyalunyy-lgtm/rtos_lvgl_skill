#!/usr/bin/env python3
"""C23.3 LVGL frame-rate budget checker.

Reports high-confidence patterns that commonly consume the UI frame budget:
  - polling ``lv_timer_handler()`` at 1 ms or faster;
  - forced synchronous refresh with ``lv_refr_now``;
  - invalidating the active screen for a small update;
  - registered flush callbacks that never return their draw buffer to LVGL.

This is a static heuristic. It does not estimate measured FPS or replace target
hardware profiling.
"""
from __future__ import annotations

import re
from pathlib import Path

from checker_io import extract_functions, make_issue, read_file, run_checker, strip_comments

FULL_SCREEN_INVALIDATE = re.compile(r"\blv_obj_invalidate\s*\(\s*lv_scr_act\s*\(", re.IGNORECASE)
FORCED_REFRESH = re.compile(r"\blv_refr_now\s*\(", re.IGNORECASE)
FAST_DELAY = re.compile(
    r"\b(?:vTaskDelay|osDelay)\s*\(\s*(?:pdMS_TO_TICKS\s*\(\s*)?(?:0|1)\s*\)?\s*\)",
    re.IGNORECASE,
)
FLUSH_CALLBACK_ASSIGNMENT = re.compile(
    r"\.\s*flush_cb\s*=\s*&?\s*(?P<name>[A-Za-z_]\w*)\s*;",
    re.IGNORECASE,
)
V9_FLUSH_CALLBACK_ASSIGNMENT = re.compile(
    r"\blv_display_set_flush_cb\s*\(\s*[^,]+,\s*&?\s*(?P<name>[A-Za-z_]\w*)\s*\)",
    re.IGNORECASE,
)
FLUSH_READY = re.compile(r"\blv_(?:disp|display)_flush_ready\s*\(", re.IGNORECASE)
ASYNC_FLUSH_READY_ANNOTATION = "LVGL_ASYNC_FLUSH_READY"


def _next_delay_is_too_fast(lines: list[str], start: int) -> bool:
    """Look only at the local UI-loop tail after lv_timer_handler()."""
    for line in lines[start + 1 : start + 5]:
        code = strip_comments(line)
        if FAST_DELAY.search(code):
            return True
        if ";" in code and ("vTaskDelay" in code or "osDelay" in code):
            return False
    return False


def _registered_flush_callbacks(code: str) -> set[str]:
    """Return v8/v9 flush callback names registered in this source file."""
    callbacks = {match.group("name") for match in FLUSH_CALLBACK_ASSIGNMENT.finditer(code)}
    callbacks.update(match.group("name") for match in V9_FLUSH_CALLBACK_ASSIGNMENT.finditer(code))
    return callbacks


def _has_async_flush_annotation(lines: list[str], func_line: int, body: str) -> bool:
    """Allow cross-file DMA completion only when its ownership is explicit."""
    start = max(0, func_line - 2)
    end = min(len(lines), func_line + body.count("\n") + 3)
    return ASYNC_FLUSH_READY_ANNOTATION in "\n".join(lines[start:end])


def check_flush_completion(path: Path, lines: list[str], text: str) -> list[dict]:
    """Ensure locally-defined, registered flush callbacks release draw buffers."""
    code = strip_comments(text)
    callbacks = _registered_flush_callbacks(code)
    if not callbacks:
        return []

    functions = {func.name: func for func in extract_functions(code)}
    issues: list[dict] = []
    for name in sorted(callbacks):
        func = functions.get(name)
        if func is None or FLUSH_READY.search(func.body):
            continue
        if _has_async_flush_annotation(lines, func.line, func.body):
            continue
        issues.append(make_issue(
            path, func.line, "C23.6", "P0",
            f"{name} is registered as an LVGL flush callback but never signals draw-buffer completion; "
            "call lv_disp_flush_ready/lv_display_flush_ready only after the transfer is safe, or document the async completion owner",
        ))
    return issues


def check_file(path: Path) -> list[dict]:
    result = read_file(path)
    if result is None:
        return []
    lines, text = result
    issues: list[dict] = []

    for index, line in enumerate(lines):
        code = strip_comments(line)
        line_no = index + 1
        if FULL_SCREEN_INVALIDATE.search(code):
            issues.append(make_issue(
                path, line_no, "C23.3", "P1",
                "full-screen lv_obj_invalidate(lv_scr_act()) can exhaust the UI frame budget; invalidate the changed object or area",
            ))
        if FORCED_REFRESH.search(code):
            issues.append(make_issue(
                path, line_no, "C23.3", "P1",
                "lv_refr_now forces a synchronous refresh; keep refresh scheduling inside the normal LVGL timer cadence",
            ))
        if "lv_timer_handler" in code and _next_delay_is_too_fast(lines, index):
            issues.append(make_issue(
                path, line_no, "C23.3", "P1",
                "lv_timer_handler() is followed by a 0-1 ms delay; use the returned timeout or a panel-budgeted cadence",
            ))
    issues.extend(check_flush_completion(path, lines, text))
    return issues


if __name__ == "__main__":
    raise SystemExit(run_checker(check_file, "C23.3 LVGL frame-rate budget checker", ("C23",)))
