#!/usr/bin/env python3
"""
C43 lock budget and priority-inversion heuristic checker.

Checks:
  C43.1 mutex waits should be bounded and have a lock budget
  C43.2 locks must not be held across blocking IO, TLS, flash, JSON, or delay
  C43.3 binary semaphores should not protect shared resources as mutexes
  C43.4 nested locks need an explicit lock order/rank note
  C43.5 ISR/callback/hot paths must not take mutexes

Usage:
    python tools/lock_budget_checker.py <file.c> [file2.c ...]
    python tools/lock_budget_checker.py --dir src/
    python tools/lock_budget_checker.py --json <file.c>
"""

from __future__ import annotations

import re
from pathlib import Path

from checker_io import extract_functions, line_at, make_issue, nearby, read_file, run_checker, strip_comments
from sdk_lookup import SdkLookup

# 全平台 SDK 查询
_ALL_PLATFORMS = ["esp32", "stm32", "jl", "bk", "zephyr"]
_lookup = SdkLookup(_ALL_PLATFORMS)

# 构建锁获取正则（保留 args 捕获组用于 forever 检测）
_lock_take_apis = _lookup.get_all_apis("SEM_TAKE", "MUTEX_LOCK")
LOCK_TAKE_RE = re.compile(
    r"\b(?:%s)\s*\((?P<args>[^;]*?)\)\s*;" % "|".join(re.escape(a) for a in _lock_take_apis),
    re.IGNORECASE | re.DOTALL,
)
LOCK_GIVE_RE = _lookup.build_regex("SEM_GIVE", "MUTEX_UNLOCK")
_lock_give_apis = _lookup.get_all_apis("SEM_GIVE", "MUTEX_UNLOCK")
LOCK_GIVE_CALL_RE = re.compile(
    r"\b(?:%s)\s*\((?P<args>[^;]*?)\)\s*;" % "|".join(re.escape(a) for a in _lock_give_apis),
    re.IGNORECASE | re.DOTALL,
)
FOREVER_WAIT_RE = _lookup.build_constant_regex("TIMEOUT_FOREVER")
LOCK_BUDGET_HINT_RE = re.compile(r"(lock_budget|max_hold|hold_.*(?:us|ms)|bounded_lock|try_lock|pdMS_TO_TICKS\s*\()", re.IGNORECASE)
LOCK_ORDER_HINT_RE = re.compile(r"(lock_order|lock order|lock_rank|rank:|order:|L[0-9]\s*->)", re.IGNORECASE)
BLOCKING_WORK_RE = _lookup.build_combined_regex(
    "mbedtls_ssl_read|mbedtls_ssl_write|mbedtls_ssl_handshake|fopen|fread|fwrite|codec_open|codec_create",
    "TASK_DELAY", "TLS_READ", "TLS_WRITE", "TLS_HANDSHAKE", "SOCKET_RECV", "SOCKET_SEND",
    "SOCKET_CONNECT", "PARSE", "NVS_COMMIT", "FLASH_WRITE", "FLASH_ERASE", "TIMER_HANDLER",
)
HOT_FUNC_RE = re.compile(r"(IRQHandler|ISR|_isr|Callback|Cplt|Done|flush|frame|audio|video|render|encode|decode|capture)", re.IGNORECASE)
BINARY_SEM_CREATE_RE = re.compile(
    r"(?P<name>[A-Za-z_]\w*(?:mutex|lock|guard|shared|state|resource)[A-Za-z_0-9]*)\s*=\s*xSemaphoreCreateBinary\s*\(",
    re.IGNORECASE,
)


def issue(path: Path, line: int, cid: str, severity: str, msg: str) -> dict[str, str]:
    return make_issue(path, line, cid, severity, msg)


def check_forever_lock_wait(path: Path, code: str, raw_text: str) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    for match in LOCK_TAKE_RE.finditer(code):
        args = match.group("args")
        if FOREVER_WAIT_RE.search(args) and not LOCK_BUDGET_HINT_RE.search(nearby(raw_text, match.start())):
            issues.append(issue(
                path,
                line_at(code, match.start()),
                "C43.1",
                "P0",
                "mutex wait uses forever timeout without nearby lock budget or bounded exception",
            ))
    return issues


def check_function_lock_patterns(path: Path, raw_text: str, functions: list) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    for func in functions:
        name = func.name
        body = func.body
        line = func.line
        lock_takes = list(LOCK_TAKE_RE.finditer(body))
        if not lock_takes:
            continue

        if HOT_FUNC_RE.search(name):
            issues.append(issue(path, line, "C43.5", "P0", f"{name} is a hot path/callback and takes a mutex"))

        first_take = lock_takes[0]
        first_give = LOCK_GIVE_RE.search(body, first_take.end())
        locked_region = body[first_take.end():first_give.start()] if first_give else body[first_take.end():]
        if BLOCKING_WORK_RE.search(locked_region):
            issues.append(issue(path, line, "C43.2", "P0", f"{name} holds a mutex across blocking or heavy work"))

        if len(lock_takes) >= 2:
            raw_window = raw_text[max(0, raw_text.find(name) - 300):raw_text.find(name) + 800]
            if not LOCK_ORDER_HINT_RE.search(body) and not LOCK_ORDER_HINT_RE.search(raw_window):
                issues.append(issue(path, line, "C43.4", "P1", f"{name} takes multiple locks without explicit lock_order/rank evidence"))

    return issues


