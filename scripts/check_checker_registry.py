#!/usr/bin/env python3
"""Validate checker registry metadata completeness.

Checks each registered checker for:
  - constraint IDs (domains)
  - error_prefix
  - fixture coverage (at least one good/bad pair in SELF_TEST_CASES)

Use --strict to turn missing metadata or fixture coverage into a failing gate.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent.parent / "tools"
sys.path.insert(0, str(TOOLS_DIR))

from checker_registry import ALL_CHECKERS, SELF_TEST_CASES, CheckerSpec


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate checker registry metadata completeness")
    parser.add_argument("--strict", action="store_true", help="fail when a metadata gap is found")
    parser.add_argument("--max-missing-fixtures", type=int, default=0,
                        help="maximum missing self-test fixtures in --strict mode (default: 0)")
    args = parser.parse_args()
    if args.max_missing_fixtures < 0:
        parser.error("--max-missing-fixtures must be non-negative")
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

    metadata_gaps = len(missing_domains) + len(missing_prefix) + len(overlap_warnings)
    fixture_gaps = len(missing_fixture)
    if args.strict and (metadata_gaps or fixture_gaps > args.max_missing_fixtures):
        print(
            "[FAIL] checker registry threshold exceeded: "
            f"metadata_gaps={metadata_gaps}, missing_fixtures={fixture_gaps} "
            f"(max {args.max_missing_fixtures})"
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
