#!/usr/bin/env python3
"""
Agent end-to-end evaluation — non-blocking, for manual/scheduled runs.

Validates that a real Agent (Codex/ChatGPT) correctly routes 10 frozen requests
by asserting: chosen workflow, whether it asked for clarification, and first
loaded files. Does NOT assert natural language output quality.

Usage:
    # Run with a real Agent and capture its decisions:
    python scripts/eval_agent_e2e.py --agent-output artifacts/agent_decisions.json

    # Generate the frozen request set for Agent input:
    python scripts/eval_agent_e2e.py --generate-input > artifacts/agent_input.json

    # Evaluate Agent decisions against expectations:
    python scripts/eval_agent_e2e.py --evaluate artifacts/agent_decisions.json

This script is NOT a CI gate. It runs on manual trigger or scheduled workflow.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── Frozen requests (shared with run_agent_e2e.py) ──

from e2e_fixtures import FROZEN_REQUESTS


def generate_input() -> dict:
    """Generate the input file for Agent evaluation."""
    return {
        "meta": {
            "description": "Frozen requests for Agent e2e routing evaluation",
            "total": len(FROZEN_REQUESTS),
            "instructions": (
                "For each request, the Agent should: "
                "1) Classify the request into a domain/workflow or ask for clarification. "
                "2) Load the appropriate workflow file and dependencies. "
                "3) Record the chosen workflow, whether clarification was asked, "
                "and the list of files loaded (in order)."
            ),
        },
        "requests": [
            {"id": r["id"], "request": r["request"]}
            for r in FROZEN_REQUESTS
        ],
    }


def evaluate_decisions(decisions: list[dict]) -> dict:
    """Evaluate Agent decisions against frozen expectations.

    Validates:
    - All expected IDs are present (no missing)
    - No duplicate IDs in decisions
    - No unknown IDs (not in expected set)
    - Each decision matches expected workflow/clarification/files
    """
    expectations = {r["id"]: r for r in FROZEN_REQUESTS}
    expected_ids = set(expectations.keys())
    results = []
    passed = 0
    failed = 0

    # Track seen IDs for duplicate detection
    seen_ids: dict[str, int] = {}

    for decision in decisions:
        did = decision.get("id") or decision.get("case_id")
        if not did:
            results.append({"id": "?", "passed": False, "failures": ["Missing id/case_id field"]})
            failed += 1
            continue

        # Duplicate check
        seen_ids[did] = seen_ids.get(did, 0) + 1
        if seen_ids[did] > 1:
            results.append({"id": did, "passed": False, "failures": [f"Duplicate ID (occurrence {seen_ids[did]})"]})
            failed += 1
            continue

        # Unknown ID check
        expect = expectations.get(did)
        if not expect:
            results.append({"id": did, "passed": False, "failures": [f"Unknown ID: {did}"]})
            failed += 1
            continue

        failures = []

        # Check clarification (support both key names)
        actual_clarified = decision.get("asked_clarification",
                             decision.get("clarification_required", False))
        if expect["expected_clarification"] and not actual_clarified:
            failures.append(f"Expected clarification but Agent chose workflow: {decision.get('workflow')}")
        if not expect["expected_clarification"] and actual_clarified:
            failures.append("Agent asked for clarification but should have routed")

        # Check workflow (only if not expecting clarification)
        if not expect["expected_clarification"] and not actual_clarified:
            actual_wf = decision.get("workflow")
            if actual_wf != expect["expected_workflow"]:
                failures.append(f"Workflow: expected {expect['expected_workflow']}, got {actual_wf}")

        # Check loaded files (only if not expecting clarification)
        if not expect["expected_clarification"] and not actual_clarified:
            loaded = decision.get("loaded_files", decision.get("initial_files", []))
            must_load = expect.get("must_load_prefix")
            if must_load and not any(must_load in f for f in loaded):
                failures.append(f"Must-load prefix not found: {must_load}")

            for forbidden in expect.get("must_not_load", []):
                if any(forbidden in f for f in loaded):
                    failures.append(f"Forbidden file loaded: {forbidden}")

        results.append({
            "id": did,
            "passed": len(failures) == 0,
            "failures": failures,
            "expected_workflow": expect["expected_workflow"],
            "actual_workflow": decision.get("workflow"),
            "expected_clarification": expect["expected_clarification"],
            "actual_clarification": actual_clarified,
        })

        if failures:
            failed += 1
        else:
            passed += 1

    # Missing ID check: expected IDs not seen in decisions
    actual_ids = set(seen_ids.keys())
    missing_ids = expected_ids - actual_ids
    for mid in sorted(missing_ids):
        results.append({"id": mid, "passed": False, "failures": [f"Missing: expected {mid} but not in decisions"]})
        failed += 1

    total = passed + failed
    return {
        "meta": {
            "expected_total": len(expected_ids),
            "actual_total": len(decisions),
            "total_evaluated": total,
            "passed": passed,
            "failed": failed,
            "missing_ids": sorted(missing_ids),
            "duplicate_ids": [did for did, count in seen_ids.items() if count > 1],
            "unknown_ids": sorted(actual_ids - expected_ids),
            "conformance": passed / total if total else 0,
        },
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Agent e2e routing evaluation (non-blocking)")
    parser.add_argument("--generate-input", action="store_true", help="Generate Agent input file")
    parser.add_argument("--evaluate", type=Path, help="Evaluate Agent decisions from JSON file")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    if args.generate_input:
        data = generate_input()
        if args.json:
            json.dump(data, sys.stdout, ensure_ascii=False, indent=2)
            print()
        else:
            print(f"Frozen requests: {len(data['requests'])}")
            for r in data["requests"]:
                print(f"  {r['id']}: {r['request'][:60]}...")
        return 0

    if args.evaluate:
        if not args.evaluate.is_file():
            print(f"File not found: {args.evaluate}", file=sys.stderr)
            return 1
        decisions = json.loads(args.evaluate.read_text(encoding="utf-8-sig"))
        if isinstance(decisions, dict) and "decisions" in decisions:
            decisions = decisions["decisions"]
        report = evaluate_decisions(decisions)

        if args.json:
            json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
            print()
        else:
            total = report['meta'].get('total_evaluated', report['meta'].get('total', '?'))
            print(f"Agent E2E Evaluation: {report['meta']['passed']}/{total} passed\n")
            for r in report["results"]:
                status = "PASS" if r["passed"] else "FAIL"
                print(f"  [{status}] {r['id']}", end="")
                if not r["passed"]:
                    print()
                    for f in r["failures"]:
                        print(f"         - {f}")
                else:
                    wf = r["actual_workflow"] or "clarification"
                    print(f"  {wf}")
        return 0 if report["meta"]["failed"] == 0 else 1

    # Default: show summary
    print(f"Agent E2E Evaluation — {len(FROZEN_REQUESTS)} frozen requests")
    print(f"\nUse --generate-input to create Agent input file")
    print(f"Use --evaluate <file> to evaluate Agent decisions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
