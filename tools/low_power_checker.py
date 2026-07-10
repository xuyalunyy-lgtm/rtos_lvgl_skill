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

from checker_io import make_issue, read_file, run_checker
from sdk_lookup import SdkLookup

lookup = SdkLookup("esp32")

# Deep sleep entry APIs
DEEP_SLEEP_APIS = lookup.get_all_apis("DEEP_SLEEP", "LIGHT_SLEEP")

# State save indicators
STATE_SAVE_INDICATORS = lookup.get_all_apis("NVS_WRITE", "NVS_COMMIT", "FLASH_WRITE")

# Power down indicators — specific shutdown functions only
POWER_DOWN_INDICATORS = lookup.get_apis("PERIPHERAL_POWER_DOWN")


def check_state_save_before_sleep(path: Path, lines: list[str]) -> list[dict]:
    """C21.1 — Must have state save before deep_sleep"""
    issues = []

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("/*"):
            continue

        for api in DEEP_SLEEP_APIS:
            if api + "(" not in stripped and api + "()" not in stripped:
                continue

            # Check previous 20 lines for state save
            has_state_save = False
            for j in range(max(0, i - 20), i):
                prev_line = lines[j]
                if any(indicator in prev_line for indicator in STATE_SAVE_INDICATORS):
                    has_state_save = True
                    break

            if not has_state_save:
                issues.append(make_issue(
                    path, i, "C21.1", "P0",
                    f"No state save found before {api} (nvs_set_* / nvs_commit)",
                ))

    return issues


def check_power_down_before_sleep(path: Path, lines: list[str]) -> list[dict]:
    """C21.4 — Must power down peripherals before deep_sleep"""
    issues = []

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("/*"):
            continue

        for api in DEEP_SLEEP_APIS:
            if api + "(" not in stripped and api + "()" not in stripped:
                continue

            # Check previous 30 lines for power down
            has_power_down = False
            for j in range(max(0, i - 30), i):
                prev_line = lines[j]
                if any(indicator in prev_line for indicator in POWER_DOWN_INDICATORS):
                    has_power_down = True
                    break

            if not has_power_down:
                issues.append(make_issue(
                    path, i, "C21.4", "P1",
                    f"No peripheral power down found before {api} (LCD/Audio/WiFi)",
                ))

    return issues


def check_file(path: Path) -> list[dict]:
    result = read_file(path)
    if result is None:
        return []

    lines, _text = result
    issues = []
    issues.extend(check_state_save_before_sleep(path, lines))
    issues.extend(check_power_down_before_sleep(path, lines))
    return issues


if __name__ == "__main__":
    raise SystemExit(run_checker(check_file, "C21 Low Power Management Checker", ("C21",)))
