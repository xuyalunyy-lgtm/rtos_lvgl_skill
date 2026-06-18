#!/usr/bin/env python3
"""
C13 状态机启发式检查器。

检查项:
  C13.1 — 长生命周期任务须有显式 enum state
  C13.3 — switch-default 处理非法状态（log + reset）

用法:
    python tools/state_machine_checker.py <file.c> [file2.c ...]
    python tools/state_machine_checker.py --dir src/
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


def check_switch_default(path: Path, lines: list[str]) -> list[dict]:
    """C13.3 — switch 语句必须有 default 分支"""
    issues = []
    in_switch = False
    switch_start_line = 0
    has_default = False
    brace_depth = 0
    switch_var = ""

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("/*"):
            continue

        # Detect switch start
        switch_match = re.search(r"switch\s*\((.+?)\)", stripped)
        if switch_match and "{" in stripped:
            in_switch = True
            switch_start_line = i
            has_default = False
            brace_depth = stripped.count("{") - stripped.count("}")
            switch_var = switch_match.group(1).strip()
        elif in_switch:
            brace_depth += stripped.count("{") - stripped.count("}")

            # Check for default
            if re.match(r"default\s*:", stripped):
                has_default = True

            # Switch end
            if brace_depth <= 0:
                if not has_default and switch_var:
                    # Only flag if switch variable looks like a state
                    if any(kw in switch_var.lower() for kw in ["state", "status", "mode", "phase", "step"]):
                        issues.append({
                            "id": "C13.3",
                            "file": f"{path}:{switch_start_line}",
                            "issue": f"switch({switch_var}) 缺少 default 分支（非法状态未处理）",
                            "severity": "P1",
                        })
                in_switch = False

    return issues


def check_state_enum(path: Path, lines: list[str]) -> list[dict]:
    """C13.1 — 长生命周期任务应有显式状态枚举"""
    issues = []
    has_state_enum = False
    has_task_function = False

    # Check for state enum
    for line in lines:
        stripped = line.strip()
        if re.search(r"typedef\s+enum\s*\{.*state.*\}", stripped, re.IGNORECASE):
            has_state_enum = True
            break
        if re.search(r"enum\s+\w*state\w*", stripped, re.IGNORECASE):
            has_state_enum = True
            break

    # Check for task function (long-lived)
    for line in lines:
        stripped = line.strip()
        if re.search(r"static\s+void\s+\w+_task\s*\(", stripped):
            has_task_function = True
            break
        if re.search(r"void\s+\w+_task\s*\(\s*void\s*\*\s*arg\s*\)", stripped):
            has_task_function = True
            break

    # If has task but no state enum, flag it
    if has_task_function and not has_state_enum:
        # Find the task function line
        for i, line in enumerate(lines, 1):
            if re.search(r"void\s+\w+_task\s*\(", line):
                issues.append({
                    "id": "C13.1",
                    "file": f"{path}:{i}",
                    "issue": "长生命周期任务未见显式状态枚举（建议定义 enum xxx_state）",
                    "severity": "P1",
                })
                break

    return issues


def check_file(path: Path) -> list[dict]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    lines = text.splitlines()
    issues = []
    issues.extend(check_switch_default(path, lines))
    issues.extend(check_state_enum(path, lines))
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="C13 状态机检查器")
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
        print("[state_machine_checker] 无文件可检查")
        return 0

    all_issues: list[dict] = []
    for path in unique:
        all_issues.extend(check_file(path))

    if not all_issues:
        print(f"[state_machine_checker] 已检查 {len(unique)} 个文件，未发现 C13 违规")
        return 0

    print(f"[state_machine_checker] 已检查 {len(unique)} 个文件，发现 {len(all_issues)} 个 C13 告警:\n")
    for issue in all_issues:
        print(f"  [{issue['severity']}] {issue['id']} — {issue['file']} — {issue['issue']}")

    print(f"\nSummary: {len(all_issues)} C13 state-machine warnings")
    return 1


if __name__ == "__main__":
    sys.exit(main())
