#!/usr/bin/env python3
"""
C36/C37 efficiency budget heuristic checker.

Checks:
  C36.2 large payload should use descriptor/index/handle instead of raw frame/buffer structs
  C36.3 copy-heavy paths should expose copy budget / copy count / owner-release hints
  C36.5 buffer pool full paths need drop/backpressure/retry counters
  C37.2 full queues must not wait forever
  C37.4 retry/reconnect loops must be bounded and backoff-aware

Usage:
    python tools/efficiency_budget_checker.py <file.c> [file2.c ...]
    python tools/efficiency_budget_checker.py --dir src/
"""

from __future__ import annotations

import re
from pathlib import Path

from checker_io import (
    extract_functions,
    line_at,
    make_issue,
    nearby,
    read_file,
    run_checker,
    strip_comments,
)

QUEUE_SEND_RE = re.compile(
    r"\bxQueue(?:Send|SendToBack|SendToFront|GenericSend)\s*\((?P<args>[^;]*?)\)\s*;",
    re.IGNORECASE | re.DOTALL,
)
QUEUE_WAIT_FOREVER_RE = re.compile(
    r"\bxQueue(?:Send|SendToBack|SendToFront|Receive|GenericSend)\s*\([^;]*(?:portMAX_DELAY|WAIT_FOREVER|RTOS_WAIT_FOREVER)",
    re.IGNORECASE | re.DOTALL,
)
QUEUE_CREATE_RE = re.compile(
    r"\bxQueueCreate\s*\([^,]+,\s*sizeof\s*\(\s*(?P<type>[^)]+)\s*\)",
    re.IGNORECASE,
)
MEMCPY_RE = re.compile(r"\bmemcpy\s*\(", re.IGNORECASE)
ALLOC_RE = re.compile(r"\b(?:malloc|calloc|pvPortMalloc|heap_caps_malloc|heap_caps_calloc)\s*\(", re.IGNORECASE)
FREE_RE = re.compile(r"\b(?:free|vPortFree|heap_caps_free)\s*\(", re.IGNORECASE)
RETRY_LOOP_RE = re.compile(r"\b(?:while\s*\(\s*(?:1|true)\s*\)|for\s*\(\s*;\s*;\s*\))", re.IGNORECASE)
RETRY_WORD_RE = re.compile(r"(retry|reconnect|resend|connect|handshake|send|recv)", re.IGNORECASE)
BACKOFF_HINT_RE = re.compile(r"(backoff|retry_max|max_retry|max_retries|retry_count|circuit|delay|timeout|deadline|sleep|vTaskDelay)", re.IGNORECASE)

PAYLOAD_WORD_RE = re.compile(r"(frame|buffer|buf|packet|payload|sample|pcm|image|jpeg|audio|video|event)", re.IGNORECASE)
HANDLE_WORD_RE = re.compile(r"(^|_|\b)(handle|descriptor|desc|index|idx|id|ptr|ref)($|_|\b)", re.IGNORECASE)
COPY_BUDGET_HINT_RE = re.compile(r"(copy_count|copy_budget|zero_copy|one_copy|owner|release|descriptor|handle|index|bounded)", re.IGNORECASE)
BACKPRESSURE_HINT_RE = re.compile(
    r"(drop|dropped|drop_oldest|drop_newest|coalesce|overwrite|backpressure|degrade|overflow|full_count|pool_full|retry)",
    re.IGNORECASE,
)
HOT_FUNC_RE = re.compile(r"(isr|callback|cplt|done|frame|process|render|encode|decode|capture|flush|loop|task)", re.IGNORECASE)


def queue_send_payload_arg(args: str) -> str:
    parts = [part.strip() for part in args.split(",")]
    if len(parts) < 2:
        return ""
    return parts[1]


def check_queue_payloads(path: Path, code: str, raw_text: str) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []

    for match in QUEUE_CREATE_RE.finditer(code):
        type_name = match.group("type").strip()
        if PAYLOAD_WORD_RE.search(type_name) and not HANDLE_WORD_RE.search(type_name):
            if not COPY_BUDGET_HINT_RE.search(nearby(raw_text, match.start())):
                issues.append(make_issue(
                    path,
                    line_at(code, match.start()),
                    "C36.2",
                    "P0",
                    f"Queue element uses sizeof({type_name}); prefer descriptor/index/handle or document copy budget",
                ))

    for match in QUEUE_SEND_RE.finditer(code):
        payload = queue_send_payload_arg(match.group("args"))
        if not payload:
            continue
        if PAYLOAD_WORD_RE.search(payload) and not HANDLE_WORD_RE.search(payload):
            if not COPY_BUDGET_HINT_RE.search(nearby(raw_text, match.start())):
                issues.append(make_issue(
                    path,
                    line_at(code, match.start()),
                    "C36.2",
                    "P0",
                    f"Queue sends raw payload '{payload}'; pass descriptor/index/handle or document bounded copy",
                ))
    return issues


def check_copy_budget(path: Path, code: str, raw_text: str, functions: list) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    for func in functions:
        name = func.name
        body = func.body
        if not MEMCPY_RE.search(body):
            continue
        if HOT_FUNC_RE.search(name) or PAYLOAD_WORD_RE.search(body):
            if not COPY_BUDGET_HINT_RE.search(body) and not COPY_BUDGET_HINT_RE.search(raw_text):
                issues.append(make_issue(
                    path,
                    func.line,
                    "C36.3",
                    "P1",
                    f"{name} contains memcpy on a likely data path without copy_count/owner/release evidence",
                ))

        if ALLOC_RE.search(body) and MEMCPY_RE.search(body):
            if not FREE_RE.search(body) or not BACKPRESSURE_HINT_RE.search(body):
                issues.append(make_issue(
                    path,
                    func.line,
                    "C36.5",
                    "P2",
                    f"{name} allocates and copies data without visible pool-full/backpressure/drop accounting",
                ))
    return issues


def check_backpressure(path: Path, code: str, raw_text: str, functions: list) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []

    for match in QUEUE_WAIT_FOREVER_RE.finditer(code):
        if not BACKPRESSURE_HINT_RE.search(nearby(raw_text, match.start())):
            issues.append(make_issue(
                path,
                line_at(code, match.start()),
                "C37.2",
                "P0",
                "Queue operation waits forever without nearby drop/coalesce/overwrite/backpressure evidence",
            ))

    for func in functions:
        name = func.name
        body = func.body
        if RETRY_LOOP_RE.search(body) and RETRY_WORD_RE.search(body):
            if not BACKOFF_HINT_RE.search(body):
                issues.append(make_issue(
                    path,
                    func.line,
                    "C37.4",
                    "P1",
                    f"{name} has an unbounded retry/reconnect loop without backoff/max retry/circuit breaker",
                ))
    return issues


def check_file(path: Path) -> list[dict[str, str]]:
    result = read_file(path)
    if result is None:
        return []

    _lines, raw_text = result
    code = strip_comments(raw_text)
    functions = extract_functions(code)
    issues: list[dict[str, str]] = []
    issues.extend(check_queue_payloads(path, code, raw_text))
    issues.extend(check_copy_budget(path, code, raw_text, functions))
    issues.extend(check_backpressure(path, code, raw_text, functions))
    return issues


if __name__ == "__main__":
    raise SystemExit(run_checker(check_file, "C36/C37 efficiency budget checker", ("C36", "C37"), {".c", ".cpp"}))
