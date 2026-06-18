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

PARSE_ASSIGN_PATTERN = re.compile(
    r"\b(?P<var>[A-Za-z_]\w*)\s*=\s*(?:\([^)]*\)\s*)?"
    r"cJSON_Parse(?:WithLength|WithOpts)?\s*\("
)
CONTROL_KEYWORDS = {"if", "for", "while", "switch", "return", "sizeof"}


@dataclass
class ParseSite:
    line_no: int
    line_text: str
    func_name: str = "global"
    var_name: str | None = None


@dataclass
class FunctionSpan:
    name: str
    start: int
    end: int


@dataclass
class CheckResult:
    file: str
    parse_sites: list[ParseSite] = field(default_factory=list)
    delete_count: int = 0
    create_count: int = 0
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def strip_comments_preserve_lines(content: str) -> list[str]:
    """Remove C/C++ comments while preserving line numbers."""
    out: list[str] = []
    in_block = False
    for raw in content.splitlines():
        i = 0
        cleaned: list[str] = []
        while i < len(raw):
            if in_block:
                end = raw.find("*/", i)
                if end == -1:
                    i = len(raw)
                else:
                    in_block = False
                    i = end + 2
                continue
            if raw.startswith("//", i):
                break
            if raw.startswith("/*", i):
                in_block = True
                i += 2
                continue
            cleaned.append(raw[i])
            i += 1
        out.append("".join(cleaned))
    return out


def _match_function_header(text: str) -> str | None:
    if not text or text.endswith(";"):
        return None
    collapsed = " ".join(text.strip().split())
    m = re.search(r"\b([A-Za-z_]\w*)\s*\([^;{}]*\)\s*$", collapsed)
    if not m:
        return None
    name = m.group(1)
    if name in CONTROL_KEYWORDS:
        return None
    prefix = collapsed[: m.start(1)].strip()
    if not prefix:
        return None
    return name


def build_function_spans(lines: list[str]) -> tuple[list[FunctionSpan], list[str]]:
    spans: list[FunctionSpan] = []
    line_to_func = ["global"] * len(lines)
    current_name: str | None = None
    current_start = 0
    depth = 0
    pending_name: str | None = None
    pending_start = 0

    for i, line in enumerate(lines):
        stripped = line.strip()
        if current_name is None:
            if pending_name is not None:
                if "{" in stripped:
                    current_name = pending_name
                    current_start = pending_start
                    depth = line.count("{") - line.count("}")
                    for j in range(current_start, i + 1):
                        line_to_func[j] = current_name
                    pending_name = None
                    if depth <= 0:
                        spans.append(FunctionSpan(current_name, current_start, i))
                        current_name = None
                    continue
                if stripped.endswith(";") or not stripped:
                    pending_name = None

            if "{" in stripped:
                header = stripped.split("{", 1)[0].strip()
                name = _match_function_header(header)
                if name:
                    current_name = name
                    current_start = i
                    depth = line.count("{") - line.count("}")
                    line_to_func[i] = current_name
                    if depth <= 0:
                        spans.append(FunctionSpan(current_name, current_start, i))
                        current_name = None
                    continue

            name = _match_function_header(stripped)
            if name:
                pending_name = name
                pending_start = i
            continue

        line_to_func[i] = current_name
        depth += line.count("{") - line.count("}")
        if depth <= 0:
            spans.append(FunctionSpan(current_name, current_start, i))
            current_name = None

    return spans, line_to_func


def _line_deletes_var(line: str, var: str) -> bool:
    return re.search(rf"\bcJSON_Delete\s*\(\s*{re.escape(var)}\s*\)", line) is not None


def _is_null_guard_exit(body: list[tuple[int, str]], var: str, exit_idx: int) -> bool:
    start = max(0, exit_idx - 4)
    window = "\n".join(line for _, line in body[start : exit_idx + 1])
    null_guard = re.search(
        rf"\bif\s*\(\s*(?:{re.escape(var)}\s*==\s*NULL|"
        rf"NULL\s*==\s*{re.escape(var)}|!\s*{re.escape(var)})\s*\)",
        window,
    )
    if not null_guard:
        return False
    used_after_parse = re.search(
        rf"{re.escape(var)}\s*->|cJSON_GetObjectItem|cJSON_Is\w+\s*\(",
        window,
    )
    return used_after_parse is None


