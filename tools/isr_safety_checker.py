#!/usr/bin/env python3
"""
ISR / HAL 回调阻塞 API 静态审查工具。

扫描 IRQHandler、HAL_*_Callback、FromISR 上下文中的阻塞 FreeRTOS 调用。
"""

from __future__ import annotations

import re
from pathlib import Path

from checker_io import make_issue, read_file, run_checker

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
