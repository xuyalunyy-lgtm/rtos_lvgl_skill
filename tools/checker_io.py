"""Checker 脚本共用基础设施。

提供：
  - configure_stdout: Windows GBK 控制台 UTF-8 输出
  - output_json / safe_print: 安全输出
  - read_file: 统一文件读取
  - strip_comments: 统一注释剥离
  - extract_functions: 统一函数提取
  - find_matching_brace: 统一花括号匹配
  - make_issue: 统一 issue 构建
  - collect_targets: 统一文件收集
  - run_checker: 统一 main() 框架
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

# Force UTF-8 on Windows
if sys.platform == "win32":
    os.environ.setdefault("PYTHONUTF8", "1")


# ============================================================================
# 输出配置
# ============================================================================

def configure_stdout() -> None:
    """配置 stdout/stderr 为 UTF-8（Windows GBK 兼容）。"""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def output_json(data: dict[str, Any], file=None) -> None:
    """输出 JSON 格式结果（CI 集成 / 机器可读）。"""
    stream = file or sys.stdout
    try:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        print(file=stream)
    except UnicodeEncodeError:
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
            json.dump(data, stream, ensure_ascii=False, indent=2)
            print(file=stream)
        else:
            raise


def safe_print(text: str, file=None) -> None:
    """Print with UTF-8 fallback for Windows GBK consoles."""
    stream = file or sys.stdout
    try:
        print(text, end="", file=stream)
    except UnicodeEncodeError:
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
            print(text, end="", file=stream)
        else:
            raise


# ============================================================================
# 文件读取
# ============================================================================

def read_file(path: Path) -> tuple[list[str], str] | None:
    """统一文件读取，返回 (lines, text) 或 None。"""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        return text.splitlines(), text
    except OSError:
        return None


# ============================================================================
# C/C++ 解析工具（状态机驱动，感知字符串/字符字面量）
# ============================================================================

FUNC_DEF_RE = re.compile(
    r"(?:^|[\n;])\s*"
    r"(?:static\s+)?(?:inline\s+)?(?:__attribute__\s*\(\([^)]*\)\)\s*)?"
    r"(?:[A-Za-z_][\w]*\s+)+"
    r"(?:\*\s*)?"
    r"(?P<name>[A-Za-z_]\w*)\s*\([^;{}]*\)\s*\{",
    re.MULTILINE,
)

# 状态常量
_ST_CODE = 0
_ST_LINE_COMMENT = 1
_ST_BLOCK_COMMENT = 2
_ST_STRING = 3
_ST_CHAR = 4


def _skip_string_literals(text: str) -> set[int]:
    """返回所有属于字符串/字符字面量的字符位置集合。"""
    positions: set[int] = set()
    state = _ST_CODE
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if state == _ST_CODE:
            if ch == "/" and i + 1 < n:
                nxt = text[i + 1]
                if nxt == "/":
                    state = _ST_LINE_COMMENT
                elif nxt == "*":
                    state = _ST_BLOCK_COMMENT
            elif ch == '"':
                state = _ST_STRING
                positions.add(i)
            elif ch == "'":
                state = _ST_CHAR
                positions.add(i)
        elif state == _ST_LINE_COMMENT:
            if ch == "\n":
                state = _ST_CODE
        elif state == _ST_BLOCK_COMMENT:
            if ch == "*" and i + 1 < n and text[i + 1] == "/":
                i += 1
                state = _ST_CODE
        elif state == _ST_STRING:
            positions.add(i)
            if ch == "\\" and i + 1 < n:
                i += 1
                positions.add(i)
            elif ch == '"':
                state = _ST_CODE
        elif state == _ST_CHAR:
            positions.add(i)
            if ch == "\\" and i + 1 < n:
                i += 1
                positions.add(i)
            elif ch == "'":
                state = _ST_CODE
        i += 1
    return positions


def strip_comments(text: str) -> str:
    """剥离 C/C++ 注释，保留行数。感知字符串/字符字面量。"""
    result = list(text)
    state = _ST_CODE
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if state == _ST_CODE:
            if ch == "/" and i + 1 < n:
                nxt = text[i + 1]
                if nxt == "/":
                    state = _ST_LINE_COMMENT
                    result[i] = "\n" if ch == "\n" else ""
                    i += 1
                    result[i] = ""
                elif nxt == "*":
                    state = _ST_BLOCK_COMMENT
                    result[i] = ""
                    i += 1
                    result[i] = ""
                # else: division operator, keep
            # string/char literals: keep as-is
            elif ch == '"':
                state = _ST_STRING
            elif ch == "'":
                state = _ST_CHAR
        elif state == _ST_LINE_COMMENT:
            if ch == "\n":
                result[i] = "\n"
                state = _ST_CODE
            else:
                result[i] = ""
        elif state == _ST_BLOCK_COMMENT:
            if ch == "\n":
                result[i] = "\n"
            else:
                result[i] = ""
            if ch == "*" and i + 1 < n and text[i + 1] == "/":
                i += 1
                result[i] = ""
                state = _ST_CODE
        elif state == _ST_STRING:
            if ch == "\\" and i + 1 < n:
                i += 1  # skip escape
            elif ch == '"':
                state = _ST_CODE
        elif state == _ST_CHAR:
            if ch == "\\" and i + 1 < n:
                i += 1
            elif ch == "'":
                state = _ST_CODE
        i += 1
    return "".join(result)


def strip_comments_lines(text: str) -> list[str]:
    """剥离注释并返回行列表。"""
    return strip_comments(text).splitlines()


def line_at(text: str, pos: int) -> int:
    """返回 pos 位置的行号（1-based）。"""
    return text[:pos].count("\n") + 1


def nearby(text: str, pos: int, before: int = 240, after: int = 160) -> str:
    """返回 pos 位置附近的文本。"""
    return text[max(0, pos - before):min(len(text), pos + after)]


def find_matching_brace(text: str, open_pos: int) -> int:
    """找到匹配的右花括号位置。感知字符串/字符字面量。"""
    if open_pos < 0:
        return -1
    skip = _skip_string_literals(text)
    depth = 0
    for i in range(open_pos, len(text)):
        if i in skip:
            continue
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return i
    return -1


@dataclass
class FunctionSpan:
    """函数范围信息。"""
    name: str
    body: str
    line: int


def extract_functions(code: str) -> list[FunctionSpan]:
    """提取所有函数定义。"""
    functions: list[FunctionSpan] = []
    for match in FUNC_DEF_RE.finditer(code):
        name = match.group("name")
        if name in {"if", "for", "while", "switch", "return", "sizeof"}:
            continue
        open_pos = code.find("{", match.end() - 1)
        close_pos = find_matching_brace(code, open_pos)
        if open_pos < 0 or close_pos < 0:
            continue
        functions.append(FunctionSpan(
            name=name,
            body=code[open_pos + 1:close_pos],
            line=line_at(code, match.start("name")),
        ))
    return functions


# ============================================================================
# Issue 构建
# ============================================================================

def make_issue(path: Path, line: int, cid: str, severity: str, msg: str) -> dict[str, str]:
    """构建标准 issue dict。"""
    return {"id": cid, "severity": severity, "file": f"{path}:{line}", "issue": msg}


def make_issue_str(file: str, cid: str, severity: str, msg: str) -> dict[str, str]:
    """构建标准 issue dict（file 已格式化）。"""
    return {"id": cid, "severity": severity, "file": file, "issue": msg}


# ============================================================================
# 文件收集
# ============================================================================

def collect_targets(files: list[str], dir_path: str | None = None,
                    suffixes: set[str] | None = None) -> list[Path]:
    """统一文件收集 + 去重。"""
    if suffixes is None:
        suffixes = {".c", ".h"}

    targets: list[Path] = []
    for item in files:
        path = Path(item)
        if path.is_file() and path.suffix.lower() in suffixes:
            targets.append(path)
        elif path.is_dir():
            for suffix in suffixes:
                targets.extend(sorted(path.rglob(f"*{suffix}")))

    if dir_path:
        root = Path(dir_path)
        if root.is_dir():
            for suffix in suffixes:
                targets.extend(sorted(root.rglob(f"*{suffix}")))

    seen: set[Path] = set()
    unique: list[Path] = []
    for target in targets:
        resolved = target.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(resolved)
    return unique


# ============================================================================
# 统一 Checker 框架
# ============================================================================

def run_checker(
    check_fn: Callable[[Path], list[dict]],
    description: str,
    domains: tuple[str, ...],
    suffixes: set[str] | None = None,
) -> int:
    """统一 checker main() 框架。

    Args:
        check_fn: 检查函数，接收 Path，返回 issue dict 列表
        description: checker 描述
        domains: 约束域 tuple（如 ("C3",)）
        suffixes: 文件后缀（默认 {".c", ".h"}）

    Returns:
        0 = 无违规，1 = 有违规
    """
    configure_stdout()

    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("files", nargs="*", help="待检查文件")
    parser.add_argument("--dir", "-d", help="递归检查目录")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    parser.add_argument(
        "--jsonl", action="store_true",
        help="Emit exactly one JSON Lines protocol record (for tool orchestration)",
    )
    args = parser.parse_args()

    targets = collect_targets(args.files, args.dir, suffixes)

    if not targets:
        print(f"[{description}] 无文件可检查")
        return 0

    all_issues: list[dict] = []
    for path in targets:
        all_issues.extend(check_fn(path))

    domain_str = "/".join(domains)

    if args.json or args.jsonl:
        payload = {
            "protocol_version": "checker-result/v1",
            "checker": description,
            "domains": list(domains),
            "files_checked": len(targets),
            "violations": len(all_issues),
            "issues": all_issues,
        }
        if args.jsonl:
            print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
        else:
            output_json(payload)
        return 1 if all_issues else 0

    if not all_issues:
        print(f"[{description}] 已检查 {len(targets)} 个文件，未发现 {domain_str} 违规")
        return 0

    print(f"[{description}] 已检查 {len(targets)} 个文件，发现 {len(all_issues)} 个 {domain_str} 告警:\n")
    for issue in all_issues:
        sev = issue.get("severity", "?")
        cid = issue.get("id", "?")
        loc = issue.get("file", "?")
        msg = issue.get("issue", "?")
        print(f"  [{sev}] {cid} — {loc} — {msg}")

    print(f"\nSummary: {len(all_issues)} {domain_str} warnings")
    return 1


def run_checker_simple(
    check_fn: Callable[[Path], list[dict]],
    description: str,
    domain: str,
) -> int:
    """简化的 checker main() 框架（单域）。"""
    return run_checker(check_fn, description, (domain,))
