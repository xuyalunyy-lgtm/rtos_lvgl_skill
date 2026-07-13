#!/usr/bin/env python3
"""
Golden routing evaluation — validate classify_request + build_load_plan
against a fixture set of 24 natural language requests.

Usage:
    python scripts/eval_golden_routing.py
    python scripts/eval_golden_routing.py --json
    python scripts/eval_golden_routing.py --id review_01
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "golden_routing.json"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Import the router
sys.path.insert(0, str(ROOT / "tools"))
from context_router import build_load_plan, classify_request


def load_fixtures() -> list[dict]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def evaluate_fixture(fixture: dict) -> dict:
    """Evaluate a single golden request fixture.

    Returns a dict with: id, passed (bool), failures (list[str]), details (dict).
    """
    fid = fixture["id"]
    failures: list[str] = []
    details: dict = {}

    # Step 1: classify
    cls = classify_request(fixture["request"])
    details["classify"] = cls

    # Negative case: expect clarification
    if fixture.get("expected_clarification"):
        if cls.get("clarification_required"):
            return {"id": fid, "passed": True, "failures": [], "details": details}
        failures.append(
            f"Expected clarification but got workflow: {cls.get('workflow')} "
            f"({cls.get('routing_reason', '')})"
        )
        return {"id": fid, "passed": False, "failures": failures, "details": details}

    # Positive case: should not require clarification
    if cls.get("clarification_required"):
        failures.append(f"Unexpected clarification: {cls.get('clarification_reason')}")
        return {"id": fid, "passed": False, "failures": failures, "details": details}

    # Check domain
    if cls["domain"] != fixture["expected_domain"]:
        failures.append(
            f"Domain mismatch: expected {fixture['expected_domain']}, got {cls['domain']}"
        )

    # Check workflow
    if cls["workflow"] != fixture["expected_workflow"]:
        failures.append(
            f"Workflow mismatch: expected {fixture['expected_workflow']}, got {cls['workflow']}"
        )

    # Step 2: build load plan
    plan = build_load_plan(
        cls["workflow"],
        fixture["platform"],
        fixture["rtos"],
        budget=fixture.get("budget", "compact"),
    )
    details["load_plan"] = {
        "budget_mode": plan.get("budget_mode"),
        "estimated_tokens": plan.get("estimated_tokens"),
        "file_count": len(plan.get("required_files", [])),
    }

    if "error" in plan:
        failures.append(f"Load plan error: {plan['error']}")
        return {"id": fid, "passed": False, "failures": failures, "details": details}

    # Check must_include
    plan_paths = [f["path"] for f in plan.get("required_files", [])]
    for pattern in fixture.get("must_include", []):
        found = any(pattern in p for p in plan_paths)
        if not found:
            failures.append(f"Must-include not found: {pattern}")

    # Check must_exclude
    for pattern in fixture.get("must_exclude", []):
        found = any(pattern in p for p in plan_paths)
        if found:
            failures.append(f"Must-exclude leaked: {pattern}")

    # Check token budget
    max_tokens = fixture.get("max_tokens", 8000)
    est = plan.get("estimated_tokens", 0)
    if est > max_tokens:
        failures.append(f"Token budget exceeded: {est} > {max_tokens}")

    return {
        "id": fid,
        "passed": len(failures) == 0,
        "failures": failures,
        "details": details,
    }


def run_evaluation(filter_id: str | None = None) -> tuple[list[dict], int, int]:
    """Run the golden routing evaluation.

    Returns (results, passed_count, failed_count).
    """
    fixtures = load_fixtures()
    results: list[dict] = []
    passed = 0
    failed = 0

    for fixture in fixtures:
        if filter_id and fixture["id"] != filter_id:
            continue
        result = evaluate_fixture(fixture)
        results.append(result)
        if result["passed"]:
            passed += 1
        else:
            failed += 1

    return results, passed, failed


def main() -> int:
    parser = argparse.ArgumentParser(description="Golden routing evaluation")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--id", help="Run only this fixture ID")
    args = parser.parse_args()

    results, passed, failed = run_evaluation(args.id)

    if args.json:
        json.dump(
            {"passed": passed, "failed": failed, "total": len(results), "results": results},
            sys.stdout,
            ensure_ascii=False,
            indent=2,
        )
        print()
    else:
        for r in results:
            status = "PASS" if r["passed"] else "FAIL"
            print(f"  [{status}] {r['id']}", end="")
            if not r["passed"]:
                print()
                for f in r["failures"]:
                    print(f"         - {f}")
            else:
                cls = r["details"]["classify"]
                if cls.get("clarification_required"):
                    print(f"  clarification_required")
                else:
                    wf = cls.get("workflow", "?")
                    reason = cls.get("routing_reason", "")
                    print(f"  {wf} ({reason})")

        print(f"\nGolden routing: {passed}/{passed + failed} passed")
        if failed:
            print(f"  {failed} fixture(s) failed")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
