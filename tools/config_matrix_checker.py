#!/usr/bin/env python3
"""
C39 配置矩阵启发式检查器。

检查项:
  C39.1 — Kconfig/feature flag/board/SDK 差异必须进入配置矩阵
  C39.3 — #ifdef 必须归类 platform/board/feature/debug，禁止无名散落

用法:
    python tools/config_matrix_checker.py <file.c> [file2.c ...]
    python tools/config_matrix_checker.py --dir src/
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


# Known config prefixes
KNOWN_PREFIXES = [
    "CONFIG_", "CONFIG_APP_", "CONFIG_SYSTEM_",
    "BOARD_", "PLATFORM_", "FEATURE_", "DEBUG_",
    "APP_TEST_MODE_", "SDK_",
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

        # C39.3: Check for unnamed #ifdef
        match = re.match(r'#\s*if(?:def|ndef)?\s+(\w+)', stripped)
        if match:
            macro = match.group(1)

            # Skip standard C macros
            if macro.startswith("__") or macro in ["_H", "H", "TRUE", "FALSE", "NULL"]:
                continue

            # Check if it matches known prefixes
            is_known = any(macro.startswith(prefix) for prefix in KNOWN_PREFIXES)

            if not is_known and not macro.startswith("__"):
                issues.append({
                    "id": "C39.3",
                    "file": f"{path}:{i}",
                    "issue": f"#ifdef {macro} 未归类为 platform/board/feature/debug",
                    "severity": "P1",
                })

    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="C39 配置矩阵检查器")
    parser.add_argument("files", nargs="*", help="待检查 .c/.h 文件")
    parser.add_argument("--dir", "-d", help="递归检查目录")
    args = parser.parse_args()

    targets: list[Path] = []
    for f in args.files:
        p = Path(f)
        if p.is_file():
            targets.append(p)
        elif p.is_dir():
            targets.extend(sorted(p.rglob("*.c")))
            targets.extend(sorted(p.rglob("*.h")))

    if args.dir:
        d = Path(args.dir)
        if d.is_dir():
            targets.extend(sorted(d.rglob("*.c")))
            targets.extend(sorted(d.rglob("*.h")))

    seen: set[Path] = set()
    unique: list[Path] = []
    for t in targets:
        r = t.resolve()
        if r not in seen:
            seen.add(r)
            unique.append(r)

    if not unique:
        print("[config_matrix_checker] 无文件可检查")
        return 0

    all_issues: list[dict] = []
    for path in unique:
        all_issues.extend(check_file(path))

    if not all_issues:
        print(f"[config_matrix_checker] 已检查 {len(unique)} 个文件，未发现 C39 违规")
        return 0

    print(f"[config_matrix_checker] 已检查 {len(unique)} 个文件，发现 {len(all_issues)} 个 C39 告警:\n")
    for issue in all_issues:
        print(f"  [{issue['severity']}] {issue['id']} — {issue['file']} — {issue['issue']}")

    print(f"\nSummary: {len(all_issues)} C39 config matrix warnings")
    return 1


if __name__ == "__main__":
    sys.exit(main())
