#!/usr/bin/env python3
"""
C11.5 函数长度启发式检查器。

检查项:
  C11.5 — 单函数 ≤80 行，超限须拆分或注释说明原因

用法:
    python tools/function_length_checker.py <file.c> [file2.c ...]
    python tools/function_length_checker.py --dir src/
    python tools/function_length_checker.py --max-lines 80 --dir src/
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Match C function definitions: return_type func_name(...) {
# Handles: static void func(void) {, int main(void) {, etc.
FUNC_DEF_RE = re.compile(
    r"^(?:static\s+)?(?:inline\s+)?(?:const\s+)?"
    r"(?:\w+\s+)+(\w+)\s*\([^)]*\)\s*\{?\s*$"
)

DEFAULT_MAX_LINES = 80


def check_file(path: Path, max_lines: int) -> list[dict]:
    """Check a single .c/.h file for functions exceeding max_lines."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    issues: list[dict] = []
    lines = text.splitlines()
    i = 0

    while i < len(lines):
        line = lines[i].strip()
        # Skip comments and preprocessor
        if line.startswith("//") or line.startswith("/*") or line.startswith("*") or line.startswith("#"):
            i += 1
            continue

        # Look for function definition
        m = FUNC_DEF_RE.match(line)
        if m:
            func_name = m.group(1)
            # Skip common non-function patterns
            if func_name in ("if", "else", "for", "while", "switch", "do", "return", "sizeof"):
                i += 1
                continue

            func_start = i + 1  # 1-based
            brace_count = 0
            func_end = func_start
            found_open = False

            # Count braces to find function end
            for j in range(i, len(lines)):
                for ch in lines[j]:
                    if ch == "{":
                        brace_count += 1
                        found_open = True
                    elif ch == "}":
                        brace_count -= 1
                if found_open and brace_count == 0:
                    func_end = j + 1  # 1-based
                    break

            func_length = func_end - func_start + 1
            if func_length > max_lines:
                issues.append({
                    "id": "C11.5",
                    "file": f"{path}:{func_start}-{func_end}",
                    "issue": f"函数 {func_name}() 共 {func_length} 行（上限 {max_lines}）",
                    "severity": "P1",
                })
            i = func_end
        else:
            i += 1

    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="C11.5 函数长度检查器")
    parser.add_argument("files", nargs="*", help="待检查 .c 文件")
    parser.add_argument("--dir", "-d", help="递归检查目录")
    parser.add_argument("--max-lines", "-m", type=int, default=DEFAULT_MAX_LINES,
                        help=f"函数最大行数（默认 {DEFAULT_MAX_LINES}）")
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
        print("[function_length_checker] 无文件可检查")
        return 0

    all_issues: list[dict] = []
    for path in unique:
        all_issues.extend(check_file(path, args.max_lines))

    if not all_issues:
        print(f"[function_length_checker] 已检查 {len(unique)} 个文件，所有函数 ≤{args.max_lines} 行")
        return 0

    print(f"[function_length_checker] 已检查 {len(unique)} 个文件，发现 {len(all_issues)} 个超长函数:\n")
    for issue in all_issues:
        print(f"  [{issue['severity']}] {issue['id']} — {issue['file']} — {issue['issue']}")

    print(f"\nSummary: {len(all_issues)} C11.5 function-length warnings")
    return 1


if __name__ == "__main__":
    sys.exit(main())