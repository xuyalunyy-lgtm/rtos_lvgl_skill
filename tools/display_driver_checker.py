#!/usr/bin/env python3
"""
C23 display driver safety heuristic checker.

Checks:
  C23.5 — framebuffer allocation must check return value
  C23.6 — lv_disp_drv_t must set hor_res/ver_res

Usage:
    python tools/display_driver_checker.py <file.c> [file2.c ...]
    python tools/display_driver_checker.py --dir src/
"""

from __future__ import annotations

import re
from pathlib import Path

from checker_io import make_issue, read_file, run_checker


def check_framebuffer_alloc(path: Path, lines: list[str]) -> list[dict]:
    """C23.5 — framebuffer allocation must check return value"""
    issues = []
    fb_alloc_apis = [
        "heap_caps_malloc",
        "heap_caps_calloc",
        "malloc",
        "calloc",
        "pvPortMalloc",
    ]

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("/*"):
            continue

        # Look for framebuffer-sized allocations (heuristic: large size or FB-related name)
        is_fb_alloc = False
        for api in fb_alloc_apis:
            if api + "(" not in stripped:
                continue

            # Check if it's framebuffer-related
            if any(kw in stripped.lower() for kw in ["framebuf", "fb_", "draw_buf", "lv_color", "disp_buf"]):
                is_fb_alloc = True
            # Check for large allocation (> 10KB)
            size_match = re.search(r"(\d{5,})", stripped)
            if size_match and int(size_match.group(1)) >= 10000:
                is_fb_alloc = True

            if is_fb_alloc:
                # Check if return value is checked
                var_match = re.search(r"(\w+)\s*=\s*" + re.escape(api), stripped)
                if var_match:
                    var_name = var_match.group(1)
                    checked = False
                    for j in range(i, min(i + 5, len(lines))):
                        next_line = lines[j]
                        if var_name in next_line and (
                            "if" in next_line or "NULL" in next_line or "assert" in next_line
                        ):
                            checked = True
                            break
                    if not checked:
                        issues.append(make_issue(path, i, "C23.5", "P0",
                            f"framebuffer {api} allocation without return value check (may be NULL)"))
                break

    return issues


def check_disp_drv_fields(path: Path, lines: list[str]) -> list[dict]:
    """C23.6 — lv_disp_drv_t must set hor_res/ver_res"""
    issues = []
    in_disp_drv_init = False
    has_hor_res = False
    has_ver_res = False
    has_flush_cb = False
    has_draw_buf = False
    init_start_line = 0

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("/*"):
            continue

        # Detect disp_drv init context
        if "lv_disp_drv_init" in stripped:
            in_disp_drv_init = True
            has_hor_res = False
            has_ver_res = False
            has_flush_cb = False
            has_draw_buf = False
            init_start_line = i

        if in_disp_drv_init:
            if ".hor_res" in stripped:
                has_hor_res = True
            if ".ver_res" in stripped:
                has_ver_res = True
            if ".flush_cb" in stripped:
                has_flush_cb = True
            if ".draw_buf" in stripped:
                has_draw_buf = True

            # End of init block
            if "lv_disp_drv_register" in stripped:
                if not has_hor_res:
                    issues.append(make_issue(path, init_start_line, "C23.6", "P1",
                        "lv_disp_drv_t hor_res not set (render region error)"))
                if not has_ver_res:
                    issues.append(make_issue(path, init_start_line, "C23.6", "P1",
                        "lv_disp_drv_t ver_res not set (render region error)"))
                if not has_flush_cb:
                    issues.append(make_issue(path, init_start_line, "C23.6", "P0",
                        "lv_disp_drv_t flush_cb not set (cannot flush display)"))
                if not has_draw_buf:
                    issues.append(make_issue(path, init_start_line, "C23.6", "P0",
                        "lv_disp_drv_t draw_buf not set (no draw buffer)"))
                in_disp_drv_init = False

    return issues


def check_file(path: Path) -> list[dict]:
    result = read_file(path)
    if result is None:
        return []

    lines, text = result
    issues = []
    issues.extend(check_framebuffer_alloc(path, lines))
    issues.extend(check_disp_drv_fields(path, lines))
    return issues


if __name__ == "__main__":
    raise SystemExit(run_checker(check_file, "C23 display driver safety checker", ("C23",)))
