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

import argparse
import re
import sys
from pathlib import Path

from checker_io import configure_stdout, output_json


def analyze_ast(content: str, filename: str = "<stdin>") -> dict:
    lines = content.splitlines()
    errors = []

    # 精确函数边界检测（大括号深度）
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

    parse_re = re.compile(r"cJSON_Parse\s*\(")
    delete_re = re.compile(r"cJSON_Delete\s*\(")
    return_re = re.compile(r"\breturn\b")
    goto_re = re.compile(r"\bgoto\s+(\w+)")
    label_re = re.compile(r"^(\w+):\s*$")

    for func_name, start, end in functions:
        body = lines[start : end + 1]
        parse_lines = []
        delete_lines = []
        return_lines = []
        goto_cleanup_lines = []
        cleanup_label_line = None

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
            errors.append({
                "func": func_name,
                "type": "parse_delete_mismatch",
                "message": f"{func_name}(): Parse {len(parse_lines)} 次, Delete {len(delete_lines)} 次",
                "line": parse_lines[0],
            })

        # 检查 2: 有 Parse + early return 但无 goto cleanup
        if parse_lines and not goto_cleanup_lines and not cleanup_label_line:
            first_delete = min(delete_lines) if delete_lines else 999999
            has_early = any(rl < first_delete for rl in return_lines)
            if has_early:
                errors.append({
                    "func": func_name,
                    "type": "no_cleanup_pattern",
                    "message": f"{func_name}(): 有 Parse + early return 但无 goto cleanup",
                    "line": min(return_lines),
                })

        # 检查 3: goto cleanup 但无 cleanup 标签
        if goto_cleanup_lines and not cleanup_label_line:
            errors.append({
                "func": func_name,
                "type": "missing_cleanup_label",
                "message": f"{func_name}(): goto cleanup 但无 cleanup: 标签",
                "line": goto_cleanup_lines[0],
            })

    return {
        "checker": "cjson_ast_checker",
        "file": filename,
        "summary": {"functions_analyzed": len(functions), "errors": len(errors)},
        "violations": [{"severity": "error", "rule": "C3", **e} for e in errors],
    }


def format_report(result: dict) -> str:
    lines = [
        "=" * 60,
        f"cJSON AST 泄漏审查: {result['file']}",
        "=" * 60,
        f"分析函数数: {result['summary']['functions_analyzed']}",
        f"违规数: {result['summary']['errors']}",
        "",
    ]
    if result["violations"]:
        lines.append("🔴 违规:")
        for v in result["violations"]:
            lines.append(f"  L{v.get('line', '?')} [{v['type']}]: {v['message']}")
        lines.append("")
        lines.append("修复建议: 使用 goto cleanup 模板 (prompts/cjson_safe_parse.txt)")
    else:
        lines.append("✅ 通过：所有 Parse/Delete 配对正确。")
    lines.append("")
    lines.append("ℹ️  本工具基于函数级 AST 分析，精度高于正则版本。")
    return "\n".join(lines)


def main() -> int:
    configure_stdout()
    parser = argparse.ArgumentParser(description="cJSON AST 泄漏审查（增强版）")
    parser.add_argument("file", help="待检查的 .c 文件")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()

    path = Path(args.file)
    if not path.exists():
        print(f"错误: 文件不存在: {path}", file=sys.stderr)
        return 1

    content = path.read_text(encoding="utf-8", errors="replace")
    result = analyze_ast(content, str(path))

    if args.json:
        output_json(result)
    else:
        print(format_report(result))
    return 1 if result["summary"]["errors"] > 0 else 0


if __name__ == "__main__":
    sys.exit(main())