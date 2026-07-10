#!/usr/bin/env python3
"""
Queue payload ownership static review (Iron Rule #2).

Detects violations in xQueueSend call chains:
  - Passing cJSON* or fields containing cJSON* to a Queue
  - payload pointing to stack buffer (dangling after function return)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from checker_io import make_issue, read_file, run_checker
from sdk_lookup import SdkLookup

lookup = SdkLookup("esp32")

QUEUE_SEND = lookup.build_regex("QUEUE_SEND", "QUEUE_OVERWRITE")
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
    """Find function start upward from xQueueSend line, and rough function end downward."""
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
                    detail="xQueueSend call line contains cJSON — passing cJSON* to Queue is forbidden",
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
                        detail=f".payload/.data points to stack variable '{rhs}' — Presenter receives dangling pointer",
                        line_text=lines[assign_line - 1].strip()[:100],
                    )
                )
            if rhs in cjson_vars:
                result.violations.append(
                    Violation(
                        line_no=assign_line,
                        kind="cjson_payload",
                        detail=f"Field assigned with cJSON* '{rhs}' — cJSON must not enter Queue",
                        line_text=lines[assign_line - 1].strip()[:100],
                    )
                )

        # xQueueSend(q, &cjson_var, ...) — passing cJSON* directly when queue element is a pointer
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
                        detail=f"xQueueSend passes cJSON* '&{arg}'",
                        line_text=stripped[:100],
                    )
                )
            if arg in stack_vars:
                result.violations.append(
                    Violation(
                        line_no=idx + 1,
                        kind="stack_queue_element",
                        detail=f"xQueueSend passes stack buffer '&{arg}'",
                        line_text=stripped[:100],
                    )
                )
            if arg in ptr_from_stack:
                result.violations.append(
                    Violation(
                        line_no=idx + 1,
                        kind="stack_ptr_queue_element",
                        detail=f"xQueueSend passes pointer to stack '{ptr_from_stack[arg]}' as '&{arg}'",
                        line_text=stripped[:100],
                    )
                )

        # Parse result directly into Queue (common anti-pattern)
        if re.search(
            r"xQueue\w+.*\bcJSON_(?:Parse|Create)",
            region_text,
            re.DOTALL,
        ):
            result.violations.append(
                Violation(
                    line_no=idx + 1,
                    kind="parse_to_queue",
                    detail=f"cJSON_Parse/Create and xQueueSend in same scope — verify root pointer is not passed",
                    line_text=stripped[:100],
                )
            )

    # Deduplicate (same line + kind)
    seen: set[tuple[int, str]] = set()
    unique: list[Violation] = []
    for v in result.violations:
        key = (v.line_no, v.kind)
        if key not in seen:
            seen.add(key)
            unique.append(v)
    result.violations = unique
    return result


def check_file(path: Path) -> list[dict]:
    result = read_file(path)
    if result is None:
        return []
    _lines, text = result
    analysis = analyze(text, str(path))
    issues = []
    for v in analysis.violations:
        cid = {
            "cJSON_in_queue_send":   "C2.1",
            "stack_payload":         "C2.2",
            "cjson_payload":         "C2.3",
            "cjson_queue_element":   "C2.4",
            "stack_queue_element":   "C2.5",
            "stack_ptr_queue_element": "C2.6",
            "parse_to_queue":        "C2.7",
        }.get(v.kind, "C2.0")
        issues.append(make_issue(path, v.line_no, cid, "P0", f"[{v.kind}] {v.detail}"))
    return issues


if __name__ == "__main__":
    raise SystemExit(run_checker(check_file, "C2 Queue payload ownership review", ("C2",)))
