#!/usr/bin/env python3
"""C23.3 LVGL frame-rate budget checker.

Reports high-confidence patterns that commonly consume the UI frame budget:
  - polling ``lv_timer_handler()`` at 1 ms or faster;
  - forced synchronous refresh with ``lv_refr_now``;
  - invalidating the active screen for a small update.

This is a static heuristic. It does not estimate measured FPS or replace target
hardware profiling.
"""
from __future__ import annotations

import re
from pathlib import Path

from checker_io import make_issue, read_file, run_checker, strip_comments

FULL_SCREEN_INVALIDATE = re.compile(r"\blv_obj_invalidate\s*\(\s*lv_scr_act\s*\(", re.IGNORECASE)
FORCED_REFRESH = re.compile(r"\blv_refr_now\s*\(", re.IGNORECASE)
FAST_DELAY = re.compile(
    r"\b(?:vTaskDelay|osDelay)\s*\(\s*(?:pdMS_TO_TICKS\s*\(\s*)?(?:0|1)\s*\)?\s*\)",
    re.IGNORECASE,
)


def _next_delay_is_too_fast(lines: list[str], start: int) -> bool:
    """Look only at the local UI-loop tail after lv_timer_handler()."""
    for line in lines[start + 1 : start + 5]:
        code = strip_comments(line)
        if FAST_DELAY.search(code):
            return True
        if ";" in code and ("vTaskDelay" in code or "osDelay" in code):
            return False
    return False


def check_file(path: Path) -> list[dict]:
    result = read_file(path)
    if result is None:
        return []
    lines, _text = result
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
    return issues


if __name__ == "__main__":
    raise SystemExit(run_checker(check_file, "C23.3 LVGL frame-rate budget checker", ("C23",)))
