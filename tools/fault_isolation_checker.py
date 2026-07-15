#!/usr/bin/env python3
"""C38 fault-isolation / circuit-breaker heuristic checker.

Flags only infinite retry/reconnect loops that have neither a bounded attempt
counter nor a visible isolation/offline/circuit-breaker path.  It is a guard
against recovery storms, not a proof that a subsystem is fully fault-isolated.
"""

from __future__ import annotations

import re
from pathlib import Path

from checker_io import extract_functions, make_issue, read_file, run_checker, strip_comments

INFINITE_LOOP_RE = re.compile(r"\b(?:while\s*\(\s*(?:1|true)\s*\)|for\s*\(\s*;\s*;\s*\))", re.I)
RECOVERY_RE = re.compile(r"\b(?:reconnect|retry|recover|restart|reinit|connect)\w*\s*\(", re.I)
EXIT_POLICY_RE = re.compile(
    r"\b(?:max_?retry|retry_?count|attempt(?:s)?|circuit|offline|isolate|disabled?|faulted)\b",
    re.I,
)


def check_file(path: Path) -> list[dict[str, str]]:
    result = read_file(path)
    if result is None:
        return []
    _lines, raw_text = result
    code = strip_comments(raw_text)
    issues: list[dict[str, str]] = []

    for func in extract_functions(code):
        if not INFINITE_LOOP_RE.search(func.body) or not RECOVERY_RE.search(func.body):
            continue
        if EXIT_POLICY_RE.search(func.body):
            continue
        issues.append(make_issue(
            path, func.line, "C38", "P1",
            f"{func.name}() contains an unbounded recovery loop without retry limit or isolation path",
        ))
    return issues


if __name__ == "__main__":
    raise SystemExit(run_checker(check_file, "C38 fault-isolation checker", ("C38",)))
