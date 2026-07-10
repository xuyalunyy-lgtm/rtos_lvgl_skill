#!/usr/bin/env python3
"""Validate checker registry metadata completeness.

Checks each registered checker for:
  - constraint IDs (domains)
  - error_prefix
  - fixture coverage (at least one good/bad pair in SELF_TEST_CASES)

Exit 0 always. Missing fixture coverage is reported as warning-only metadata debt.
"""
from __future__ import annotations

import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent.parent / "tools"
sys.path.insert(0, str(TOOLS_DIR))

from checker_registry import ALL_CHECKERS, SELF_TEST_CASES, CheckerSpec


def main() -> int:
    # Build fixture map: script -> [case labels]
    fixture_map: dict[str, list[str]] = {}
    for case in SELF_TEST_CASES:
        fixture_map.setdefault(case.script, []).append(case.label)

    missing_domains = []
    missing_prefix = []
    missing_fixture = []
    overlap_warnings = []

    for spec in ALL_CHECKERS:
        if not spec.domains:
            missing_domains.append(spec.name)
        if not spec.error_prefix:
            missing_prefix.append(spec.name)
        if spec.script not in fixture_map:
            missing_fixture.append(spec.name)

        # Check overlap consistency: if A overlaps B, B should overlap A
        for other_name in spec.overlaps:
            other = next((c for c in ALL_CHECKERS if c.name == other_name), None)
            if other and spec.name not in other.overlaps:
                overlap_warnings.append(
                    f"{spec.name} -> {other_name} but {other_name} does not declare overlap back"
                )

    issues = 0

    if missing_domains:
        print(f"[WARN] checkers without constraint IDs: {', '.join(missing_domains)}")
        issues += len(missing_domains)

    if missing_prefix:
        print(f"[WARN] checkers without error_prefix: {', '.join(missing_prefix)}")
        issues += len(missing_prefix)

    if missing_fixture:
        print(f"[WARN] checkers without self-test fixture: {', '.join(missing_fixture)}")
        issues += len(missing_fixture)

    if overlap_warnings:
        for w in overlap_warnings:
            print(f"[WARN] overlap inconsistency: {w}")
        issues += len(overlap_warnings)

    if issues == 0:
        print("[OK] all checker metadata complete")
    else:
        print(f"\n[INFO] {issues} metadata gaps found (warnings, not blocking)")

    return 0  # Always pass; warnings only


if __name__ == "__main__":
    raise SystemExit(main())
