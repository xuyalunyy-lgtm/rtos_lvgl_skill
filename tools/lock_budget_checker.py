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
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from static_c_scan import collect_c_like_files, extract_functions, line_at, make_issue, nearby, strip_comments


LOCK_TAKE_RE = re.compile(
    r"\b(?:xSemaphoreTake|xSemaphoreTakeRecursive|rtos_lock_mutex|os_mutex_pend|pthread_mutex_lock)\s*\((?P<args>[^;]*?)\)\s*;",
    re.IGNORECASE | re.DOTALL,
)
LOCK_GIVE_RE = re.compile(r"\b(?:xSemaphoreGive|xSemaphoreGiveRecursive|rtos_unlock_mutex|os_mutex_post|pthread_mutex_unlock)\s*\(", re.IGNORECASE)
FOREVER_WAIT_RE = re.compile(r"\b(?:portMAX_DELAY|WAIT_FOREVER|RTOS_WAIT_FOREVER|OS_WAIT_FOREVER|BEKEN_WAIT_FOREVER)\b")
LOCK_BUDGET_HINT_RE = re.compile(r"(lock_budget|max_hold|hold_.*(?:us|ms)|bounded_lock|try_lock|pdMS_TO_TICKS\s*\()", re.IGNORECASE)
LOCK_ORDER_HINT_RE = re.compile(r"(lock_order|lock order|lock_rank|rank:|order:|L[0-9]\s*->)", re.IGNORECASE)
BLOCKING_WORK_RE = re.compile(
    r"\b(?:vTaskDelay|vTaskDelayUntil|mbedtls_ssl_(?:read|write|handshake)|recv|send|connect|select|poll|"
    r"cJSON_Parse|fopen|fread|fwrite|nvs_commit|flash_erase|flash_write|lv_timer_handler|codec_(?:open|create))\s*\(",
    re.IGNORECASE,
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


def check_function_lock_patterns(path: Path, raw_text: str, functions: list[dict[str, object]]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    for func in functions:
        name = str(func["name"])
        body = str(func["body"])
        line = int(func["line"])
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


def check_file(path: Path) -> list[dict[str, str]]:
    try:
        raw_text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    code = strip_comments(raw_text)
    functions = extract_functions(code)
    issues: list[dict[str, str]] = []
    issues.extend(check_forever_lock_wait(path, code, raw_text))
    issues.extend(check_function_lock_patterns(path, raw_text, functions))
    issues.extend(check_binary_semaphore_mutex(path, code))
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="C43 lock budget checker")
    parser.add_argument("files", nargs="*", help="C/C++ files to check")
    parser.add_argument("--dir", "-d", help="Directory to scan recursively")
    args = parser.parse_args()

    targets = collect_c_like_files(args.files, args.dir)
    if not targets:
        print("[lock_budget_checker] no files to check")
        return 0

    all_issues: list[dict[str, str]] = []
    for path in targets:
        all_issues.extend(check_file(path))

    if not all_issues:
        print(f"[lock_budget_checker] checked {len(targets)} files, no C43 warnings")
        return 0

    print(f"[lock_budget_checker] checked {len(targets)} files, found {len(all_issues)} C43 warnings:\n")
    for item in all_issues:
        print(f"  [{item['severity']}] {item['id']} - {item['file']} - {item['issue']}")
    print(f"\nSummary: {len(all_issues)} C43 lock budget warnings")
    return 1


if __name__ == "__main__":
    sys.exit(main())
