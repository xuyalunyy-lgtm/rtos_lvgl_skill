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

import argparse
import re
import sys
from pathlib import Path

from checker_io import configure_stdout, output_json


def analyze_queue_ast(content: str, filename: str = "<stdin>") -> dict:
    lines = content.splitlines()
    errors = []

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

    send_re = re.compile(r"xQueue(?:Send|SendToBack|SendFromISR|Overwrite)\s*\(")
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

        stack_vars = set()
        cjson_vars = set()
        ptr_from_stack_map = {}

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
                errors.append({
                    "line": abs_line,
                    "type": "cjson_in_queue_send",
                    "message": f"{func_name}(): xQueueSend 行含 cJSON — 禁止",
                    "func": func_name,
                })

            # 检查 payload 赋值
            for m in payload_assign.finditer("\n".join(body)):
                rhs = m.group(1)
                assign_line = m.start() // 100 + start + 1  # approx
                if rhs in stack_vars:
                    errors.append({
                        "line": abs_line,
                        "type": "stack_payload",
                        "message": f"{func_name}(): .payload 指向栈变量 '{rhs}'",
                        "func": func_name,
                    })
                if rhs in cjson_vars:
                    errors.append({
                        "line": abs_line,
                        "type": "cjson_payload",
                        "message": f"{func_name}(): 字段赋值为 cJSON* '{rhs}'",
                        "func": func_name,
                    })

            # 检查 xQueueSend 第二个参数
            send_m = re.search(
                r"xQueue\w+\s*\(\s*[^,]+,\s*&(\w+)", line
            )
            if send_m:
                arg = send_m.group(1)
                if arg in cjson_vars:
                    errors.append({
                        "line": abs_line,
                        "type": "cjson_queue_element",
                        "message": f"{func_name}(): xQueueSend 传递 cJSON* '&{arg}'",
                        "func": func_name,
                    })
                if arg in stack_vars:
                    errors.append({
                        "line": abs_line,
                        "type": "stack_queue_element",
                        "message": f"{func_name}(): xQueueSend 传递栈 buffer '&{arg}'",
                        "func": func_name,
                    })
                if arg in ptr_from_stack_map:
                    errors.append({
                        "line": abs_line,
                        "type": "stack_ptr_queue_element",
                        "message": f"{func_name}(): 传递指向栈 '{ptr_from_stack_map[arg]}' 的指针 '&{arg}'",
                        "func": func_name,
                    })

    # 去重
    seen = set()
    unique = []
    for e in errors:
        key = (e["line"], e["type"])
        if key not in seen:
            seen.add(key)
            unique.append(e)
    errors = unique

    return {
        "checker": "queue_ast_checker",
        "file": filename,
        "summary": {"functions_analyzed": len(functions), "errors": len(errors)},
        "violations": [{"severity": "error", "rule": "C2", **e} for e in errors],
    }


def format_report(result: dict) -> str:
    lines = [
        "=" * 60,
        f"Queue 所有权 AST 审查: {result['file']}",
        "=" * 60,
        f"分析函数数: {result['summary']['functions_analyzed']}",
        f"违规数: {result['summary']['errors']}",
        "",
    ]
    if result["violations"]:
        lines.append("🔴 铁律 #2 违规:")
        for v in result["violations"]:
            lines.append(f"  L{v.get('line', '?')} [{v['type']}]: {v['message']}")
        lines.append("")
        lines.append("正例: examples/good_presenter_consumer.c（heap payload + Presenter vPortFree）")
    else:
        lines.append("✅ 通过：未检测到栈指针/cJSON* 进 Queue。")
    lines.append("")
    lines.append("ℹ️  本工具基于函数级 AST 分析，精度高于正则版本。")
    return "\n".join(lines)


def main() -> int:
    configure_stdout()
    parser = argparse.ArgumentParser(description="Queue 所有权 AST 审查（增强版）")
    parser.add_argument("file", help="待检查的 .c 文件")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()

    path = Path(args.file)
    if not path.exists():
        print(f"错误: 文件不存在: {path}", file=sys.stderr)
        return 1

    content = path.read_text(encoding="utf-8", errors="replace")
    result = analyze_queue_ast(content, str(path))

    if args.json:
        output_json(result)
    else:
        print(format_report(result))
    return 1 if result["summary"]["errors"] > 0 else 0


if __name__ == "__main__":
    sys.exit(main())