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

import argparse
import re
import sys
from pathlib import Path


# Threshold for "large" stack allocation (bytes)
LARGE_STACK_THRESHOLD = 256

# Patterns for stack-allocated large buffers
# Matches: char buf[512], uint8_t data[1024], static char ..., etc.
STACK_ALLOC_PATTERN = re.compile(
    r'^\s*'
    r'(?:static\s+)?'
    r'(?:const\s+)?'
    r'(?:unsigned\s+)?'
    r'(?:char|uint8_t|int8_t|uint16_t|int16_t|uint32_t|int32_t|float|double|unsigned|BYTE|WORD|DWORD)'
    r'\s+\w+\s*\[\s*(\d+)\s*\]'
)

# Certificate/JSON patterns
CERT_JSON_PATTERN = re.compile(
    r'(?:cert|certificate|pem|json|cJSON|root_ca|client_cert|server_cert)',
    re.IGNORECASE
)


def check_file(path: Path, threshold: int = LARGE_STACK_THRESHOLD) -> list[dict]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    # Skip header files and non-function files
    if path.suffix == ".h":
        return []

    issues = []

    for i, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()

        # Skip comments
        if stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*"):
            continue

        match = STACK_ALLOC_PATTERN.match(stripped)
        if match:
            size_str = match.group(1)
            try:
                size = int(size_str)
            except ValueError:
                continue

            if size > threshold:
                # Check if it's a cert/JSON buffer (always flag)
                is_cert_json = bool(CERT_JSON_PATTERN.search(stripped))

                if is_cert_json:
                    issues.append({
                        "id": "C7.3",
                        "file": f"{path}:{i}",
                        "issue": f"证书/JSON 缓冲区 ({size}B) 禁止放栈上，须堆分配或静态池",
                        "severity": "P0",
                    })
                elif size > 1024:
                    issues.append({
                        "id": "C7.3",
                        "file": f"{path}:{i}",
                        "issue": f"栈上大缓冲区 ({size}B > 1024B)，须堆分配或静态池",
                        "severity": "P0",
                    })
                elif size > threshold:
                    issues.append({
                        "id": "C7.3",
                        "file": f"{path}:{i}",
                        "issue": f"栈上缓冲区 ({size}B > {threshold}B)，建议堆分配",
                        "severity": "P1",
                    })

    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="C7.3 大缓冲区栈分配检查器")
    parser.add_argument("files", nargs="*", help="待检查 .c 文件")
    parser.add_argument("--dir", "-d", help="递归检查目录")
    parser.add_argument("--threshold", type=int, default=LARGE_STACK_THRESHOLD,
                        help=f"栈分配阈值 (默认 {LARGE_STACK_THRESHOLD}B)")
    args = parser.parse_args()

    threshold = args.threshold
    args = parser.parse_args()

    threshold = args.threshold

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
        print("[stack_alloc_checker] 无文件可检查")
        return 0

    all_issues: list[dict] = []
    for path in unique:
        all_issues.extend(check_file(path, threshold))

    if not all_issues:
        print(f"[stack_alloc_checker] 已检查 {len(unique)} 个文件，未发现 C7.3 违规")
        return 0

    print(f"[stack_alloc_checker] 已检查 {len(unique)} 个文件，发现 {len(all_issues)} 个 C7.3 告警:\n")
    for issue in all_issues:
        print(f"  [{issue['severity']}] {issue['id']} — {issue['file']} — {issue['issue']}")

    print(f"\nSummary: {len(all_issues)} C7.3 stack allocation warnings")
    return 1


if __name__ == "__main__":
    sys.exit(main())
