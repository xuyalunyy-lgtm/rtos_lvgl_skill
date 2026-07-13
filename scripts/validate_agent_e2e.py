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

# ── Frozen requests for real Agent evaluation ──

FROZEN_REQUESTS = [
    {
        "id": "e2e_01",
        "request": "Review this ESP32 cJSON parsing code for buffer overflow risks",
        "expected_workflow": "code_review",
        "expected_clarification": False,
        "must_load_prefix": "workflows/l2_code_review",
        "must_not_load": ["workflows/l3_lvgl_page", "workflows/debug_crash"],
    },
    {
        "id": "e2e_02",
        "request": "设备死机了，看门狗一直在重启，帮我分析日志",
        "expected_workflow": "crash_debug",
        "expected_clarification": False,
        "must_load_prefix": "workflows/debug_crash",
        "must_not_load": ["workflows/l2_code_review", "workflows/l3_lvgl_page"],
    },
    {
        "id": "e2e_03",
        "request": "根据这张设计截图生成 LVGL 界面代码",
        "expected_workflow": "lvgl_page",
        "expected_clarification": False,
        "must_load_prefix": "workflows/l3_lvgl_page",
        "must_not_load": ["workflows/l2_code_review", "workflows/debug_crash"],
    },
    {
        "id": "e2e_04",
        "request": "Analyze heap fragmentation in this STM32 firmware",
        "expected_workflow": "memory_analysis",
        "expected_clarification": False,
        "must_load_prefix": "workflows/l2_memory_analysis",
        "must_not_load": ["workflows/l3_lvgl_page", "workflows/debug_crash"],
    },
    {
        "id": "e2e_05",
        "request": "新板子刚焊好，需要验证外设工作是否正常",
        "expected_workflow": "bring_up",
        "expected_clarification": False,
        "must_load_prefix": "workflows/l3_bring_up",
        "must_not_load": ["workflows/l2_code_review", "workflows/l3_lvgl_page"],
    },
    {
        "id": "e2e_06",
        "request": "flash 空间不够了，帮我裁剪一下 SDK",
        "expected_workflow": "sdk_trim",
        "expected_clarification": False,
        "must_load_prefix": "workflows/l3_sdk_trim",
        "must_not_load": ["workflows/l2_code_review", "workflows/l3_lvgl_page"],
    },
    {
        "id": "e2e_07",
        "request": "用 manifest 生成一个多页面应用的脚手架",
        "expected_workflow": "app_manifest",
        "expected_clarification": False,
        "must_load_prefix": "workflows/l3_lvgl_page",
        "must_not_load": ["workflows/l2_code_review", "workflows/debug_crash"],
    },
    {
        "id": "e2e_08",
        "request": "帮我设计一个 MQTT 通信模块，需要支持断线重连",
        "expected_workflow": "new_module",
        "expected_clarification": False,
        "must_load_prefix": "workflows/l3_new_module",
        "must_not_load": ["workflows/l3_lvgl_page", "workflows/debug_crash"],
    },
    {
        "id": "e2e_09",
        "request": "Project review: audit the entire workspace before release",
        "expected_workflow": "project_review",
        "expected_clarification": False,
        "must_load_prefix": "workflows/l2_project_review",
        "must_not_load": ["workflows/l3_lvgl_page", "workflows/debug_crash"],
    },
    {
        "id": "e2e_10",
        "request": "SPI 和 I2C 引脚冲突了，帮我看看怎么解决",
        "expected_workflow": "hw_sw_debug",
        "expected_clarification": False,
        "must_load_prefix": "workflows/hw_sw_cocodebug",
        "must_not_load": ["workflows/l3_lvgl_page", "workflows/debug_crash"],
    },
    {
        "id": "e2e_11",
        "request": "帮我看看这个问题",
        "expected_workflow": None,
        "expected_clarification": True,
        "must_load_prefix": None,
        "must_not_load": [],
    },
    {
        "id": "e2e_12",
        "request": "LVGL page crashes with HardFault during rendering, need both UI fix and crash debug",
        "expected_workflow": None,
        "expected_clarification": True,
        "must_load_prefix": None,
        "must_not_load": [],
    },
]


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
