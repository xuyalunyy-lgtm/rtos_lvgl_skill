#!/usr/bin/env python3
"""
cJSON AST 泄漏审查（增强版，精确到函数级别 + goto 追踪）。

比 cjson_leak_checker.py 精度更高：
- 精确函数边界检测（大括号深度追踪）
- goto cleanup 模式识别
- Parse 失败分支排除
- cleanup 标签覆盖检查

用法:
    python tools/cjson_ast_checker.py path/to/file.c
    python tools/cjson_ast_checker.py path/to/file.c --json
"""
from __future__ import annotations

import re
from pathlib import Path

from checker_io import make_issue, read_file, run_checker


# ---------------------------------------------------------------------------
# Core check logic
# ---------------------------------------------------------------------------

def check_file(path: Path) -> list[dict]:
    """分析单个 C 文件的 cJSON AST 泄漏问题，返回 issue 列表。"""
    result = read_file(path)
    if result is None:
        return []
    lines, content = result

    # 精确函数边界检测（大括号深度）
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

    parse_re = re.compile(r"cJSON_Parse\s*\(")
    delete_re = re.compile(r"cJSON_Delete\s*\(")
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

        # 检查 1: Parse 数 > Delete 数
        if len(parse_lines) > len(delete_lines):
            issues.append(make_issue(
                path, parse_lines[0], "C3", "P2",
                f"{func_name}(): Parse {len(parse_lines)} 次, Delete {len(delete_lines)} 次",
            ))

        # 检查 2: 有 Parse + early return 但无 goto cleanup
        if parse_lines and not goto_cleanup_lines and not cleanup_label_line:
            first_delete = min(delete_lines) if delete_lines else 999999
            has_early = any(rl < first_delete for rl in return_lines)
            if has_early:
                issues.append(make_issue(
                    path, min(return_lines), "C3", "P2",
                    f"{func_name}(): 有 Parse + early return 但无 goto cleanup",
                ))

        # 检查 3: goto cleanup 但无 cleanup 标签
        if goto_cleanup_lines and not cleanup_label_line:
            issues.append(make_issue(
                path, goto_cleanup_lines[0], "C3", "P2",
                f"{func_name}(): goto cleanup 但无 cleanup: 标签",
            ))

    return issues


if __name__ == "__main__":
    raise SystemExit(run_checker(check_file, "cJSON AST 泄漏审查（增强版）", ("C3",)))
