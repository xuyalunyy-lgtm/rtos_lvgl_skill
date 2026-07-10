#!/usr/bin/env python3
"""
C44 critical-section / IRQ-mask budget heuristic checker.

Checks:
  C44.1 critical sections and IRQ-masked regions should be short and budgeted
  C44.2 critical sections must not contain blocking or heavy work
  C44.3 every enter/disable path should restore IRQ/exit before return
  C44.4 busy loops are forbidden while interrupts are masked
  C44.5 ISR/callback/hot paths must not create long critical sections

Usage:
    python tools/critical_section_checker.py <file.c> [file2.c ...]
    python tools/critical_section_checker.py --dir src/
"""

from __future__ import annotations

import re
from pathlib import Path

from checker_io import make_issue, read_file, run_checker, strip_comments, extract_functions, line_at, nearby
from sdk_lookup import SdkLookup

# All-platform SDK lookup
_ALL_PLATFORMS = ["esp32", "stm32", "jl", "bk", "zephyr"]
_lookup = SdkLookup(_ALL_PLATFORMS)

ENTER_RE = _lookup.build_regex("CRITICAL_ENTER", "IRQ_DISABLE")
EXIT_RE = _lookup.build_regex("CRITICAL_EXIT", "IRQ_ENABLE")
HEAVY_RE = _lookup.build_combined_regex(
    "memcpy|memmove|memset|codec_open|codec_create",
    "TASK_DELAY", "QUEUE_SEND", "QUEUE_RECV", "SEM_TAKE", "SEM_GIVE",
    "TLS_READ", "TLS_WRITE", "TLS_HANDSHAKE", "SOCKET_RECV", "SOCKET_SEND",
    "SOCKET_CONNECT", "HEAP_ALLOC", "HEAP_FREE", "PRINTF", "LOG_WRITE",
    "PARSE", "NVS_COMMIT", "FLASH_WRITE", "FLASH_ERASE", "TIMER_HANDLER",
)
BUSY_LOOP_RE = re.compile(r"\b(?:while\s*\(|for\s*\()", re.IGNORECASE)
RETURN_RE = re.compile(r"\breturn\b")
CRITICAL_BUDGET_RE = re.compile(r"(critical_budget|irq_off_budget|max_irq_off|max_critical|bounded_critical|<=\s*\d+\s*(?:us|ms))", re.IGNORECASE)
HOT_FUNC_RE = re.compile(r"(IRQHandler|ISR|_isr|Callback|Cplt|Done|flush|frame|audio|video|render|encode|decode|capture)", re.IGNORECASE)


def count_code_lines(region: str) -> int:
    return sum(1 for line in region.splitlines() if line.strip())


def find_critical_regions(code: str) -> list[dict[str, object]]:
    regions: list[dict[str, object]] = []
    pos = 0
    while True:
        enter = ENTER_RE.search(code, pos)
        if not enter:
            break
        exit_match = EXIT_RE.search(code, enter.end())
        if not exit_match:
            regions.append({
                "start": enter.start(),
                "end": len(code),
                "body": code[enter.end():],
                "closed": False,
                "line": line_at(code, enter.start()),
            })
            pos = enter.end()
            continue
        regions.append({
            "start": enter.start(),
            "end": exit_match.end(),
            "body": code[enter.end():exit_match.start()],
            "closed": True,
            "line": line_at(code, enter.start()),
        })
        pos = exit_match.end()
    return regions


def function_for_pos(functions: list, code: str, pos: int):
    target_line = line_at(code, pos)
    selected = None
    for func in functions:
        if func.line <= target_line:
            selected = func
        else:
            break
    return selected


def check_regions(path: Path, code: str, raw_text: str, functions: list) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    for region in find_critical_regions(code):
        line = int(region["line"])
        body = str(region["body"])
        start = int(region["start"])
        func = function_for_pos(functions, code, start)
        func_name = func.name if func else "<global>"

        if not bool(region["closed"]):
            issues.append(make_issue(path, line, "C44.3", "P0", "critical section or IRQ-disable path has no matching exit/enable"))

        if RETURN_RE.search(body):
            issues.append(make_issue(path, line, "C44.3", "P0", "critical section contains return before restoring IRQ/exit"))

        if HEAVY_RE.search(body):
            issues.append(make_issue(path, line, "C44.2", "P0", "critical section contains blocking, allocation, logging, copy, IO, or heavy work"))

        if BUSY_LOOP_RE.search(body):
            issues.append(make_issue(path, line, "C44.4", "P1", "critical section contains a loop while interrupts may be masked"))

        if HOT_FUNC_RE.search(func_name):
            issues.append(make_issue(path, line, "C44.5", "P0", f"{func_name} enters a critical section on a hot path/callback"))

        if count_code_lines(body) > 6 and not CRITICAL_BUDGET_RE.search(nearby(raw_text, start, before=260, after=260)):
            issues.append(make_issue(path, line, "C44.1", "P1", "critical section is longer than a short register/state update and lacks irq_off budget evidence"))

    return issues


def check_file(path: Path) -> list[dict[str, str]]:
    result = read_file(path)
    if result is None:
        return []

    _lines, raw_text = result
    code = strip_comments(raw_text)
    functions = extract_functions(code)
    return check_regions(path, code, raw_text, functions)


if __name__ == "__main__":
    raise SystemExit(run_checker(check_file, "C44 critical-section budget checker", ("C44",)))
