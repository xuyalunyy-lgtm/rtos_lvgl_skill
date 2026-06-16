#!/usr/bin/env python3
"""
C12 错误处理启发式检查器。

检查项:
  C12.1 — FreeRTOS API 返回值未检查
  C12.2 — pvPortMalloc 未检查即使用

用法:
    python tools/return_check_checker.py <file.c> [file2.c ...]
    python tools/return_check_checker.py --dir src/
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Functions whose return value MUST be checked
CRITICAL_API = [
    "xTaskCreate",
    "xTaskCreateStatic",
    "xQueueCreate",
    "xQueueSend",
    "xQueueReceive",
    "xSemaphoreCreateMutex",
    "xSemaphoreCreateBinary",
    "xSemaphoreTake",
    "pvPortMalloc",
    "pvPortCalloc",
    "xTimerStart",
    "xTimerChangePeriod",
]

# Build pattern: these function calls
CALL_PATTERN = re.compile(
    r"(?:" + "|".join(re.escape(f) for f in CRITICAL_API) + r")\s*\("
)

# Pattern for checking if return is captured
CAPTURE_PATTERN = re.compile(
    r"(?:(?:\w+)\s*=\s*)?(" + "|".join(re.escape(f) for f in CRITICAL_API) + r")\s*\("
)

# NULL check patterns
NULL_CHECK_PATTERN = re.compile(r"(?:!=\s*NULL|==\s*NULL|if\s*\(\s*!\s*\w+|if\s*\(\s*\w+\s*\))")


def check_file(path: Path) -> list[dict]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    issues: list[dict] = []
    lines = text.splitlines()

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        # Skip comments
        if stripped.startswith("//") or stripped.startswith("/*"):
            continue

        # Find API calls
        for api in CRITICAL_API:
            if api + "(" not in stripped:
                continue

            # Check if return is captured (assigned to variable)
            assign_match = re.search(rf"(\w+)\s*=\s*{re.escape(api)}\s*\(", stripped)
            if assign_match:
                # Return is captured, check next few lines for NULL/error check
                var_name = assign_match.group(1)
                checked = False
                for j in range(i, min(i + 5, len(lines))):
                    next_line = lines[j]
                    if var_name in next_line and (
                        "if" in next_line
                        or "NULL" in next_line
                        or "!= pdPASS" in next_line
                        or "== pdPASS" in next_line
                        or "< 0" in next_line
                    ):
                        checked = True
                        break
                if not checked:
                    issues.append({
                        "id": "C12.1",
                        "file": f"{path}:{i}",
                        "issue": f"{api} 返回值已赋给 {var_name} 但未检查",
                        "severity": "P0",
                    })
            else:
                # Return value discarded entirely
                issues.append({
                    "id": "C12.1",
                    "file": f"{path}:{i}",
                    "issue": f"{api} 返回值未检查（直接调用无赋值）",
                    "severity": "P0",
                })

    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="C12 错误处理检查器")
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
        print("[return_check_checker] 无文件可检查")
        return 0

    all_issues: list[dict] = []
    for path in unique:
        all_issues.extend(check_file(path))

    if not all_issues:
        print(f"[return_check_checker] 已检查 {len(unique)} 个文件，未发现 C12 违规")
        return 0

    print(f"[return_check_checker] 已检查 {len(unique)} 个文件，发现 {len(all_issues)} 个 C12 告警:\n")
    for issue in all_issues:
        print(f"  [{issue['severity']}] {issue['id']} — {issue['file']} — {issue['issue']}")

    print(f"\nSummary: {len(all_issues)} C12 return-check warnings")
    return 1


if __name__ == "__main__":
    sys.exit(main())