def _block_segment_before_exit(body: list[tuple[int, str]], exit_idx: int) -> str:
    start = 0
    for j in range(exit_idx, -1, -1):
        text = body[j][1].strip()
        if "{" in text or re.match(r"^[A-Za-z_]\w*\s*:\s*$", text):
            start = j
            break
    return "\n".join(line for _, line in body[start : exit_idx + 1])


def _label_deletes_var(body: list[tuple[int, str]], label: str, var: str) -> bool:
    for idx, (_, line) in enumerate(body):
        if not re.match(rf"^\s*{re.escape(label)}\s*:\s*(?:/\*.*\*/)?\s*$", line):
            continue
        for _, label_line in body[idx + 1 :]:
            if re.match(r"^\s*[A-Za-z_]\w*\s*:\s*$", label_line):
                return False
            if _line_deletes_var(label_line, var):
                return True
            if re.search(r"\breturn\b", label_line):
                return False
    return False


def _function_body_for(
    spans: list[FunctionSpan],
    clean_lines: list[str],
    func_name: str,
) -> list[tuple[int, str]]:
    for span in spans:
        if span.name == func_name:
            return [(i + 1, clean_lines[i]) for i in range(span.start, span.end + 1)]
    return [(i + 1, line) for i, line in enumerate(clean_lines)]


def analyze(content: str, filename: str = "<stdin>") -> CheckResult:
    result = CheckResult(file=filename)
    raw_lines = content.splitlines()
    lines = strip_comments_preserve_lines(content)
    spans, line_to_func = build_function_spans(lines)

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue

        for pat in PARSE_PATTERNS:
            if pat.search(line):
                func = line_to_func[i]
                var_match = PARSE_ASSIGN_PATTERN.search(line)
                result.parse_sites.append(
                    ParseSite(
                        line_no=i + 1,
                        line_text=raw_lines[i].strip(),
                        func_name=func,
                        var_name=var_match.group("var") if var_match else None,
                    )
                )

        if DELETE_PATTERN.search(line):
            result.delete_count += 1

        if CREATE_PATTERN.search(line):
            result.create_count += 1

    if result.parse_sites:
        for site in result.parse_sites:
            func_body = _function_body_for(spans, lines, site.func_name)
            local_parse_idx = next(
                (idx for idx, (line_no, _) in enumerate(func_body) if line_no == site.line_no),
                None,
            )
            if local_parse_idx is None:
                continue

            var = site.var_name
            if var is None:
                result.errors.append(
                    f"函数 '{site.func_name}()': L{site.line_no} Parse 结果未赋值 — 无法释放 cJSON 树"
                )
                continue

            delete_lines = [
                line_no
                for line_no, text in func_body[local_parse_idx + 1 :]
                if _line_deletes_var(text, var)
            ]
            if not delete_lines:
                result.errors.append(
                    f"函数 '{site.func_name}()': L{site.line_no} 解析到 '{var}' 后未发现 cJSON_Delete({var})"
                )

            for idx in range(local_parse_idx + 1, len(func_body)):
                line_no, text = func_body[idx]
                stripped = text.strip()
                if not stripped:
                    continue

                goto_match = re.search(r"\bgoto\s+([A-Za-z_]\w*)\s*;", stripped)
                if goto_match:
                    if _is_null_guard_exit(func_body, var, idx):
                        continue
                    label = goto_match.group(1)
                    if _label_deletes_var(func_body, label, var):
                        continue
                    result.errors.append(
                        f"函数 '{site.func_name}()': L{line_no} goto {label} 早于 cJSON_Delete({var})"
                    )
                    continue

                if not re.search(r"\b(return|continue|break)\b", stripped):
                    continue
                if _is_null_guard_exit(func_body, var, idx):
                    continue
                segment = _block_segment_before_exit(func_body, idx)
                if _line_deletes_var(segment, var):
                    continue
                result.errors.append(
                    f"函数 '{site.func_name}()': L{line_no} 提前退出早于 cJSON_Delete({var})"
                )

    # Create 对象也需要 Delete
    if result.create_count > 0 and result.delete_count < result.create_count:
        result.warnings.append(
            f"cJSON_Create* 调用 {result.create_count} 次，Delete 仅 {result.delete_count} 次"
        )

    # 检查常见反模式
    if any(site.var_name is None for site in result.parse_sites):
        result.warnings.append(
            "检测到 Parse 结果未赋值给变量 — 无法追踪释放"
        )

    return result


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


