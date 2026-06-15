#!/usr/bin/env python3
"""
Queue payload 所有权静态审查（铁律 #2）。

检测 xQueueSend 链路中的违规：
  - 向 Queue 传递 cJSON* 或含 cJSON* 的字段
  - payload 指向栈上 buffer（函数返回后悬空）

用法:
    python tools/queue_ownership_checker.py path/to/file.c
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

QUEUE_SEND = re.compile(
    r"\bxQueue(?:Send|SendToBack|SendFromISR|Overwrite)\s*\("
)
STACK_ARRAY = re.compile(
    r"(?:char|uint8_t|int8_t)\s+(\w+)\s*\[[^\]]+\]"
)
CJSON_DECL = re.compile(r"\bcJSON\s*\*\s*(\w+)\b")
PAYLOAD_ASSIGN = re.compile(
    r"\.(?:payload|data|obj|message|buf|ptr)\s*=\s*(?:\([^)]*\)\s*)?(?:&)?(\w+)\s*;"
)
PTR_FROM_STACK = re.compile(
    r"(?:char|uint8_t|int8_t)\s*\*\s*(\w+)\s*=\s*(?:&)?(\w+)\s*;"
)
FUNC_START = re.compile(
    r"^(?:static\s+)?(?:inline\s+)?(?:\w+\s+)+\w+\s*\([^;]*\)\s*\{?\s*$"
)


@dataclass
class Violation:
    line_no: int
    kind: str
    detail: str
    line_text: str


@dataclass
class CheckResult:
    file: str
    violations: list[Violation] = field(default_factory=list)


def find_function_at_line(lines: list[str], line_idx: int) -> str:
    for i in range(line_idx, -1, -1):
        if FUNC_START.match(lines[i].strip()):
            return lines[i].strip()[:60]
    return "global"


def _func_region(lines: list[str], send_line_idx: int) -> tuple[int, int]:
    """从 xQueueSend 行向上找函数起点，向下找粗略函数结尾。"""
    start = send_line_idx
    for i in range(send_line_idx, -1, -1):
        if FUNC_START.match(lines[i].strip()):
            start = i
            break
    depth = 0
    end = send_line_idx
    for i in range(start, len(lines)):
        depth += lines[i].count("{") - lines[i].count("}")
        end = i
        if i > start and depth <= 0 and "{" in "".join(lines[start : i + 1]):
            break
    return start, end


def analyze(content: str, filename: str = "<stdin>") -> CheckResult:
    result = CheckResult(file=filename)
    lines = content.splitlines()

    send_indices = [
        i for i, line in enumerate(lines)
        if QUEUE_SEND.search(line) and not line.strip().startswith("//")
    ]

    for idx in send_indices:
        line = lines[idx]
        stripped = line.strip()
        func = find_function_at_line(lines, idx)
        start, end = _func_region(lines, idx)
        region = lines[start : end + 1]
        region_text = "\n".join(region)

        stack_vars: set[str] = set()
        for m in STACK_ARRAY.finditer(region_text):
            stack_vars.add(m.group(1))

        ptr_from_stack: dict[str, str] = {}
        for m in PTR_FROM_STACK.finditer(region_text):
            ptr_name, src = m.group(1), m.group(2)
            if src in stack_vars:
                ptr_from_stack[ptr_name] = src

        cjson_vars: set[str] = set()
        for m in CJSON_DECL.finditer(region_text):
            cjson_vars.add(m.group(1))

        if re.search(r"cJSON", line, re.I):
            result.violations.append(
                Violation(
                    line_no=idx + 1,
                    kind="cJSON_in_queue_send",
                    detail="xQueueSend 调用行含 cJSON — 禁止向 Queue 传 cJSON*",
                    line_text=stripped[:100],
                )
            )

        for m in PAYLOAD_ASSIGN.finditer(region_text):
            rhs = m.group(1)
            assign_line = region_text[: m.start()].count("\n") + start + 1
            if rhs in stack_vars:
                result.violations.append(
                    Violation(
                        line_no=assign_line,
                        kind="stack_payload",
                        detail=f".payload/.data 指向栈变量 '{rhs}' — Presenter 收到悬空指针",
                        line_text=lines[assign_line - 1].strip()[:100],
                    )
                )
            if rhs in cjson_vars:
                result.violations.append(
                    Violation(
                        line_no=assign_line,
                        kind="cjson_payload",
                        detail=f"字段赋值为 cJSON* '{rhs}' — cJSON 不得进 Queue",
                        line_text=lines[assign_line - 1].strip()[:100],
                    )
                )

        # xQueueSend(q, &cjson_var, ...) — 队列元素为指针时直接传 cJSON*
        send_m = re.search(
            r"xQueue(?:Send|SendToBack|SendFromISR)\s*\(\s*[^,]+,\s*&(\w+)",
            line,
        )
        if send_m:
            arg = send_m.group(1)
            if arg in cjson_vars:
                result.violations.append(
                    Violation(
                        line_no=idx + 1,
                        kind="cjson_queue_element",
                        detail=f"xQueueSend 传递 cJSON* '&{arg}'",
                        line_text=stripped[:100],
                    )
                )
            if arg in stack_vars:
                result.violations.append(
                    Violation(
                        line_no=idx + 1,
                        kind="stack_queue_element",
                        detail=f"xQueueSend 传递栈 buffer '&{arg}'",
                        line_text=stripped[:100],
                    )
                )
            if arg in ptr_from_stack:
                result.violations.append(
                    Violation(
                        line_no=idx + 1,
                        kind="stack_ptr_queue_element",
                        detail=f"xQueueSend 传递指向栈 '{ptr_from_stack[arg]}' 的指针 '&{arg}'",
                        line_text=stripped[:100],
                    )
                )

        # Parse 结果直接进 Queue（常见反模式）
        if re.search(
            r"xQueue\w+.*\bcJSON_(?:Parse|Create)",
            region_text,
            re.DOTALL,
        ):
            result.violations.append(
                Violation(
                    line_no=idx + 1,
                    kind="parse_to_queue",
                    detail=f"函数内 cJSON_Parse/Create 与 xQueueSend 同域 — 确认未传 root 指针",
                    line_text=stripped[:100],
                )
            )

    # 去重（同 line + kind）
    seen: set[tuple[int, str]] = set()
    unique: list[Violation] = []
    for v in result.violations:
        key = (v.line_no, v.kind)
        if key not in seen:
            seen.add(key)
            unique.append(v)
    result.violations = unique
    return result


def format_report(result: CheckResult) -> str:
    out = [
        "=" * 60,
        f"Queue payload 所有权审查: {result.file}",
        "=" * 60,
        f"违规数: {len(result.violations)}",
        "",
    ]

    if result.violations:
        out.append("🔴 铁律 #2 违规（参照 examples/bad_queue_stack_pointer.c）:")
        for v in result.violations:
            out.append(f"  L{v.line_no} [{v.kind}]: {v.detail}")
            out.append(f"      {v.line_text}")
        out.append("")
        out.append("正例: examples/good_presenter_consumer.c（heap payload + Presenter vPortFree）")
        out.append("❌ 未通过：请修复 Queue payload 所有权后重试。")
    else:
        out.append("✅ 通过：未检测到栈指针/cJSON* 进 Queue 的明显模式。")

    out.append("")
    out.append("ℹ️  本工具为静态启发式辅助，可能有误报/漏报，不能替代 Code Review。")
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description="Queue payload 所有权审查（铁律 #2）")
    parser.add_argument("file", help="待检查的 .c/.h 文件路径")
    args = parser.parse_args()

    path = Path(args.file)
    if not path.exists():
        print(f"错误: 文件不存在: {path}", file=sys.stderr)
        return 1

    content = path.read_text(encoding="utf-8", errors="replace")
    result = analyze(content, str(path))
    print(format_report(result))
    return 1 if result.violations else 0


if __name__ == "__main__":
    sys.exit(main())
