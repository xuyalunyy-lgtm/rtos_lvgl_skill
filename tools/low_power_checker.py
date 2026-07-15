#!/usr/bin/env python3
"""
C21 Low power management heuristic checker.

Checks:
  C21.1 — Must save state to NVS/Flash before deep sleep
  C21.4 — Must power down peripherals before deep sleep

Usage:
    python tools/low_power_checker.py <file.c> [file2.c ...]
    python tools/low_power_checker.py --dir src/
"""

from __future__ import annotations

from pathlib import Path

from checker_io import extract_functions, make_issue, read_file, run_checker, strip_comments
from sdk_lookup import SdkLookup

lookup = SdkLookup("esp32")

# Deep sleep entry APIs
DEEP_SLEEP_APIS = lookup.get_all_apis("DEEP_SLEEP", "LIGHT_SLEEP")

# State save indicators
STATE_SAVE_INDICATORS = lookup.get_all_apis("NVS_WRITE", "NVS_COMMIT", "FLASH_WRITE")

# Power down indicators — specific shutdown functions only
POWER_DOWN_INDICATORS = lookup.get_apis("PERIPHERAL_POWER_DOWN")


def check_state_save_before_sleep(path: Path, code: str) -> list[dict]:
    """C21.1 — Must have state save before deep_sleep"""
    issues = []

    for func in extract_functions(code):
        for api in DEEP_SLEEP_APIS:
            match = func.body.find(api + "(")
            if match < 0:
                continue
            # A shared shutdown helper can establish state well before sleep;
            # search the complete function rather than an arbitrary line window.
            if not any(indicator in func.body for indicator in STATE_SAVE_INDICATORS):
                issues.append(make_issue(
                    path, func.line + func.body[:match].count("\n"), "C21.1", "P0",
                    f"No state save found before {api} (nvs_set_* / nvs_commit)",
                ))

    return issues


def check_power_down_before_sleep(path: Path, code: str) -> list[dict]:
    """C21.4 — Must power down peripherals before deep_sleep"""
    issues = []

    for func in extract_functions(code):
        for api in DEEP_SLEEP_APIS:
            match = func.body.find(api + "(")
            if match < 0:
                continue
            if not any(indicator in func.body for indicator in POWER_DOWN_INDICATORS):
                issues.append(make_issue(
                    path, func.line + func.body[:match].count("\n"), "C21.4", "P1",
                    f"No peripheral power down found before {api} (LCD/Audio/WiFi)",
                ))

    return issues


def check_file(path: Path) -> list[dict]:
    result = read_file(path)
    if result is None:
        return []

    _lines, raw_text = result
    code = strip_comments(raw_text)
    issues = []
    issues.extend(check_state_save_before_sleep(path, code))
    issues.extend(check_power_down_before_sleep(path, code))
    return issues


if __name__ == "__main__":
    raise SystemExit(run_checker(check_file, "C21 Low Power Management Checker", ("C21",)))