def format_fix_suggest(result: CheckResult, content: str) -> str:
    """Print a compact cleanup pattern after the normal report."""
    del content
    return "\n\n".join(
        [
            format_report(result),
            """建议模板:

```c
int ret = -1;
cJSON *root = cJSON_Parse(json);
if (root == NULL) {
    return -1;
}

/* parse fields; use goto cleanup on every failure after root is non-NULL */
ret = 0;

cleanup:
if (root != NULL) {
    cJSON_Delete(root);
}
return ret;
```""",
        ]
    )


def main() -> int:
    configure_stdout()
    parser = argparse.ArgumentParser(description="cJSON 静态泄漏审查")
    parser.add_argument("file", nargs="?", help="待检查的 .c/.h 文件路径")
    parser.add_argument("--dir", "-d", help="递归检查目录下的 .c/.h/.cpp 文件")
    parser.add_argument(
        "--platform",
        help="兼容旧 workflow 参数；cJSON 泄漏检查不使用平台值",
    )
    parser.add_argument("--stdin", action="store_true", help="从标准输入读取")
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式（CI 集成）")
    parser.add_argument("--fix-suggest", action="store_true", help="输出修复建议代码骨架")
    args = parser.parse_args()

    if args.stdin:
        content = sys.stdin.read()
        result = analyze(content)
        if args.json:
            from checker_io import output_json
            output_json(format_report_json(result))
        elif args.fix_suggest:
            print(format_fix_suggest(result, content))
        else:
            print(format_report(result))
        return 1 if result.errors else 0

    targets: list[Path] = []
    if args.file:
        targets.append(Path(args.file))
    if args.dir:
        root = Path(args.dir)
        if not root.is_dir():
            print(f"错误: 目录不存在: {root}", file=sys.stderr)
            return 1
        for suffix in ("*.c", "*.h", "*.cpp"):
            targets.extend(sorted(root.rglob(suffix)))

    if not targets:
        parser.print_help()
        return 1

    results: list[CheckResult] = []
    contents: dict[str, str] = {}
    seen: set[Path] = set()
    for path in targets:
        path = path.resolve()
        if path in seen:
            continue
        seen.add(path)
        if not path.exists():
            print(f"错误: 文件不存在: {path}", file=sys.stderr)
            return 1
        content = path.read_text(encoding="utf-8", errors="replace")
        contents[str(path)] = content
        results.append(analyze(content, str(path)))

    if args.json:
        from checker_io import output_json
        if len(results) == 1:
            output_json(format_report_json(results[0]))
        else:
            output_json(
                {
                    "checker": "cjson_leak_checker",
                    "files": [format_report_json(result) for result in results],
                    "summary": {
                        "files": len(results),
                        "errors": sum(len(result.errors) for result in results),
                        "warnings": sum(len(result.warnings) for result in results),
                    },
                }
            )
    elif args.fix_suggest:
        shown = [r for r in results if r.parse_sites or r.errors or r.warnings]
        for idx, result in enumerate(shown):
            if idx:
                print()
            print(format_fix_suggest(result, contents[result.file]))
    else:
        shown = [r for r in results if r.parse_sites or r.errors or r.warnings]
        for idx, result in enumerate(shown):
            if idx:
                print()
            print(format_report(result))
        if len(results) > 1:
            clean = len(results) - len(shown)
            print()
            print("=" * 60)
            print(
                f"Summary: 扫描 {len(results)} 个文件；"
                f"有 cJSON 站点/告警 {len(shown)} 个；"
                f"无 cJSON 站点 {clean} 个；"
                f"错误 {sum(len(result.errors) for result in results)} 个"
            )
            print("=" * 60)
    return 1 if any(result.errors for result in results) else 0


if __name__ == "__main__":
    sys.exit(main())
