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

import argparse
import re
import sys
from pathlib import Path


COMMENT_RE = re.compile(r"//.*?$|/\*.*?\*/", re.MULTILINE | re.DOTALL)
FUNC_DEF_RE = re.compile(
    r"(?:^|[\n;])\s*"
    r"(?:static\s+)?(?:inline\s+)?"
    r"(?:[A-Za-z_][\w\s\*]*\s+)+"
    r"(?P<name>[A-Za-z_]\w*)\s*\([^;{}]*\)\s*\{",
    re.MULTILINE,
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


def strip_comments(text: str) -> str:
    return COMMENT_RE.sub(lambda m: "\n" * m.group(0).count("\n"), text)


def line_at(text: str, pos: int) -> int:
    return text[:pos].count("\n") + 1


def find_matching_brace(text: str, open_pos: int) -> int:
    depth = 0
    for i in range(open_pos, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return i
    return -1


def extract_functions(code: str) -> list[dict[str, object]]:
    functions: list[dict[str, object]] = []
    for match in FUNC_DEF_RE.finditer(code):
        name = match.group("name")
        if name in {"if", "for", "while", "switch", "return", "sizeof"}:
            continue
        open_pos = code.find("{", match.end() - 1)
        close_pos = find_matching_brace(code, open_pos)
        if open_pos < 0 or close_pos < 0:
            continue
        functions.append({
            "name": name,
            "body": code[open_pos + 1:close_pos],
            "line": line_at(code, match.start("name")),
        })
    return functions


def issue(path: Path, line: int, cid: str, severity: str, msg: str) -> dict[str, str]:
    return {"id": cid, "severity": severity, "file": f"{path}:{line}", "issue": msg}


def nearby(text: str, pos: int, before: int = 240, after: int = 160) -> str:
    return text[max(0, pos - before):min(len(text), pos + after)]


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
                issues.append(issue(
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
                issues.append(issue(
                    path,
                    line_at(code, match.start()),
                    "C36.2",
                    "P0",
                    f"Queue sends raw payload '{payload}'; pass descriptor/index/handle or document bounded copy",
                ))
    return issues


def check_copy_budget(path: Path, code: str, raw_text: str, functions: list[dict[str, object]]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    for func in functions:
        name = str(func["name"])
        body = str(func["body"])
        if not MEMCPY_RE.search(body):
            continue
        if HOT_FUNC_RE.search(name) or PAYLOAD_WORD_RE.search(body):
            if not COPY_BUDGET_HINT_RE.search(body) and not COPY_BUDGET_HINT_RE.search(raw_text):
                issues.append(issue(
                    path,
                    int(func["line"]),
                    "C36.3",
                    "P1",
                    f"{name} contains memcpy on a likely data path without copy_count/owner/release evidence",
                ))

        if ALLOC_RE.search(body) and MEMCPY_RE.search(body):
            if not FREE_RE.search(body) or not BACKPRESSURE_HINT_RE.search(body):
                issues.append(issue(
                    path,
                    int(func["line"]),
                    "C36.5",
                    "P2",
                    f"{name} allocates and copies data without visible pool-full/backpressure/drop accounting",
                ))
    return issues


def check_backpressure(path: Path, code: str, raw_text: str, functions: list[dict[str, object]]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []

    for match in QUEUE_WAIT_FOREVER_RE.finditer(code):
        if not BACKPRESSURE_HINT_RE.search(nearby(raw_text, match.start())):
            issues.append(issue(
                path,
                line_at(code, match.start()),
                "C37.2",
                "P0",
                "Queue operation waits forever without nearby drop/coalesce/overwrite/backpressure evidence",
            ))

    for func in functions:
        name = str(func["name"])
        body = str(func["body"])
        if RETRY_LOOP_RE.search(body) and RETRY_WORD_RE.search(body):
            if not BACKOFF_HINT_RE.search(body):
                issues.append(issue(
                    path,
                    int(func["line"]),
                    "C37.4",
                    "P1",
                    f"{name} has an unbounded retry/reconnect loop without backoff/max retry/circuit breaker",
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
    issues.extend(check_queue_payloads(path, code, raw_text))
    issues.extend(check_copy_budget(path, code, raw_text, functions))
    issues.extend(check_backpressure(path, code, raw_text, functions))
    return issues


def collect_targets(files: list[str], dir_path: str | None) -> list[Path]:
    targets: list[Path] = []
    for item in files:
        path = Path(item)
        if path.is_file():
            targets.append(path)
        elif path.is_dir():
            targets.extend(sorted(path.rglob("*.c")))
            targets.extend(sorted(path.rglob("*.cpp")))
    if dir_path:
        root = Path(dir_path)
        if root.is_dir():
            targets.extend(sorted(root.rglob("*.c")))
            targets.extend(sorted(root.rglob("*.cpp")))

    seen: set[Path] = set()
    unique: list[Path] = []
    for target in targets:
        resolved = target.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(resolved)
    return unique


def main() -> int:
    parser = argparse.ArgumentParser(description="C36/C37 efficiency budget checker")
    parser.add_argument("files", nargs="*", help="C/C++ files to check")
    parser.add_argument("--dir", "-d", help="Directory to scan recursively")
    args = parser.parse_args()

    targets = collect_targets(args.files, args.dir)
    if not targets:
        print("[efficiency_budget_checker] no files to check")
        return 0

    all_issues: list[dict[str, str]] = []
    for path in targets:
        all_issues.extend(check_file(path))

    if not all_issues:
        print(f"[efficiency_budget_checker] checked {len(targets)} files, no C36/C37 warnings")
        return 0

    print(f"[efficiency_budget_checker] checked {len(targets)} files, found {len(all_issues)} C36/C37 warnings:\n")
    for item in all_issues:
        print(f"  [{item['severity']}] {item['id']} - {item['file']} - {item['issue']}")
    print(f"\nSummary: {len(all_issues)} C36/C37 efficiency budget warnings")
    return 1


if __name__ == "__main__":
    sys.exit(main())
