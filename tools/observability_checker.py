#!/usr/bin/env python3
"""
C32 可观测性优先启发式检查器。

检查项:
  C32.1 — 关键模块必须暴露 state、last_error、last_error_line
  C32.2 — 关键链路必须计数 timeout/drop/retry/reconnect/overflow/underrun

用法:
    python tools/observability_checker.py <file.c> [file2.c ...]
    python tools/observability_checker.py --dir src/
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


# Keywords indicating a module with state
MODULE_INDICATORS = [
    "state", "status", "handle", "context", "instance",
]

# Observability fields expected
OBSERVABILITY_FIELDS = [
    "last_error", "error_count", "timeout_count", "drop_count",
    "retry_count", "reconnect_count", "overflow", "underrun",
    "state", "last_error_line",
]


def check_file(path: Path) -> list[dict]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    lines = text.splitlines()
    issues = []

    # Check for module structs without observability fields
    in_struct = False
    struct_name = ""
    struct_fields = []
    brace_depth = 0

    for i, line in enumerate(lines, 1):
        stripped = line.strip()

        # Detect struct start
        match = re.match(r'typedef\s+struct\s*\{', stripped)
        if match:
            in_struct = True
            struct_fields = []
            brace_depth = 1
            continue

        if in_struct:
            brace_depth += stripped.count("{") - stripped.count("}")
            if brace_depth <= 0:
                in_struct = False
                # Check if this looks like a module status struct
                if any(indicator in " ".join(struct_fields).lower() for indicator in ["state", "error", "count"]):
                    # Check for observability fields
                    has_error = any("error" in f.lower() for f in struct_fields)
                    has_state = any("state" in f.lower() or "status" in f.lower() for f in struct_fields)
                    has_count = any("count" in f.lower() for f in struct_fields)

                    if not (has_error and has_state):
                        issues.append({
                            "id": "C32.1",
                            "file": f"{path}:{i}",
                            "issue": f"模块状态结构体缺少 last_error 或 state 字段",
                            "severity": "P1",
                        })
                    if not has_count:
                        issues.append({
                            "id": "C32.2",
                            "file": f"{path}:{i}",
                            "issue": f"模块状态结构体缺少 timeout/drop/retry 计数器",
                            "severity": "P1",
                        })
                continue

            # Collect field names
            field_match = re.match(r'\w+\s+(\w+)\s*;', stripped)
            if field_match:
                struct_fields.append(field_match.group(1))

    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="C32 可观测性检查器")
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
        print("[observability_checker] 无文件可检查")
        return 0

    all_issues: list[dict] = []
    for path in unique:
        all_issues.extend(check_file(path))

    if not all_issues:
        print(f"[observability_checker] 已检查 {len(unique)} 个文件，未发现 C32 违规")
        return 0

    print(f"[observability_checker] 已检查 {len(unique)} 个文件，发现 {len(all_issues)} 个 C32 告警:\n")
    for issue in all_issues:
        print(f"  [{issue['severity']}] {issue['id']} — {issue['file']} — {issue['issue']}")

    print(f"\nSummary: {len(all_issues)} C32 observability warnings")
    return 1


if __name__ == "__main__":
    sys.exit(main())
