#!/usr/bin/env python3
"""Look up rules, automatic checkers, examples, and RTOS/platform notes by ID."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from checker_registry import ALL_CHECKERS, SELF_TEST_CASES

ID_RE = re.compile(r"^C\d+(?:\.\d+)?$", re.IGNORECASE)
ROW_RE = re.compile(r"^\|\s*(C\d+(?:\.\d+)?)\s*\|(.+)\|$")

PLATFORM_NOTES = {
    "esp32": "FreeRTOS task priority: larger number is higher; ESP32 also has shared-instance dual-core scheduling.",
    "stm32": "FreeRTOS priority: larger number is higher; CMSIS osThreadNew stack is bytes while xTaskCreate stack is words.",
    "jl": "JL priority: larger number is higher; use thread_fork/os_task_create and task_info_table stack sizes are words.",
    "bk": "BK priority: larger number is higher; use rtos_create_thread and its stack_size is bytes.",
    "zephyr": "Zephyr priority: smaller number is higher; use k_thread_create/K_THREAD_DEFINE and stacks are bytes.",
    "freertos": "Generic FreeRTOS priority: larger number is higher; xTaskCreate stack depth is expressed in words.",
}


def configure_console_encoding() -> None:
    """Keep non-ASCII constraint descriptions readable in Windows consoles."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


def _rules(constraint_id: str) -> list[dict[str, str]]:
    prefix = constraint_id + "."
    rules: list[dict[str, str]] = []
    detail = ROOT / "references" / "constraint_detail.md"
    for line in detail.read_text(encoding="utf-8").splitlines():
        match = ROW_RE.match(line)
        if not match:
            continue
        rule_id = match.group(1)
        if rule_id != constraint_id and not rule_id.startswith(prefix):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) >= 6:
            rules.append({
                "id": cells[0], "rule": cells[1], "severity": cells[2],
                "validation": cells[3], "good": cells[4], "bad": cells[5],
            })
    return rules


def lookup(constraint_id: str, platform: str | None = None) -> dict[str, Any]:
    normalized = constraint_id.upper()
    rules = _rules(normalized)
    checkers = [
        {"name": spec.name, "script": spec.script, "domains": list(spec.domains), "suites": list(spec.suites)}
        for spec in ALL_CHECKERS
        if any(domain == normalized or domain.startswith(normalized + ".") for domain in spec.domains)
    ]
    scripts = {item["script"] for item in checkers}
    examples = [
        {"path": case.path, "expected_exit": case.expected, "label": case.label}
        for case in SELF_TEST_CASES if case.script in scripts
    ]
    notes = ({platform: PLATFORM_NOTES[platform]} if platform else PLATFORM_NOTES)
    return {
        "constraint": normalized, "rules": rules, "checkers": checkers,
        "examples": examples, "platform_differences": notes,
    }


def print_text(result: dict[str, Any]) -> None:
    print(f"{result['constraint']} — {len(result['rules'])} rule(s)")
    for rule in result["rules"]:
        print(f"- {rule['id']} [{rule['severity']}] {rule['rule']}")
        print(f"  validation: {rule['validation']}")
    print("Checkers:")
    for checker in result["checkers"] or [{"name": "manual", "script": "—", "domains": []}]:
        print(f"- {checker['name']}: {checker['script']}")
    if result["examples"]:
        print("Examples:")
        for example in result["examples"]:
            print(f"- {example['path']} (exit {example['expected_exit']}: {example['label']})")
    print("Platform differences:")
    for name, note in result["platform_differences"].items():
        print(f"- {name}: {note}")


def main() -> int:
    configure_console_encoding()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("constraint", help="Constraint family or rule ID, e.g. C15 or C15.2")
    parser.add_argument("--platform", choices=sorted(PLATFORM_NOTES))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    constraint_id = args.constraint.upper()
    if not ID_RE.fullmatch(constraint_id):
        parser.error("constraint must look like C15 or C15.2")
    result = lookup(constraint_id, args.platform)
    if not result["rules"] and not result["checkers"]:
        print(f"Unknown constraint: {constraint_id}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_text(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
