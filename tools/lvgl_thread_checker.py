#!/usr/bin/env python3
"""
LVGL 跨线程调用静态审查工具。

检测非 View 层文件中对 lv_obj_* / lv_label_* 等 LVGL API 的直接调用。

用法:
    python tools/lvgl_thread_checker.py path/to/src
    python tools/lvgl_thread_checker.py network_wss_task.c --allow view
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from checker_io import configure_stdout

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


@dataclass
class Hit:
    file: str
    line_no: int
    api: str
    line_text: str
    risk_level: str


@dataclass
class CheckResult:
    hits: list[Hit] = field(default_factory=list)


def is_allowed_file(path: Path, extra_allow: str | None) -> bool:
    name = path.name
    if name.startswith("bad_"):
        return False
    if extra_allow and extra_allow.lower() in name.lower():
        return True
    path_norm = str(path).replace("\\", "/")
    if any(marker in path_norm for marker in ALLOWED_PATH_MARKERS):
        return True
    return any(p.search(name) for p in ALLOWED_FILE_PATTERNS)


def risk_level_for_file(path: Path) -> str:
    name = path.name
    if any(p.search(name) for p in RISK_FILE_PATTERNS):
        return "高"
    return "中"


def analyze_file(path: Path, extra_allow: str | None) -> CheckResult:
    result = CheckResult()
    if is_allowed_file(path, extra_allow):
        return result

    content = path.read_text(encoding="utf-8", errors="replace")
    lines = content.splitlines()
    risk = risk_level_for_file(path)

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("/*"):
            continue
        # lv_async_call 在非 view 文件中是推荐写法，不算违规
        if "lv_async_call" in line:
            continue

        m = LVGL_API_PATTERN.search(line)
        if m:
            result.hits.append(
                Hit(
                    file=str(path),
                    line_no=i + 1,
                    api=m.group(0).rstrip("("),
                    line_text=stripped[:100],
                    risk_level=risk,
                )
            )

    return result


def format_report(all_hits: list[Hit], scanned: int) -> str:
    out = [
        "=" * 60,
        "LVGL 跨线程调用审查",
        "=" * 60,
        f"扫描文件数: {scanned}",
        f"违规调用数: {len(all_hits)}",
        "",
    ]

    if all_hits:
        out.append("🔴 非 View 层 LVGL 直接调用（应改为 lv_async_call 或 view_xxx 接口）:")
        for h in all_hits:
            out.append(f"  [{h.risk_level}] {h.file}:{h.line_no} — {h.api}")
            out.append(f"      {h.line_text}")
        out.append("")
        out.append("参照: examples/bad_lvgl_cross_thread.c")
        out.append("      examples/good_presenter_consumer.c (view_post_set_text)")
    else:
        out.append("✅ 通过：非 View 文件未检测到 lv_* 直接调用。")

    out.append("")
    out.append("ℹ️  本工具为静态启发式辅助，可能有误报/漏报，不能替代 Code Review。")
    return "\n".join(out)


def main() -> int:
    configure_stdout()
    parser = argparse.ArgumentParser(description="LVGL 跨线程调用审查")
    parser.add_argument("path", help=".c/.h 文件或源码目录")
    parser.add_argument("--allow", help="额外允许的文件名片段")
    args = parser.parse_args()

    root = Path(args.path)
    if not root.exists():
        print(f"错误: 路径不存在: {root}", file=sys.stderr)
        return 1

    files = [root] if root.is_file() else sorted(root.rglob("*.c"))
    all_hits: list[Hit] = []

    for f in files:
        r = analyze_file(f, args.allow)
        all_hits.extend(r.hits)

    print(format_report(all_hits, len(files)))
    return 1 if all_hits else 0


if __name__ == "__main__":
    sys.exit(main())
