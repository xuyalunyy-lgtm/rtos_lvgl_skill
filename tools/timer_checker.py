#!/usr/bin/env python3
"""
C16 定时器管理启发式检查器。

检查项:
  C16.1 — 软件定时器回调禁止阻塞
  C16.2 — 动态创建 timer 须有 stop + delete 路径

用法:
    python tools/timer_checker.py <file.c> [file2.c ...]
    python tools/timer_checker.py --dir src/
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Blocking APIs that MUST NOT be in timer callback
BLOCKING_APIS_IN_TIMER = [
    "vTaskDelay",
    "xSemaphoreTake",
    "xQueueReceive",
    "xQueueSend",
    "recv",
    "send",
    "connect",
    "mbedtls_ssl_read",
    "mbedtls_ssl_write",
    "printf",
    "LOG_E",
    "LOG_W",
    "LOG_I",
    "LOG_D",
]


def check_timer_callback_blocking(path: Path, lines: list[str]) -> list[dict]:
    """C16.1 — timer 回调中禁止阻塞操作"""
    issues = []
    in_timer_cb = False
    cb_start_line = 0
    cb_name = ""
    brace_depth = 0

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("/*"):
            continue

        # Detect timer callback (TimerHandle_t parameter)
        cb_match = re.search(
            r"(?:static\s+)?void\s+(\w+)\s*\(\s*TimerHandle_t\s+\w+\s*\)",
            stripped,
        )
        if cb_match:
            in_timer_cb = True
            cb_start_line = i
            cb_name = cb_match.group(1)
            brace_depth = 0
            if "{" in stripped:
                brace_depth = stripped.count("{") - stripped.count("}")
        elif in_timer_cb:
            brace_depth += stripped.count("{") - stripped.count("}")

            # Check for blocking APIs
            for api in BLOCKING_APIS_IN_TIMER:
                if api + "(" in stripped:
                    issues.append({
                        "id": "C16.1",
                        "file": f"{path}:{i}",
                        "issue": f"timer 回调 {cb_name} 中调用阻塞 API {api}",
                        "severity": "P0",
                    })

            # Timer callback end
            if brace_depth <= 0:
                in_timer_cb = False

    return issues


def check_timer_lifecycle(path: Path, lines: list[str]) -> list[dict]:
    """C16.2 — 动态创建 timer 须有 stop + delete 路径"""
    issues = []
    timer_creates = []
    timer_deletes = []
    timer_stops = []

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("/*"):
            continue

        # Find xTimerCreate calls
        if "xTimerCreate" in stripped:
            # Extract timer variable name
            var_match = re.search(r"(\w+)\s*=\s*xTimerCreate", stripped)
            if var_match:
                timer_creates.append((i, var_match.group(1)))

        # Find xTimerDelete calls
        if "xTimerDelete" in stripped:
            timer_deletes.append(i)

        # Find xTimerStop calls
        if "xTimerStop" in stripped:
            timer_stops.append(i)

    # Check if created timers have delete path
    for create_line, timer_name in timer_creates:
        has_delete = False
        for delete_line in timer_deletes:
            # Check if delete is within 100 lines of create
            if abs(delete_line - create_line) < 100:
                has_delete = True
                break

        if not has_delete:
            issues.append({
                "id": "C16.2",
                "file": f"{path}:{create_line}",
                "issue": f"timer {timer_name} 动态创建但未见 delete 路径",
                "severity": "P1",
            })

    return issues


def check_file(path: Path) -> list[dict]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    lines = text.splitlines()
    issues = []
    issues.extend(check_timer_callback_blocking(path, lines))
    issues.extend(check_timer_lifecycle(path, lines))
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="C16 定时器管理检查器")
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
        print("[timer_checker] 无文件可检查")
        return 0

    all_issues: list[dict] = []
    for path in unique:
        all_issues.extend(check_file(path))

    if not all_issues:
        print(f"[timer_checker] 已检查 {len(unique)} 个文件，未发现 C16 违规")
        return 0

    print(f"[timer_checker] 已检查 {len(unique)} 个文件，发现 {len(all_issues)} 个 C16 告警:\n")
    for issue in all_issues:
        print(f"  [{issue['severity']}] {issue['id']} — {issue['file']} — {issue['issue']}")

    print(f"\nSummary: {len(all_issues)} C16 timer warnings")
    return 1


if __name__ == "__main__":
    sys.exit(main())
