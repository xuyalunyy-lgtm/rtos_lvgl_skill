#!/usr/bin/env python3
"""
C23 显示驱动安全启发式检查器。

检查项:
  C23.5 — 帧缓冲分配必须检查返回值
  C23.6 — lv_disp_drv_t 必须设置 hor_res/ver_res

用法:
    python tools/display_driver_checker.py <file.c> [file2.c ...]
    python tools/display_driver_checker.py --dir src/
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


def check_framebuffer_alloc(path: Path, lines: list[str]) -> list[dict]:
    """C23.5 — 帧缓冲分配必须检查返回值"""
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
                        issues.append({
                            "id": "C23.5",
                            "file": f"{path}:{i}",
                            "issue": f"帧缓冲 {api} 分配未检查返回值（可能为 NULL）",
                            "severity": "P0",
                        })
                break

    return issues


def check_disp_drv_fields(path: Path, lines: list[str]) -> list[dict]:
    """C23.6 — lv_disp_drv_t 必须设置 hor_res/ver_res"""
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
                    issues.append({
                        "id": "C23.6",
                        "file": f"{path}:{init_start_line}",
                        "issue": "lv_disp_drv_t 未设置 hor_res（渲染区域错误）",
                        "severity": "P1",
                    })
                if not has_ver_res:
                    issues.append({
                        "id": "C23.6",
                        "file": f"{path}:{init_start_line}",
                        "issue": "lv_disp_drv_t 未设置 ver_res（渲染区域错误）",
                        "severity": "P1",
                    })
                if not has_flush_cb:
                    issues.append({
                        "id": "C23.6",
                        "file": f"{path}:{init_start_line}",
                        "issue": "lv_disp_drv_t 未设置 flush_cb（无法刷新显示）",
                        "severity": "P0",
                    })
                if not has_draw_buf:
                    issues.append({
                        "id": "C23.6",
                        "file": f"{path}:{init_start_line}",
                        "issue": "lv_disp_drv_t 未设置 draw_buf（无绘制缓冲）",
                        "severity": "P0",
                    })
                in_disp_drv_init = False

    return issues


def check_file(path: Path) -> list[dict]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    lines = text.splitlines()
    issues = []
    issues.extend(check_framebuffer_alloc(path, lines))
    issues.extend(check_disp_drv_fields(path, lines))
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="C23 显示驱动安全检查器")
    parser.add_argument("files", nargs="*", help="待检查 .c 文件")
    parser.add_argument("--dir", "-d", help="递归检查目录")
    args = parser.parse_args()

    targets: list[Path] = []
    for f in args.files:
        p = Path(f)
        if p.is_file():
            targets.append(p)
        elif p.is_dir():
            targets.extend(sorted(p.rglob("*.c")))

    if args.dir:
        d = Path(args.dir)
        if d.is_dir():
            targets.extend(sorted(d.rglob("*.c")))

    seen: set[Path] = set()
    unique: list[Path] = []
    for t in targets:
        r = t.resolve()
        if r not in seen:
            seen.add(r)
            unique.append(r)

    if not unique:
        print("[display_driver_checker] 无文件可检查")
        return 0

    all_issues: list[dict] = []
    for path in unique:
        all_issues.extend(check_file(path))

    if not all_issues:
        print(f"[display_driver_checker] 已检查 {len(unique)} 个文件，未发现 C23 违规")
        return 0

    print(f"[display_driver_checker] 已检查 {len(unique)} 个文件，发现 {len(all_issues)} 个 C23 告警:\n")
    for issue in all_issues:
        print(f"  [{issue['severity']}] {issue['id']} — {issue['file']} — {issue['issue']}")

    print(f"\nSummary: {len(all_issues)} C23 display-driver warnings")
    return 1


if __name__ == "__main__":
    sys.exit(main())
