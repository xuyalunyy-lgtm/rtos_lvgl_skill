#!/usr/bin/env python3
"""
Routing holdout evaluation — blind test set for release validation.

Reads holdout samples from ROUTING_HOLDOUT_JSON environment variable (or file),
classifies each request, and validates against pass criteria. Does NOT echo
original requests in output to preserve blindness.

Usage:
    # From environment variable (CI):
    ROUTING_HOLDOUT_JSON='{"meta":...,"samples":[...]}' python scripts/eval_routing_holdout.py

    # From file:
    python scripts/eval_routing_holdout.py --file holdout.json

    # Output JSON:
    python scripts/eval_routing_holdout.py --json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(ROOT / "tools"))


def load_holdout(file_path: Path | None = None) -> dict:
    """Load holdout data from file or environment variable."""
    if file_path:
        return json.loads(file_path.read_text(encoding="utf-8-sig"))

    raw = os.environ.get("ROUTING_HOLDOUT_JSON", "")
    if not raw:
        print("ERROR: ROUTING_HOLDOUT_JSON not set and no --file provided", file=sys.stderr)
        sys.exit(1)
    return json.loads(raw)


def validate_holdout_schema(holdout: dict) -> list[str]:
    """Validate holdout data structure. Returns list of errors (empty = valid)."""
    errors = []

    meta = holdout.get("meta", {})
    samples = holdout.get("samples", [])

    if not isinstance(meta, dict):
        errors.append("meta must be an object")
    if not isinstance(samples, list):
        errors.append("samples must be an array")
        return errors

    if len(samples) != 36:
        errors.append(f"Expected 36 samples, got {len(samples)}")

    # Check each sample has required fields
    for i, s in enumerate(samples):
        sid = s.get("id", f"sample_{i}")
        if "request" not in s:
            errors.append(f"{sid}: missing 'request'")
        has_wf = "expected_workflow" in s
        has_clar = "expected_clarification" in s
        if not has_wf and not has_clar:
            errors.append(f"{sid}: must have expected_workflow or expected_clarification")
        if has_wf and has_clar:
            errors.append(f"{sid}: must not have both expected_workflow and expected_clarification")

    # Check distribution
    from collections import Counter
    wf_counts = Counter()
    clar_count = 0
    for s in samples:
        if s.get("expected_clarification"):
            clar_count += 1
        elif s.get("expected_workflow"):
            wf_counts[s["expected_workflow"]] += 1

    for wf in ["code_review", "memory_analysis", "project_review", "hw_sw_debug",
                "crash_debug", "lvgl_page", "app_manifest", "new_module",
                "bring_up", "sdk_trim"]:
        if wf_counts.get(wf, 0) < 3:
            errors.append(f"Workflow '{wf}' has {wf_counts.get(wf, 0)} samples, expected >= 3")
    if clar_count < 6:
        errors.append(f"Clarification has {clar_count} samples, expected >= 6")

    # Check language distribution
    lang_counts = Counter(s.get("language", "unknown") for s in samples)
    if lang_counts.get("zh", 0) < 16:
        errors.append(f"Chinese samples: {lang_counts.get('zh', 0)}, expected >= 16")
    if lang_counts.get("en", 0) < 16:
        errors.append(f"English samples: {lang_counts.get('en', 0)}, expected >= 16")

    return errors


def evaluate_holdout(holdout: dict) -> dict:
    """Evaluate holdout samples. Does NOT echo original requests."""
    from context_router import classify_request, build_load_plan

    meta = holdout.get("meta", {})
    samples = holdout.get("samples", [])
    pass_criteria = meta.get("pass_criteria", {
        "min_overall_conformance": 0.95,
        "max_false_auto_routes": 0,
        "max_false_clarifications": 2,
    })

    results = []
    for sample in samples:
        sid = sample["id"]
        result = classify_request(sample["request"])

        expected_wf = sample.get("expected_workflow")
        expect_clar = sample.get("expected_clarification", False)
        is_clar = result.get("clarification_required", False)
        actual_wf = result.get("workflow") if not is_clar else None

        if expect_clar:
            correct = is_clar
            outcome = "correct_clarification" if correct else "missed_clarification"
        elif is_clar:
            correct = False
            outcome = "false_clarification"
        else:
            correct = actual_wf == expected_wf
            outcome = "correct_route" if correct else "wrong_route"

        # Build load plan using sample's platform/rtos
        plan_valid = True
        plan_error = None
        if not is_clar and not expect_clar and actual_wf:
            platform = sample.get("platform", "esp32")
            rtos = sample.get("rtos", "freertos")
            plan = build_load_plan(actual_wf, platform, rtos, budget="compact")
            if "error" in plan:
                plan_valid = False
                plan_error = plan["error"]
                correct = False
                outcome = "plan_error"

        entry = {
            "id": sid,
            "expected_workflow": expected_wf,
            "expected_clarification": expect_clar,
            "actual_workflow": actual_wf,
            "actual_clarification": is_clar,
            "outcome": outcome,
            "correct": correct,
            "plan_valid": plan_valid,
            # Do NOT include sample["request"] in output
        }
        if plan_error:
            entry["plan_error"] = plan_error
        results.append(entry)

    # Compute stats
    total = len(results)
    correct_count = sum(1 for r in results if r["correct"])
    positive = [r for r in results if not r["expected_clarification"]]
    false_routes = sum(1 for r in positive if not r["correct"] and not r["actual_clarification"])
    false_clarifs = sum(1 for r in positive if r["actual_clarification"])

    overall_conformance = correct_count / total if total else 0

    # Check pass criteria
    passed = (
        overall_conformance >= pass_criteria.get("min_overall_conformance", 0.95)
        and false_routes <= pass_criteria.get("max_false_auto_routes", 0)
        and false_clarifs <= pass_criteria.get("max_false_clarifications", 2)
    )

    return {
        "meta": {
            "total": total,
            "correct": correct_count,
            "overall_conformance": overall_conformance,
            "false_auto_routes": false_routes,
            "false_clarifications": false_clarifs,
            "pass_criteria": pass_criteria,
            "passed": passed,
        },
        "results": results,
        "failures": [r for r in results if not r["correct"]],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Routing holdout evaluation (blind test)")
    parser.add_argument("--file", type=Path, help="Holdout JSON file")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    holdout = load_holdout(args.file)

    # Validate schema before evaluation
    schema_errors = validate_holdout_schema(holdout)
    if schema_errors:
        if args.json:
            json.dump({"schema_errors": schema_errors, "passed": False}, sys.stdout, ensure_ascii=False, indent=2)
            print()
        else:
            print(f"Holdout schema validation FAILED ({len(schema_errors)} errors):", file=sys.stderr)
            for err in schema_errors:
                print(f"  - {err}", file=sys.stderr)
        return 1

    report = evaluate_holdout(holdout)

    if args.json:
        json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
        print()
    else:
        m = report["meta"]
        print(f"Holdout Evaluation: {m['correct']}/{m['total']} ({m['overall_conformance']:.1%})")
        print(f"  False auto-routes: {m['false_auto_routes']}")
        print(f"  False clarifications: {m['false_clarifications']}")
        print(f"  Pass criteria: {m['pass_criteria']}")
        print(f"  Result: {'PASS' if m['passed'] else 'FAIL'}")

        if report["failures"]:
            print(f"\nFailures ({len(report['failures'])}):")
            for f in report["failures"]:
                expect = f["expected_workflow"] or "clarification"
                actual = f["actual_workflow"] or "clarification"
                print(f"  {f['id']}: expected {expect}, got {actual} ({f['outcome']})")

    return 0 if report["meta"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
