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

import re
from pathlib import Path

from checker_io import make_issue, read_file, run_checker


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
                        issues.append(make_issue(path, switch_start_line, "C13.3", "P1",
                            f"switch({switch_var}) 缺少 default 分支（非法状态未处理）"))
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
                issues.append(make_issue(path, i, "C13.1", "P1",
                    "长生命周期任务未见显式状态枚举（建议定义 enum xxx_state）"))
                break

    return issues


def check_file(path: Path) -> list[dict]:
    result = read_file(path)
    if result is None:
        return []

    lines, text = result
    issues = []
    issues.extend(check_switch_default(path, lines))
    issues.extend(check_state_enum(path, lines))
    return issues


if __name__ == "__main__":
    raise SystemExit(run_checker(check_file, "C13 状态机检查器", ("C13",)))
