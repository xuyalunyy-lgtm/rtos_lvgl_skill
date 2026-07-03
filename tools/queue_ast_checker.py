#!/usr/bin/env python3
"""
Queue 所有权 AST 审查（增强版，精确函数边界 + 跨变量追踪）。

比 queue_ownership_checker.py 精度更高：
- 精确函数边界检测（大括号深度追踪）
- 变量赋值链追踪（ptr = &stack_var → ptr 进 Queue）
- cJSON 指针生命周期追踪

用法:
    python tools/queue_ast_checker.py path/to/file.c
    python tools/queue_ast_checker.py path/to/file.c --json
"""
from __future__ import annotations

import re
from pathlib import Path

from checker_io import make_issue, read_file, run_checker
from sdk_lookup import SdkLookup

lookup = SdkLookup("esp32")


def check_file(path: Path) -> list[dict]:
    """检查单个文件的 Queue 所有权 AST 违规。"""
    result = read_file(path)
    if result is None:
        return []

    lines, text = result
    errors: list[dict] = []

    # 精确函数边界检测
    functions = []
    brace_depth = 0
    current_func = None
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

    send_re = lookup.build_regex("QUEUE_SEND", "QUEUE_OVERWRITE")
    stack_decl = re.compile(r"(?:char|uint8_t|int8_t)\s+(\w+)\s*\[[^\]]+\]")
    cjson_decl = re.compile(r"cJSON\s*\*\s*(\w+)")
    payload_assign = re.compile(
        r"\.(?:payload|data|obj|message|buf|ptr)\s*=\s*(?:\([^)]*\)\s*)?(?:&)?(\w+)\s*;"
    )
    ptr_from_stack = re.compile(
        r"(?:char|uint8_t|int8_t)\s*\*\s*(\w+)\s*=\s*(?:&)?(\w+)\s*;"
    )

    for func_name, start, end in functions:
        body = lines[start : end + 1]

        stack_vars: set[str] = set()
        cjson_vars: set[str] = set()
        ptr_from_stack_map: dict[str, str] = {}

        for line in body:
            for m in stack_decl.finditer(line):
                stack_vars.add(m.group(1))
            for m in cjson_decl.finditer(line):
                cjson_vars.add(m.group(1))
            for m in ptr_from_stack.finditer(line):
                ptr_name, src = m.group(1), m.group(2)
                if src in stack_vars:
                    ptr_from_stack_map[ptr_name] = src

        for j, line in enumerate(body):
            abs_line = start + j + 1
            if not send_re.search(line):
                continue

            # 检查 cJSON 在 xQueueSend 行
            if re.search(r"cJSON", line, re.I):
                errors.append(make_issue(path, abs_line, "C2", "P0",
                    f"{func_name}(): xQueueSend 行含 cJSON — 禁止"))

            # 检查 payload 赋值
            for m in payload_assign.finditer("\n".join(body)):
                rhs = m.group(1)
                if rhs in stack_vars:
                    errors.append(make_issue(path, abs_line, "C2", "P0",
                        f"{func_name}(): .payload 指向栈变量 '{rhs}'"))
                if rhs in cjson_vars:
                    errors.append(make_issue(path, abs_line, "C2", "P0",
                        f"{func_name}(): 字段赋值为 cJSON* '{rhs}'"))

            # 检查 xQueueSend 第二个参数
            send_m = re.search(
                r"xQueue\w+\s*\(\s*[^,]+,\s*&(\w+)", line
            )
            if send_m:
                arg = send_m.group(1)
                if arg in cjson_vars:
                    errors.append(make_issue(path, abs_line, "C2", "P0",
                        f"{func_name}(): xQueueSend 传递 cJSON* '&{arg}'"))
                if arg in stack_vars:
                    errors.append(make_issue(path, abs_line, "C2", "P0",
                        f"{func_name}(): xQueueSend 传递栈 buffer '&{arg}'"))
                if arg in ptr_from_stack_map:
                    errors.append(make_issue(path, abs_line, "C2", "P0",
                        f"{func_name}(): 传递指向栈 '{ptr_from_stack_map[arg]}' 的指针 '&{arg}'"))

    # 去重
    seen: set[tuple[str, int]] = set()
    unique: list[dict] = []
    for e in errors:
        key = (e["id"], int(e["file"].rsplit(":", 1)[-1]))
        if key not in seen:
            seen.add(key)
            unique.append(e)

    return unique


if __name__ == "__main__":
    raise SystemExit(run_checker(check_file, "Queue 所有权 AST 审查（增强版）", ("C2",)))
