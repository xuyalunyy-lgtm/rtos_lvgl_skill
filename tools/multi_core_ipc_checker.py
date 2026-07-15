#!/usr/bin/env python3
"""C17 multi-core shared-state protection heuristic checker.

This intentionally reports only a narrow, high-confidence class of problem:
a file-scope ``volatile`` object read or written more than once without a
nearby critical section, atomic primitive, or mutex.  It cannot prove task
placement or cache coherency; those remain review items.
"""

from __future__ import annotations

import re
from pathlib import Path

from checker_io import make_issue, read_file, run_checker, strip_comments

VOLATILE_DECL_RE = re.compile(
    r"^\s*(?:static\s+)?volatile\s+[A-Za-z_]\w*(?:\s*\*)*\s+([A-Za-z_]\w*)\b"
)
PROTECTION_RE = re.compile(
    r"\b(?:portENTER_CRITICAL|taskENTER_CRITICAL|atomic_[A-Za-z_]|__atomic_|"
    r"xSemaphoreTake|xSemaphoreGive|k_mutex_(?:lock|unlock)|pthread_mutex_(?:lock|unlock))\b"
)


def _shared_volatile_names(code: str) -> dict[str, int]:
    """Return file-scope volatile object names and declaration lines."""
    result: dict[str, int] = {}
    depth = 0
    for line_no, line in enumerate(code.splitlines(), 1):
        if depth == 0:
            match = VOLATILE_DECL_RE.match(line)
            if match:
                result[match.group(1)] = line_no
        depth += line.count("{") - line.count("}")
    return result


def check_file(path: Path) -> list[dict[str, str]]:
    result = read_file(path)
    if result is None:
        return []
    _lines, raw_text = result
    code = strip_comments(raw_text)
    code_lines = code.splitlines()
    issues: list[dict[str, str]] = []

    for name, declaration_line in _shared_volatile_names(code).items():
        access_re = re.compile(rf"\b{re.escape(name)}\b")
        unprotected: list[int] = []
        for index, line in enumerate(code_lines):
            line_no = index + 1
            if line_no == declaration_line or not access_re.search(line):
                continue
            window = "\n".join(code_lines[max(0, index - 3):min(len(code_lines), index + 4)])
            if not PROTECTION_RE.search(window):
                unprotected.append(line_no)

        # One access can be a one-way status handoff; two unprotected accesses
        # are a useful signal of a shared read/write path worth fixing.
        if len(unprotected) >= 2:
            issues.append(make_issue(
                path, unprotected[0], "C17", "P1",
                f"file-scope volatile '{name}' has {len(unprotected)} unprotected accesses; "
                "use an atomic operation, critical section, or explicit IPC ownership",
            ))
    return issues


if __name__ == "__main__":
    raise SystemExit(run_checker(check_file, "C17 multi-core IPC checker", ("C17",)))
