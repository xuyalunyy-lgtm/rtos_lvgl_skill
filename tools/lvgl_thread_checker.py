#!/usr/bin/env python3
"""
LVGL 跨线程调用静态审查工具。

检测非 View 层文件中对 lv_obj_* / lv_label_* 等 LVGL API 的直接调用。

用法:
    python tools/lvgl_thread_checker.py path/to/src
    python tools/lvgl_thread_checker.py --dir src/
"""

from __future__ import annotations

import re
from pathlib import Path

from checker_io import make_issue, read_file, run_checker

LVGL_API_PATTERN = re.compile(
    r"\blv_(?:obj|label|btn|bar|img|list|table|chart|textarea|dropdown|roller|"
    r"slider|switch|checkbox|arc|line|canvas|msgbox|tileview|tabview|win|"
    r"calendar|colorwheel|keyboard|spinbox|meter|anim|group|indev|disp|"
    r"timer|style|theme|async_call|lock|unlock)\w*\s*\("
)

# 允许调用 lv_async_call / lv_lock 的文件名模式
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
    "/lvgl_ui/",
    "/beken_generated/",
    "/lvgl/port/",
]

# 高风险的 Model 层文件名模式
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
        return "高"
    return "中"


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
        # lv_async_call 在非 view 文件中是推荐写法，不算违规
        if "lv_async_call" in line:
            continue

        m = LVGL_API_PATTERN.search(line)
        if m:
            api = m.group(0).rstrip("(")
            issues.append(make_issue(path, i, "C-LVGL", risk,
                f"非 View 层 LVGL 直接调用 {api}（应改为 lv_async_call 或 view_xxx 接口）"))

    return issues


if __name__ == "__main__":
    raise SystemExit(run_checker(check_file, "LVGL 跨线程调用审查", ("C-LVGL",)))
