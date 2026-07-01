#!/usr/bin/env python3
"""
C7.3 大缓冲区栈分配检查器。

检查项:
  C7.3 — 大 buffer（>256B）、证书链、JSON 解析树禁止放栈上

用法:
    python tools/stack_alloc_checker.py <file.c> [file2.c ...]
    python tools/stack_alloc_checker.py --dir src/
"""

from __future__ import annotations

import re
from pathlib import Path

from checker_io import make_issue, read_file, run_checker

THRESHOLD = 256

STACK_ALLOC_RE = re.compile(
    r'^\s*(?:static\s+)?(?:const\s+)?(?:unsigned\s+)?'
    r'(?:char|uint8_t|int8_t|uint16_t|int16_t|uint32_t|int32_t|float|double|unsigned|BYTE|WORD|DWORD)'
    r'\s+\w+\s*\[\s*(\d+)\s*\]'
)

CERT_JSON_RE = re.compile(r'(?:cert|certificate|pem|json|cJSON|root_ca|client_cert|server_cert)', re.IGNORECASE)


def check_file(path: Path) -> list[dict]:
    result = read_file(path)
    if result is None:
        return []

    if path.suffix == ".h":
        return []

    lines, text = result
    issues = []

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*"):
            continue

        match = STACK_ALLOC_RE.match(stripped)
        if match:
            try:
                size = int(match.group(1))
            except ValueError:
                continue

            if size > THRESHOLD:
                is_cert_json = bool(CERT_JSON_RE.search(stripped))
                if is_cert_json:
                    issues.append(make_issue(path, i, "C7.3", "P0",
                        f"cert/JSON buffer ({size}B) on stack, use heap or static pool"))
                elif size > 1024:
                    issues.append(make_issue(path, i, "C7.3", "P0",
                        f"large buffer ({size}B > 1024B) on stack, use heap or static pool"))
                else:
                    issues.append(make_issue(path, i, "C7.3", "P1",
                        f"buffer ({size}B > {THRESHOLD}B) on stack, consider heap"))

    return issues


if __name__ == "__main__":
    raise SystemExit(run_checker(check_file, "C7.3 栈分配检查器", ("C7.3",)))
