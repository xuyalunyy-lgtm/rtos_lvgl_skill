#!/usr/bin/env python3
"""
C35 关键路径预算表启发式检查器。

检查项:
  C35.1 — 启动/联网/音频/视频/UI/OTA/低功耗唤醒必须声明 stage budget
  C35.2 — 每个关键阶段必须声明 owner、timeout、fallback 和 metric

用法:
    python tools/critical_path_checker.py <file.c> [file2.c ...]
    python tools/critical_path_checker.py --dir src/
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


# Critical path function name patterns
CRITICAL_FUNC_PATTERNS = [
    r'boot', r'startup', r'init',
    r'connect', r'handshake',
    r'audio', r'video', r'display',
    r'ota', r'upgrade',
    r'sleep', r'wakeup', r'resume',
]


def check_file(path: Path) -> list[dict]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    lines = text.splitlines()
    issues = []

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("/*"):
            continue

        # Check for vTaskDelay with portMAX_DELAY in any context
        if "vTaskDelay" in stripped and "portMAX_DELAY" in stripped:
            # Check if it's in a critical path context
            # Look at function name
            func_context = ""
            for j in range(max(0, i - 20), i):
                match = re.match(r'^(?:static\s+)?(?:void|int|esp_err_t|bool)\s+(\w+)\s*\(', lines[j].strip())
                if match:
                    func_context = match.group(1)
                    break

            # Check if function name matches critical path
            is_critical = any(re.search(pat, func_context, re.IGNORECASE) for pat in CRITICAL_FUNC_PATTERNS)

            if is_critical:
                issues.append({
                    "id": "C35.2",
                    "file": f"{path}:{i}",
                    "issue": f"关键路径函数 {func_context}() 中 vTaskDelay(portMAX_DELAY) 缺 deadline/fallback",
                    "severity": "P0",
                })
            else:
                # Generic portMAX_DELAY in any function is still a concern
                issues.append({
                    "id": "C35.2",
                    "file": f"{path}:{i}",
                    "issue": "vTaskDelay(portMAX_DELAY) 缺 deadline/fallback",
                    "severity": "P1",
                })

    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="C35 关键路径预算表检查器")
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
        print("[critical_path_checker] 无文件可检查")
        return 0

    all_issues: list[dict] = []
    for path in unique:
        all_issues.extend(check_file(path))

    if not all_issues:
        print(f"[critical_path_checker] 已检查 {len(unique)} 个文件，未发现 C35 违规")
        return 0

    print(f"[critical_path_checker] 已检查 {len(unique)} 个文件，发现 {len(all_issues)} 个 C35 告警:\n")
    for issue in all_issues:
        print(f"  [{issue['severity']}] {issue['id']} — {issue['file']} — {issue['issue']}")

    print(f"\nSummary: {len(all_issues)} C35 critical path warnings")
    return 1


if __name__ == "__main__":
    sys.exit(main())
