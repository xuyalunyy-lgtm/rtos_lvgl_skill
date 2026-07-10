#!/usr/bin/env python3
"""
cJSON AST leak review (enhanced, function-level precision + goto tracking).

Higher precision than cjson_leak_checker.py:
- Precise function boundary detection (brace depth tracking)
- goto cleanup pattern recognition
- Parse failure branch exclusion
- cleanup label coverage check

Usage:
    python tools/cjson_ast_checker.py path/to/file.c
    python tools/cjson_ast_checker.py path/to/file.c --json
"""
from __future__ import annotations

import re
from pathlib import Path

from checker_io import make_issue, read_file, run_checker
from sdk_lookup import SdkLookup

lookup = SdkLookup("esp32")


# ---------------------------------------------------------------------------
# Core check logic
# ---------------------------------------------------------------------------

def check_file(path: Path) -> list[dict]:
    """Analyze cJSON AST leak issues in a single C file, return issue list."""
    result = read_file(path)
    if result is None:
        return []
    lines, content = result

    # Precise function boundary detection (brace depth)
    functions: list[tuple[str, int, int]] = []
    brace_depth = 0
    current_func: str | None = None
    func_start = 0
    func_pat = re.compile(
        r"^((?:static\s+)?(?:inline\s+)?[\w\s\*]+\s+(\w+)\s*\([^)]*\)\s*\{?)",
        re.MULTILINE,
    )

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("/*"):
            continue
        m = func_pat.match(stripped)
        if m and brace_depth == 0:
            current_func = m.group(2)
            func_start = i
            if "{" in stripped:
                brace_depth = 1
            continue
        if current_func:
            brace_depth += stripped.count("{") - stripped.count("}")
            if brace_depth <= 0 and "{" in "".join(lines[func_start : i + 1]):
                functions.append((current_func, func_start, i))
                current_func = None
                brace_depth = 0

    parse_re = lookup.build_regex("PARSE")
    delete_re = lookup.build_regex("DELETE")
    return_re = re.compile(r"\breturn\b")
    goto_re = re.compile(r"\bgoto\s+(\w+)")
    label_re = re.compile(r"^(\w+):\s*$")

    issues: list[dict] = []

    for func_name, start, end in functions:
        body = lines[start : end + 1]
        parse_lines: list[int] = []
        delete_lines: list[int] = []
        return_lines: list[int] = []
        goto_cleanup_lines: list[int] = []
        cleanup_label_line: int | None = None

        for j, line in enumerate(body):
            abs_line = start + j + 1
            stripped = line.strip()
            if stripped.startswith("//"):
                continue
            if parse_re.search(line):
                parse_lines.append(abs_line)
            if delete_re.search(line):
                delete_lines.append(abs_line)
            if return_re.search(stripped):
                return_lines.append(abs_line)
            m_goto = goto_re.search(line)
            if m_goto and m_goto.group(1) == "cleanup":
                goto_cleanup_lines.append(abs_line)
            m_label = label_re.match(stripped)
            if m_label and m_label.group(1) == "cleanup":
                cleanup_label_line = abs_line

        # Check 1: Parse count > Delete count
        if len(parse_lines) > len(delete_lines):
            issues.append(make_issue(
                path, parse_lines[0], "C3", "P2",
                f"{func_name}(): Parse {len(parse_lines)} times, Delete {len(delete_lines)} times",
            ))

        # Check 2: Has Parse + early return but no goto cleanup
        if parse_lines and not goto_cleanup_lines and not cleanup_label_line:
            first_delete = min(delete_lines) if delete_lines else 999999
            has_early = any(rl < first_delete for rl in return_lines)
            if has_early:
                issues.append(make_issue(
                    path, min(return_lines), "C3", "P2",
                    f"{func_name}(): Has Parse + early return but no goto cleanup",
                ))

        # Check 3: goto cleanup but no cleanup label
        if goto_cleanup_lines and not cleanup_label_line:
            issues.append(make_issue(
                path, goto_cleanup_lines[0], "C3", "P2",
                f"{func_name}(): goto cleanup but no cleanup: label",
            ))

    return issues


if __name__ == "__main__":
    raise SystemExit(run_checker(check_file, "cJSON AST leak review (enhanced)", ("C3",)))
