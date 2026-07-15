#!/usr/bin/env python3
"""One command: log triage -> targeted review -> fix plan -> verification report."""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run(argv: list[str]) -> tuple[int, str]:
    process = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return process.returncode, process.stdout


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", required=True)
    parser.add_argument("--dir", required=True)
    parser.add_argument("--platform", default="esp32")
    parser.add_argument("--output-dir", default="artifacts/diagnostic_loop")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    triage_rc, triage = run([
        sys.executable, "tools/log_triage.py", "--log", args.log,
        "--platform", args.platform, "--json",
    ])
    if triage_rc > 1:
        print(triage, file=sys.stderr)
        return triage_rc
    try:
        triage_json = json.loads(triage)
    except json.JSONDecodeError as exc:
        print(f"log_triage did not return JSON: {exc}", file=sys.stderr)
        return 1

    plan = triage_json.get("diagnostic_plan", {})
    plan_path = output_dir / "symptom_plan.json"
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    common = [
        sys.executable, "tools/run_review.py", "--dir", args.dir,
        "--platform", args.platform, "--from-symptom-plan", str(plan_path), "--json",
        "--history-dir", str(output_dir / "review_history"),
    ]
    review_rc, review = run([*common, "--suggest-fixes"])
    review_path = output_dir / "targeted_review.json"
    review_path.write_text(review, encoding="utf-8")

    # This intentionally does not apply fixes.  The second checker run validates
    # the present workspace against the immutable symptom plan, and can be run
    # again after an engineer applies a reviewed FixPlan.
    verify_rc, verification = run(common)
    verification_path = output_dir / "verification_review.json"
    verification_path.write_text(verification, encoding="utf-8")
    result = {
        "triage": str(plan_path),
        "review": str(review_path),
        "verification": str(verification_path),
        "fix_application": "not automated; apply the reviewed FixPlan, then rerun this command to compare history",
        "exit_code": max(triage_rc, review_rc, verify_rc),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
