#!/usr/bin/env python3
"""
ISR / HAL 回调阻塞 API 静态审查工具。

扫描 IRQHandler、HAL_*_Callback、FromISR 上下文中的阻塞 FreeRTOS 调用。
"""

from __future__ import annotations

import re
from pathlib import Path

from checker_io import make_issue, read_file, run_checker
from sdk_lookup import SdkLookup

# 全平台 SDK 查询
_ALL_PLATFORMS = ["esp32", "stm32", "jl", "bk", "zephyr"]
_lookup = SdkLookup(_ALL_PLATFORMS)

# 仅匹配 ISR/HAL 回调的函数定义行，勿把任务内的 *FromISR 调用误判为 ISR
ISR_FUNC_DEF = re.compile(
    r"^(?:static\s+)?(?:inline\s+)?(?:void|int|BaseType_t)\s+"
    r"(\w*(?:IRQHandler|Callback|_ISR|_Isr)\w*)\s*\([^;]*\)\s*\{?\s*$"
)
ISR_ATTR = re.compile(r"__attribute__\s*\(\s*\(\s*interrupt")

# --- SDK lookup 构建阻塞模式 ---
_ISR_OP_DESCRIPTIONS = {
    "TASK_DELAY": "ISR 中禁止",
    "SEM_TAKE": "须用 TakeFromISR",
    "SEM_GIVE": "须用 GiveFromISR",
    "QUEUE_SEND": "须用 SendFromISR",
    "QUEUE_RECV": "ISR 中禁止阻塞接收",
    "TASK_NOTIFY_GIVE": "须用 NotifyFromISR",
    "MUTEX_LOCK": "ISR 中禁止",
    "HEAP_ALLOC": "ISR 中禁止",
    "PRINTF": "ISR 中可能阻塞",
    "PARSE": "ISR 中禁止（malloc）",
}

_seen_apis: set[str] = set()
BLOCKING_PATTERNS: list[tuple[re.Pattern[str], str]] = []
for _op, _desc in _ISR_OP_DESCRIPTIONS.items():
    for _api in _lookup.get_apis(_op):
        if _api not in _seen_apis:
            _seen_apis.add(_api)
            BLOCKING_PATTERNS.append(
                (re.compile(r"\b%s\s*\(" % re.escape(_api)), f"{_api} — {_desc}")
            )
# 常量匹配
BLOCKING_PATTERNS.append(
    (_lookup.build_constant_regex("TIMEOUT_FOREVER"), "portMAX_DELAY — ISR 中禁止无限等待")
)

PORT_YIELD_PATTERN = _lookup.build_regex("IRQ_YIELD")


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


def check_file(path: Path) -> list[dict]:
    result = read_file(path)
    if result is None:
        return []
    lines, text = result
    issues: list[dict] = []

    i = 0
    while i < len(lines):
        if is_isr_function_start(lines[i]):
            func_name, body_start, body_end = extract_function_body(lines, i)

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
                        issues.append(make_issue(
                            path, body_start + j + 1, "C5", "P0",
                            f"[{func_name}] {desc}: {bline.strip()[:80]}",
                        ))

            if has_fromisr_notify and not has_yield:
                issues.append(make_issue(
                    path, i + 1, "C5-w", "P2",
                    f"[{func_name}] 使用了 FromISR API 但未调用 portYIELD_FROM_ISR",
                ))
        i += 1

    return issues


if __name__ == "__main__":
    raise SystemExit(run_checker(check_file, "ISR 安全审查", ("C5",)))
