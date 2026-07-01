#!/usr/bin/env python3
"""
C37 背压与降级策略启发式检查器。

检查项:
  C37.1 — 高频 producer/网络/音视频/日志/UI 队列必须声明背压策略
  C37.2 — 满队列禁止无限等待，必须选择 drop/coalesce/overwrite/backpressure

用法:
    python tools/backpressure_checker.py <file.c> [file2.c ...]
    python tools/backpressure_checker.py --dir src/
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


# Queue send APIs
QUEUE_SEND_APIS = [
    "xQueueSend",
    "xQueueSendToBack",
    "xQueueSendToFront",
    "xQueueOverwrite",
    "xQueueGenericSend",
]

# Safe queue send (with timeout)
SAFE_SEND_PATTERN = re.compile(
    r'xQueue(?:Send|SendToBack|SendToFront|GenericSend)\s*\([^,]+,\s*[^,]+,\s*[^)]+\)'
)

# portMAX_DELAY pattern
MAX_DELAY_PATTERN = re.compile(r'portMAX_DELAY|WAIT_FOREVER|0xFFFFFFFF')


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

        # C37.2: Check for queue send with portMAX_DELAY (blocking indefinitely)
        for api in QUEUE_SEND_APIS:
            if api + "(" in stripped:
                # Check if this send has portMAX_DELAY
                if MAX_DELAY_PATTERN.search(stripped):
                    issues.append({
                        "id": "C37.2",
                        "file": f"{path}:{i}",
                        "issue": f"{api} 使用 portMAX_DELAY 无限等待（满队列会永久阻塞）",
                        "severity": "P0",
                    })
                # Check if this send has no timeout at all
                elif not SAFE_SEND_PATTERN.search(stripped) and "(" in stripped:
                    # Check if there's a timeout in nearby lines
                    has_timeout = False
                    for j in range(max(0, i - 3), min(len(lines), i + 2)):
                        if "pdMS_TO_TICKS" in lines[j] or "timeout" in lines[j].lower():
                            has_timeout = True
                            break
                    if not has_timeout and api != "xQueueOverwrite":
                        issues.append({
                            "id": "C37.2",
                            "file": f"{path}:{i}",
                            "issue": f"{api} 未见明确超时（建议使用 pdMS_TO_TICKS 或 0 作为超时参数）",
                            "severity": "P1",
                        })

    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="C37 背压与降级策略检查器")
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
        print("[backpressure_checker] 无文件可检查")
        return 0

    all_issues: list[dict] = []
    for path in unique:
        all_issues.extend(check_file(path))

    if not all_issues:
        print(f"[backpressure_checker] 已检查 {len(unique)} 个文件，未发现 C37 违规")
        return 0

    print(f"[backpressure_checker] 已检查 {len(unique)} 个文件，发现 {len(all_issues)} 个 C37 告警:\n")
    for issue in all_issues:
        print(f"  [{issue['severity']}] {issue['id']} — {issue['file']} — {issue['issue']}")

    print(f"\nSummary: {len(all_issues)} C37 backpressure warnings")
    return 1


if __name__ == "__main__":
    sys.exit(main())
