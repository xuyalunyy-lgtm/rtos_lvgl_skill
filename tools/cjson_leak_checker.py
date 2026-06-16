#!/usr/bin/env python3
"""
cJSON 静态泄漏审查工具。

检查 cJSON_Parse / cJSON_ParseWithLength 与 cJSON_Delete 是否成对出现，
并标记可能的泄漏路径。

用法:
    python tools/cjson_leak_checker.py path/to/file.c
    python tools/cjson_leak_checker.py --stdin   # 从标准输入读取
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from checker_io import configure_stdout

PARSE_PATTERNS = [
    re.compile(r"\bcJSON_ParseWithLength\s*\("),
    re.compile(r"\bcJSON_ParseWithOpts\s*\("),
    re.compile(r"\bcJSON_Parse\s*\("),
]
DELETE_PATTERN = re.compile(r"\bcJSON_Delete\s*\(")
CREATE_PATTERN = re.compile(r"\bcJSON_Create\w*\s*\(")

# 粗略函数边界检测
FUNC_START = re.compile(
    r"^(?:static\s+)?(?:\w+\s+)+(\w+)\s*\([^)]*\)\s*\{?",
    re.MULTILINE,
)


@dataclass
class ParseSite:
    line_no: int
    line_text: str
    func_name: str = "global"


@dataclass
class CheckResult:
    file: str
    parse_sites: list[ParseSite] = field(default_factory=list)
    delete_count: int = 0
    create_count: int = 0
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def find_function_at_line(lines: list[str], line_idx: int) -> str:
    """向上搜索最近的函数定义（支持指针返回类型）。"""
    func_pat = re.compile(
        r"(?:static\s+)?(?:inline\s+)?[\w\s\*]+\s+(\w+)\s*\([^;]*\)\s*$"
    )
    for i in range(line_idx, -1, -1):
        stripped = lines[i].strip()
        if stripped.startswith("#") or stripped.startswith("extern "):
            continue
        m = func_pat.search(stripped)
        if m:
            return m.group(1)
    return "global"


def analyze(content: str, filename: str = "<stdin>") -> CheckResult:
    result = CheckResult(file=filename)
    lines = content.splitlines()

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("/*"):
            continue

        for pat in PARSE_PATTERNS:
            if pat.search(line):
                func = find_function_at_line(lines, i)
                result.parse_sites.append(
                    ParseSite(line_no=i + 1, line_text=stripped, func_name=func)
                )

        if DELETE_PATTERN.search(line):
            result.delete_count += 1

        if CREATE_PATTERN.search(line):
            result.create_count += 1

    # 每个 Parse 站点至少应有一个 Delete（同函数或调用链）
    if result.parse_sites:
        ratio = result.delete_count / len(result.parse_sites)
        if ratio < 1.0:
            result.errors.append(
                f"Parse 调用 {len(result.parse_sites)} 次，Delete 仅 {result.delete_count} 次 — "
                f"比例 {ratio:.1f}，可能存在泄漏"
            )

        # 按函数分组检查
        func_parse: dict[str, int] = {}
        func_delete_lines: dict[str, list[int]] = {}

        for site in result.parse_sites:
            func_parse[site.func_name] = func_parse.get(site.func_name, 0) + 1

        for i, line in enumerate(lines):
            if DELETE_PATTERN.search(line):
                fn = find_function_at_line(lines, i)
                func_delete_lines.setdefault(fn, []).append(i + 1)

        for func, parse_count in func_parse.items():
            del_count = len(func_delete_lines.get(func, []))
            if del_count < parse_count:
                result.errors.append(
                    f"函数 '{func}()': {parse_count} 次 Parse，仅 {del_count} 次 Delete — "
                    f"请确认所有退出分支（含 early return / goto）都调用了 cJSON_Delete"
                )

        # Parse 之后、首次 Delete 之前的 return 视为泄漏路径
        func_bodies: dict[str, list[tuple[int, str]]] = {}
        current_func = "global"
        func_pat = re.compile(
            r"(?:static\s+)?(?:inline\s+)?[\w\s\*]+\s+(\w+)\s*\([^;]*\)\s*$"
        )
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith("extern "):
                continue
            m = func_pat.search(stripped)
            if m:
                current_func = m.group(1)
            func_bodies.setdefault(current_func, []).append((i + 1, line))

        for func in func_parse:
            body_lines = func_bodies.get(func, [])
            if not body_lines:
                continue
            parse_lines = [s.line_no for s in result.parse_sites if s.func_name == func]
            delete_lines = func_delete_lines.get(func, [])
            if not parse_lines:
                continue
            first_parse = min(parse_lines)
            first_delete = min(delete_lines) if delete_lines else 10**9
            for line_no, text in body_lines:
                if line_no <= first_parse:
                    continue
                stripped = text.strip()
                if stripped.startswith("//") or stripped.startswith("/*"):
                    continue
                if not re.search(r"\breturn\b", stripped) or line_no >= first_delete:
                    continue
                segment = "\n".join(
                    t for ln, t in body_lines if first_parse < ln <= line_no
                )
                # Parse 失败直接 return（root/json 仍为 NULL）不算泄漏
                if re.search(
                    r"if\s*\(\s*(?:root|json)\s*==\s*NULL|if\s*\(\s*!\s*(?:root|json)\b",
                    segment,
                ):
                    if not re.search(
                        r"cJSON_GetObjectItem|cJSON_IsString|cJSON_IsNumber|cJSON_IsObject",
                        segment,
                    ):
                        continue
                result.errors.append(
                    f"函数 '{func}()': L{line_no} return 早于 cJSON_Delete — 疑似泄漏路径"
                )
                break

    # Create 对象也需要 Delete
    if result.create_count > 0 and result.delete_count < result.create_count:
        result.warnings.append(
            f"cJSON_Create* 调用 {result.create_count} 次，Delete 仅 {result.delete_count} 次"
        )

    # 检查常见反模式
    if re.search(r"cJSON_Parse\s*\([^)]+\)\s*;", content):
        result.warnings.append(
            "检测到 Parse 结果未赋值给变量 — 无法追踪释放"
        )

    if re.search(r"return\s*;", content) and result.parse_sites:
        # 粗略：有 parse 且有裸 return 的函数
        for site in result.parse_sites:
            func_body = _extract_func_body(lines, site.line_no - 1)
            if func_body and re.search(r"return\s*;", func_body) and "cJSON_Delete" not in func_body:
                result.warnings.append(
                    f"第 {site.line_no} 行附近函数存在 return 但未见 cJSON_Delete — 检查错误分支"
                )

    return result


def _extract_func_body(lines: list[str], start_idx: int) -> str:
    """粗略提取从某行到下一个 '}' 的文本。"""
    depth = 0
    body: list[str] = []
    for i in range(start_idx, min(start_idx + 80, len(lines))):
        body.append(lines[i])
        depth += lines[i].count("{") - lines[i].count("}")
        if depth <= 0 and "{" in "".join(body):
            break
    return "\n".join(body)


def format_report(result: CheckResult) -> str:
    lines = [
        "=" * 60,
        f"cJSON 泄漏审查: {result.file}",
        "=" * 60,
        f"Parse  调用: {len(result.parse_sites)}",
        f"Delete 调用: {result.delete_count}",
        f"Create 调用: {result.create_count}",
        "",
    ]

    if result.parse_sites:
        lines.append("Parse 站点:")
        for s in result.parse_sites:
            lines.append(f"  L{s.line_no} [{s.func_name}()]: {s.line_text[:80]}")
        lines.append("")

    if result.errors:
        lines.append("🔴 错误:")
        for e in result.errors:
            lines.append(f"  • {e}")
        lines.append("")

    if result.warnings:
        lines.append("🟡 警告:")
        for w in result.warnings:
            lines.append(f"  • {w}")
        lines.append("")

    if not result.errors and not result.warnings:
        lines.append("✅ 通过：Parse/Delete 比例正常，未发现明显泄漏模式。")
    elif not result.errors:
        lines.append("⚠️  有警告，请人工复核所有退出路径。")
    else:
        lines.append("❌ 未通过：请修复后重新运行本工具。")

    lines.append("")
    lines.append("ℹ️  本工具为静态启发式辅助，可能有误报/漏报，不能替代 Code Review。")
    return "\n".join(lines)


def format_report_json(result: CheckResult) -> dict:
    """输出 JSON 格式（CI 集成）。"""
    violations = []
    for e in result.errors:
        violations.append({"severity": "error", "rule": "C3", "message": e})
    for w in result.warnings:
        violations.append({"severity": "warning", "rule": "C3", "message": w})
    return {
        "checker": "cjson_leak_checker",
        "file": result.file,
        "summary": {
            "parse_sites": len(result.parse_sites),
            "delete_count": result.delete_count,
            "create_count": result.create_count,
            "errors": len(result.errors),
            "warnings": len(result.warnings),
        },
        "parse_sites": [
            {"line": s.line_no, "func": s.func_name, "text": s.line_text[:120]}
            for s in result.parse_sites
        ],
        "violations": violations,
    }


def main() -> int:
    configure_stdout()
    parser = argparse.ArgumentParser(description="cJSON 静态泄漏审查")
    parser.add_argument("file", nargs="?", help="待检查的 .c/.h 文件路径")
    parser.add_argument("--stdin", action="store_true", help="从标准输入读取")
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式（CI 集成）")
    args = parser.parse_args()

    if args.stdin:
        content = sys.stdin.read()
        result = analyze(content)
    elif args.file:
        path = Path(args.file)
        if not path.exists():
            print(f"错误: 文件不存在: {path}", file=sys.stderr)
            return 1
        content = path.read_text(encoding="utf-8", errors="replace")
        result = analyze(content, str(path))
    else:
        parser.print_help()
        return 1

    if args.json:
        from checker_io import output_json
        output_json(format_report_json(result))
    else:
        print(format_report(result))
    return 1 if result.errors else 0


if __name__ == "__main__":
    sys.exit(main())