def check_binary_semaphore_mutex(path: Path, code: str) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    for match in BINARY_SEM_CREATE_RE.finditer(code):
        issues.append(issue(
            path,
            line_at(code, match.start()),
            "C43.3",
            "P1",
            f"{match.group('name')} uses xSemaphoreCreateBinary for lock-like ownership; use a mutex with priority inheritance",
        ))
    return issues


def _lock_name(args: str) -> str | None:
    """Extract a stable lock-handle token from a take/give first argument."""
    first = args.split(",", 1)[0]
    first = re.sub(r"\([^)]*\)", "", first).replace("&", " ")
    match = re.search(r"[A-Za-z_]\w*(?:\s*->\s*[A-Za-z_]\w*)?", first)
    return re.sub(r"\s+", "", match.group(0)) if match else None


def _lock_edges(path: Path, code: str) -> list[tuple[str, str, int, str]]:
    """Return nested lock-order edges seen in every function of one file."""
    edges: list[tuple[str, str, int, str]] = []
    for func in extract_functions(code):
        events: list[tuple[int, str, str]] = []
        for match in LOCK_TAKE_RE.finditer(func.body):
            name = _lock_name(match.group("args"))
            if name:
                events.append((match.start(), "take", name))
        for match in LOCK_GIVE_CALL_RE.finditer(func.body):
            name = _lock_name(match.group("args"))
            if name:
                events.append((match.start(), "give", name))
        held: list[str] = []
        for offset, event, name in sorted(events):
            if event == "take":
                line = func.line + func.body[:offset].count("\n")
                for outer in held:
                    if outer != name:
                        edges.append((outer, name, line, func.name))
                held.append(name)
            elif name in held:
                held.pop(len(held) - 1 - held[::-1].index(name))
    return edges


def _find_lock_cycles(graph: dict[str, set[str]]) -> list[list[str]]:
    cycles: list[list[str]] = []
    seen: set[tuple[str, ...]] = set()

    def visit(node: str, stack: list[str], active: set[str]) -> None:
        for nxt in graph.get(node, set()):
            if nxt in active:
                cycle = stack[stack.index(nxt):] + [nxt]
                core = cycle[:-1]
                canonical = min(tuple(core[index:] + core[:index]) for index in range(len(core)))
                if canonical not in seen:
                    seen.add(canonical)
                    cycles.append(list(canonical) + [canonical[0]])
            elif nxt not in stack:
                visit(nxt, stack + [nxt], active | {nxt})

    for start in sorted(graph):
        visit(start, [start], {start})
    return cycles


def check_cross_file_lock_order(paths: list[Path]) -> list[dict[str, str]]:
    """C43.6 — detect a lock-order cycle built from all reviewed files."""
    graph: dict[str, set[str]] = {}
    evidence: dict[tuple[str, str], tuple[Path, int, str]] = {}
    all_issues: list[dict[str, str]] = []
    for path in paths:
        result = read_file(path)
        if result is None:
            continue
        _lines, raw_text = result
        code = strip_comments(raw_text)
        all_issues.extend(check_forever_lock_wait(path, code, raw_text))
        all_issues.extend(check_function_lock_patterns(path, raw_text, extract_functions(code)))
        all_issues.extend(check_binary_semaphore_mutex(path, code))
        for outer, inner, line, func in _lock_edges(path, code):
            graph.setdefault(outer, set()).add(inner)
            evidence.setdefault((outer, inner), (path, line, func))

    for cycle in _find_lock_cycles(graph):
        outer, inner = cycle[0], cycle[1]
        path, line, func = evidence[(outer, inner)]
        all_issues.append(issue(
            path, line, "C43.6", "P0",
            f"cross-file lock-order cycle: {' -> '.join(cycle)} (edge observed in {func}())",
        ))
    return all_issues


def check_file(path: Path) -> list[dict[str, str]]:
    result = read_file(path)
    if result is None:
        return []

    _lines, raw_text = result
    code = strip_comments(raw_text)
    functions = extract_functions(code)
    issues: list[dict[str, str]] = []
    issues.extend(check_forever_lock_wait(path, code, raw_text))
    issues.extend(check_function_lock_patterns(path, raw_text, functions))
    issues.extend(check_binary_semaphore_mutex(path, code))
    return issues


if __name__ == "__main__":
    raise SystemExit(run_checker(
        check_file, "C43 lock budget checker", ("C43",),
        check_paths_fn=check_cross_file_lock_order,
    ))
