#!/usr/bin/env python3
"""
ISR / HAL 回调阻塞 API 静态审查工具。

扫描 IRQHandler、HAL_*_Callback、FromISR 上下文中的阻塞 FreeRTOS 调用。

用法:
    python tools/isr_safety_checker.py path/to/file.c
    python tools/isr_safety_checker.py --dir ./src
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# 仅匹配 ISR/HAL 回调的函数定义行，勿把任务内的 *FromISR 调用误判为 ISR
ISR_FUNC_DEF = re.compile(
    r"^(?:static\s+)?(?:inline\s+)?(?:void|int|BaseType_t)\s+"
    r"(\w*(?:IRQHandler|Callback|_ISR|_Isr)\w*)\s*\([^;]*\)\s*\{?\s*$"
)
ISR_ATTR = re.compile(r"__attribute__\s*\(\s*\(\s*interrupt")

BLOCKING_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bvTaskDelay\s*\("), "vTaskDelay — ISR 中禁止"),
    (re.compile(r"\bvTaskDelayUntil\s*\("), "vTaskDelayUntil — ISR 中禁止"),
    (re.compile(r"\bxSemaphoreTake\s*\("), "xSemaphoreTake — 须用 TakeFromISR"),
    (re.compile(r"\bxSemaphoreGive\s*\("), "xSemaphoreGive — 须用 GiveFromISR"),
    (re.compile(r"\bxQueueSend\s*\("), "xQueueSend — 须用 SendFromISR"),
    (re.compile(r"\bxQueueReceive\s*\("), "xQueueReceive — ISR 中禁止阻塞接收"),
    (re.compile(r"\bxTaskNotify\s*\("), "xTaskNotify — 须用 NotifyFromISR"),
    (re.compile(r"\bos_sem_pend\s*\("), "os_sem_pend — 杰理 ISR 中禁止"),
    (re.compile(r"\bos_mutex_pend\s*\("), "os_mutex_pend — ISR 中禁止"),
    (re.compile(r"\bthread_delay_ms\s*\("), "thread_delay_ms — ISR 中禁止"),
    (re.compile(r"\bprintf\s*\("), "printf — ISR 中可能阻塞"),
    (re.compile(r"\bcJSON_Parse\s*\("), "cJSON_Parse — ISR 中禁止（malloc）"),
    (re.compile(r"\bmalloc\s*\("), "malloc — ISR 中禁止"),
    (re.compile(r"\bpvPortMalloc\s*\("), "pvPortMalloc — ISR 中禁止"),
    (re.compile(r"\bportMAX_DELAY\b"), "portMAX_DELAY — ISR 中禁止无限等待"),
]

PORT_YIELD_PATTERN = re.compile(r"\bportYIELD_FROM_ISR\s*\(")


@dataclass
class Violation:
    line_no: int
    func_hint: str
    api: str
    line_text: str


@dataclass
class CheckResult:
    file: str
    violations: list[Violation] = field(default_factory=list)
    isr_functions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def find_function_name(lines: list[str], line_idx: int) -> str:
    pat = re.compile(r"(?:static\s+)?(?:void|int|BaseType_t)\s+(\w+)\s*\(")
    for i in range(line_idx, max(line_idx - 30, -1), -1):
        m = pat.search(lines[i])
        if m:
            return m.group(1)
    return "unknown"


def is_isr_function_start(line: str) -> bool:
    stripped = line.strip()
    if stripped.startswith("//") or stripped.startswith("/*"):
        return False
    if ISR_ATTR.search(line):
        return True
    return ISR_FUNC_DEF.match(stripped) is not None


def extract_function_body(lines: list[str], start: int) -> tuple[str, int, int]:
    """返回 (func_name, body_start, body_end)。"""
    func_name = find_function_name(lines, start)
    brace = 0
    body_start = start
    for i in range(start, len(lines)):
        if "{" in lines[i]:
            brace += lines[i].count("{")
            body_start = i
            break
    if brace == 0:
        return func_name, start, min(start + 40, len(lines))

    for i in range(body_start, len(lines)):
        brace += lines[i].count("{") - lines[i].count("}")
        if brace <= 0 and i > body_start:
            return func_name, body_start, i + 1
    return func_name, body_start, len(lines)


def analyze_content(content: str, filename: str) -> CheckResult:
    result = CheckResult(file=filename)
    lines = content.splitlines()

    i = 0
    while i < len(lines):
        if is_isr_function_start(lines[i]):
            func_name, body_start, body_end = extract_function_body(lines, i)
            result.isr_functions.append(f"L{i + 1} {func_name}()")

            body_lines = lines[body_start:body_end]
            body_text = "\n".join(body_lines)
            has_fromisr_notify = bool(
                re.search(r"(Notify|Give|Send)FromISR", body_text)
            )
            has_yield = bool(PORT_YIELD_PATTERN.search(body_text))

            for j, bline in enumerate(body_lines):
                for pattern, desc in BLOCKING_PATTERNS:
                    if pattern.search(bline):
                        # xSemaphoreGiveFromISR 不算 xSemaphoreGive 违规
                        if "GiveFromISR" in bline or "TakeFromISR" in bline:
                            continue
                        if "SendFromISR" in bline or "NotifyFromISR" in bline:
                            continue
                        result.violations.append(
                            Violation(
                                line_no=body_start + j + 1,
                                func_hint=func_name,
                                api=desc,
                                line_text=bline.strip()[:100],
                            )
                        )

            if has_fromisr_notify and not has_yield:
                result.warnings.append(
                    f"函数 {func_name}() 使用了 FromISR API 但未调用 portYIELD_FROM_ISR"
                )
        i += 1

    return result


def format_report(result: CheckResult) -> str:
    out = [
        "=" * 60,
        f"ISR 安全审查: {result.file}",
        "=" * 60,
        f"检测到 ISR/HAL 回调: {len(result.isr_functions)}",
        "",
    ]
    if result.isr_functions:
        out.append("ISR 函数:")
        for f in result.isr_functions[:20]:
            out.append(f"  • {f}")
        out.append("")

    if result.violations:
        out.append("🔴 违规:")
        for v in result.violations:
            out.append(f"  L{v.line_no} [{v.func_hint}]: {v.api}")
            out.append(f"      {v.line_text}")
        out.append("")

    if result.warnings:
        out.append("🟡 警告:")
        for w in result.warnings:
            out.append(f"  • {w}")
        out.append("")

    if not result.violations and not result.warnings:
        out.append("✅ 通过：未检测到 ISR 中阻塞 API。")
    elif not result.violations:
        out.append("⚠️  有警告，请人工复核。")
    else:
        out.append("❌ 未通过：参照 examples/bad_isr_blocking.c 修复。")

    out.append("")
    out.append("ℹ️  本工具为静态启发式辅助，可能有误报/漏报，不能替代 Code Review。")
    return "\n".join(out)


def collect_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    return sorted(path.rglob("*.c")) + sorted(path.rglob("*.h"))


def main() -> int:
    parser = argparse.ArgumentParser(description="ISR 阻塞 API 静态审查")
    parser.add_argument("path", nargs="?", help=".c/.h 文件或目录")
    parser.add_argument("--dir", "-d", help="扫描目录")
    args = parser.parse_args()

    target = args.dir or args.path
    if not target:
        parser.print_help()
        return 1

    root = Path(target)
    if not root.exists():
        print(f"错误: 路径不存在: {root}", file=sys.stderr)
        return 1

    files = collect_files(root)
    if not files:
        print("未找到 .c/.h 文件", file=sys.stderr)
        return 1

    exit_code = 0
    for f in files:
        content = f.read_text(encoding="utf-8", errors="replace")
        result = analyze_content(content, str(f))
        print(format_report(result))
        print()
        if result.violations:
            exit_code = 1

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
