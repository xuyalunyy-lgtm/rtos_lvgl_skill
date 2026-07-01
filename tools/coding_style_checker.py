#!/usr/bin/env python3
"""
C11 编码规范启发式检查器。

检查项:
  C11.1 — 文件名 模块_功能.c/h，禁止中文/空格
  C11.5 — 单函数 <=80 行

用法:
    python tools/coding_style_checker.py <file.c> [file2.c ...]
    python tools/coding_style_checker.py --dir src/
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


def check_file(path: Path) -> list[dict]:
    issues = []

    # C11.1: Check filename
    name = path.name
    if re.search(r'[一-鿿]', name):
        issues.append({
            "id": "C11.1",
            "file": str(path),
            "issue": f"文件名含中文字符: {name}",
            "severity": "P2",
        })
    if ' ' in name:
        issues.append({
            "id": "C11.1",
            "file": str(path),
            "issue": f"文件名含空格: {name}",
            "severity": "P2",
        })

    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return issues

    lines = text.splitlines()

    # C11.5: Check function length
    func_start = None
    func_name = ""
    brace_depth = 0

    for i, line in enumerate(lines, 1):
        stripped = line.strip()

        # Detect function start
        match = re.match(r'^(?:static\s+)?(?:void|int|esp_err_t|bool|float|double|char|uint\w+|int\w+|size_t|BaseType_t)\s+(\w+)\s*\(', stripped)
        if match and '{' in stripped:
            func_start = i
            func_name = match.group(1)
            brace_depth = 1
            continue

        if func_start is not None:
            brace_depth += stripped.count('{') - stripped.count('}')
            if brace_depth <= 0:
                func_length = i - func_start
                if func_length > 80:
                    issues.append({
                        "id": "C11.5",
                        "file": f"{path}:{func_start}",
                        "issue": f"函数 {func_name} 长度 {func_length} 行 > 80 行",
                        "severity": "P1",
                    })
                func_start = None

    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="C11 编码规范检查器")
    parser.add_argument("files", nargs="*", help="待检查文件")
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
        print("[coding_style_checker] No files to check")
        return 0

    all_issues: list[dict] = []
    for path in unique:
        all_issues.extend(check_file(path))

    if not all_issues:
        print(f"[coding_style_checker] Checked {len(unique)} files, no C11 violations")
        return 0

    print(f"[coding_style_checker] Checked {len(unique)} files, found {len(all_issues)} C11 warnings:\n")
    for issue in all_issues:
        print(f"  [{issue['severity']}] {issue['id']} — {issue['file']} — {issue['issue']}")

    print(f"\nSummary: {len(all_issues)} C11 coding style warnings")
    return 1


if __name__ == "__main__":
    sys.exit(main())
