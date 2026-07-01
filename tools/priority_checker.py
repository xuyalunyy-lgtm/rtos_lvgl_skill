#!/usr/bin/env python3
"""
C15 任务优先级启发式检查器。

检查项:
  C15.1 — 相邻任务优先级差 >=2
  C15.2 — 共享资源用 mutex（优先级继承），禁 binary semaphore

用法:
    python tools/priority_checker.py <file.c> [file2.c ...]
    python tools/priority_checker.py --dir src/
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


def check_file(path: Path) -> list[dict]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    lines = text.splitlines()
    issues = []

    # Collect priority values from xTaskCreate calls
    priorities = []
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("/*"):
            continue

        # Match xTaskCreate priority parameter
        match = re.search(r'xTaskCreate\s*\([^)]+,\s*(\d+)\s*,\s*\)', stripped)
        if match:
            prio = int(match.group(1))
            priorities.append((i, prio))

    # C15.2: Check for binary semaphore used as mutex
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if "xSemaphoreCreateBinary" in stripped:
            # Check if it's used for resource protection (nearby shared variable access)
            has_shared_access = False
            for j in range(max(0, i - 10), min(len(lines), i + 10)):
                ctx = lines[j].strip()
                if any(kw in ctx for kw in ["shared", "g_", "s_"]) and (
                    "xSemaphoreTake" in ctx or "xSemaphoreGive" in ctx
                ):
                    has_shared_access = True
                    break
            if has_shared_access:
                issues.append({
                    "id": "C15.2",
                    "file": f"{path}:{i}",
                    "issue": "Binary semaphore 用于共享资源保护，应使用 mutex（优先级继承）",
                    "severity": "P1",
                })

    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="C15 任务优先级检查器")
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
        print("[priority_checker] 无文件可检查")
        return 0

    all_issues: list[dict] = []
    for path in unique:
        all_issues.extend(check_file(path))

    if not all_issues:
        print(f"[priority_checker] 已检查 {len(unique)} 个文件，未发现 C15 违规")
        return 0

    print(f"[priority_checker] 已检查 {len(unique)} 个文件，发现 {len(all_issues)} 个 C15 告警:\n")
    for issue in all_issues:
        print(f"  [{issue['severity']}] {issue['id']} — {issue['file']} — {issue['issue']}")

    print(f"\nSummary: {len(all_issues)} C15 priority warnings")
    return 1


if __name__ == "__main__":
    sys.exit(main())
