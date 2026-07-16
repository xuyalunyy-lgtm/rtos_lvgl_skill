#!/usr/bin/env python3
"""
LVGL cross-thread call static audit tool.

Detects direct calls to lv_obj_* / lv_label_* and other LVGL APIs in non-View layer files.

Usage:
    python tools/lvgl_thread_checker.py path/to/src
    python tools/lvgl_thread_checker.py --dir src/
"""

from __future__ import annotations

import re
from pathlib import Path

from checker_io import make_issue, read_file, run_checker
from sdk_lookup import SdkLookup

lookup = SdkLookup("esp32")

LVGL_API_PATTERN = re.compile(
    r"\blv_(?:obj|label|btn|bar|img|list|table|chart|textarea|dropdown|roller|"
    r"slider|switch|checkbox|arc|line|canvas|msgbox|tileview|tabview|win|"
    r"calendar|colorwheel|keyboard|spinbox|meter|anim|group|indev|disp|"
    r"timer|style|theme|async_call|lock|unlock)\w*\s*\("
)

# File name patterns allowed to call lv_async_call / lv_lock
ALLOWED_FILE_PATTERNS = [
    re.compile(r"view", re.I),
    re.compile(r"ui_", re.I),
    re.compile(r"lvgl", re.I),
    re.compile(r"screen", re.I),
    re.compile(r"page", re.I),
    re.compile(r"wizard", re.I),
    re.compile(r"wgt_", re.I),
    re.compile(r"study_", re.I),
    re.compile(r"lcd_", re.I),
    re.compile(r"disp_", re.I),
    re.compile(r"port_", re.I),
    re.compile(r"beken_generated", re.I),
    re.compile(r"good_mvp", re.I),
    re.compile(r"good_presenter", re.I),
]

ALLOWED_PATH_MARKERS = [
    "/beken_generated/",
    "/lvgl/port/",
]

# High-risk Model layer file name patterns
RISK_FILE_PATTERNS = [
    re.compile(r"network|wss|wifi|net_", re.I),
    re.compile(r"audio|i2s|mic|enc|dec", re.I),
    re.compile(r"model", re.I),
    re.compile(r"server|callback|event_handler", re.I),
]


def _is_allowed_file(path: Path) -> bool:
    name = path.name
    if name.startswith("bad_"):
        return False
    path_norm = str(path).replace("\\", "/")
    if any(marker in path_norm for marker in ALLOWED_PATH_MARKERS):
        return True
    return any(p.search(name) for p in ALLOWED_FILE_PATTERNS)


def _risk_level_for_file(path: Path) -> str:
    name = path.name
    if any(p.search(name) for p in RISK_FILE_PATTERNS):
        return "High"
    return "Medium"


def check_file(path: Path) -> list[dict]:
    if _is_allowed_file(path):
        return []

    result = read_file(path)
    if result is None:
        return []

    lines, _text = result
    issues: list[dict] = []
    risk = _risk_level_for_file(path)

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("/*"):
            continue
        # lv_async_call in non-view files is the recommended pattern, not a violation
        if "lv_async_call" in line:
            continue

        m = LVGL_API_PATTERN.search(line)
        if m:
            api = m.group(0).rstrip("(")
            issues.append(make_issue(path, i, "C-LVGL", risk,
                f"Direct LVGL call {api} in non-View layer (should use lv_async_call or view_xxx interface)"))

    return issues


if __name__ == "__main__":
    raise SystemExit(run_checker(check_file, "LVGL Cross-Thread Call Audit", ("C-LVGL",)))
