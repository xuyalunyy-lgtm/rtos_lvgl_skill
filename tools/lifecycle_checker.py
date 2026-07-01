#!/usr/bin/env python3
"""
C33 生命周期对称检查器。

检查项:
  C33.1 — init/open/start/enable 必须有 stop/disable/close/deinit
  C33.2 — alloc/create/register/attach 必须有 free/delete/unregister/detach

用法:
    python tools/lifecycle_checker.py <file.c> [file2.c ...]
    python tools/lifecycle_checker.py --dir src/
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


# Lifecycle pairs: (acquire_pattern, release_pattern, description)
LIFECYCLE_PAIRS = [
    # C33.1 — init/start/enable pairs
    (r'\b(\w+_init)\s*\(', r'\1_deinit', "init/deinit"),
    (r'\b(\w+_open)\s*\(', r'\1_close', "open/close"),
    (r'\b(\w+_start)\s*\(', r'\1_stop', "start/stop"),
    (r'\b(\w+_enable)\s*\(', r'\1_disable', "enable/disable"),
    (r'\b(\w+_power_on)\s*\(', r'\1_power_off', "power_on/power_off"),
    # C33.2 — alloc/create/register pairs
    (r'\b(\w+_create)\s*\(', r'\1_delete', "create/delete"),
    (r'\b(\w+_register)\s*\(', r'\1_unregister', "register/unregister"),
    (r'\b(\w+_attach)\s*\(', r'\1_detach', "attach/detach"),
    (r'\b(\w+_subscribe)\s*\(', r'\1_unsubscribe', "subscribe/unsubscribe"),
]

# FreeRTOS lifecycle pairs
RTOS_PAIRS = [
    ("xTaskCreate", "vTaskDelete", "task create/delete"),
    ("xSemaphoreCreateMutex", "vSemaphoreDelete", "mutex create/delete"),
    ("xSemaphoreCreateBinary", "vSemaphoreDelete", "semaphore create/delete"),
    ("xQueueCreate", "vQueueDelete", "queue create/delete"),
    ("xTimerCreate", "xTimerDelete", "timer create/delete"),
    ("esp_event_handler_register", "esp_event_handler_unregister", "event handler register/unregister"),
]


def check_file(path: Path) -> list[dict]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    lines = text.splitlines()
    issues = []

    # Check RTOS pairs
    for acquire, release, desc in RTOS_PAIRS:
        acquire_count = sum(1 for line in lines if acquire + "(" in line and not line.strip().startswith("//"))
        release_count = sum(1 for line in lines if release + "(" in line and not line.strip().startswith("//"))

        if acquire_count > 0 and release_count == 0:
            issues.append({
                "id": "C33.2",
                "file": str(path),
                "issue": f"{acquire} 调用 {acquire_count} 次但未见 {release}（{desc} 不对称）",
                "severity": "P0",
            })

    # Check generic lifecycle pairs
    for acquire_pattern, release_desc, desc in LIFECYCLE_PAIRS:
        acquire_matches = []
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("//") or stripped.startswith("/*"):
                continue
            match = re.search(acquire_pattern, stripped)
            if match:
                func_name = match.group(1) if match.lastindex else match.group(0)
                acquire_matches.append((i, func_name))

        if not acquire_matches:
            continue

        # For each unique function name, check if release exists
        seen_funcs = set()
        for line_no, func_name in acquire_matches:
            if func_name in seen_funcs:
                continue
            seen_funcs.add(func_name)

            # Build release pattern from function name
            release_pattern = re.sub(r'_init$', '_deinit', func_name)
            release_pattern = re.sub(r'_open$', '_close', release_pattern)
            release_pattern = re.sub(r'_start$', '_stop', release_pattern)
            release_pattern = re.sub(r'_enable$', '_disable', release_pattern)
            release_pattern = re.sub(r'_create$', '_delete', release_pattern)
            release_pattern = re.sub(r'_register$', '_unregister', release_pattern)

            has_release = any(release_pattern + "(" in line for line in lines)
            if not has_release:
                issues.append({
                    "id": "C33.1" if "init" in func_name or "start" in func_name or "open" in func_name else "C33.2",
                    "file": f"{path}:{line_no}",
                    "issue": f"{func_name}() 调用但未见对应释放函数（{desc} 不对称）",
                    "severity": "P0",
                })

    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="C33 生命周期对称检查器")
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
        print("[lifecycle_checker] 无文件可检查")
        return 0

    all_issues: list[dict] = []
    for path in unique:
        all_issues.extend(check_file(path))

    if not all_issues:
        print(f"[lifecycle_checker] 已检查 {len(unique)} 个文件，未发现 C33 违规")
        return 0

    print(f"[lifecycle_checker] 已检查 {len(unique)} 个文件，发现 {len(all_issues)} 个 C33 告警:\n")
    for issue in all_issues:
        print(f"  [{issue['severity']}] {issue['id']} — {issue['file']} — {issue['issue']}")

    print(f"\nSummary: {len(all_issues)} C33 lifecycle symmetry warnings")
    return 1


if __name__ == "__main__":
    sys.exit(main())
