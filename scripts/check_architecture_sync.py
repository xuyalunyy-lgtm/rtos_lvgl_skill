#!/usr/bin/env python3
"""
Check architecture-guideline consistency between full and lite trees.

Usage:
  python scripts/check_architecture_sync.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
FULL = ROOT
LITE = ROOT / "freertos-skill-lite"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def missing_tokens(text: str, tokens: list[str]) -> list[str]:
    return [token for token in tokens if token not in text]


def check_pair(name: str, full_path: Path, lite_path: Path, tokens: list[str]) -> dict:
    issues = []
    lite_not_applicable = not LITE.exists()

    if not full_path.exists():
        issues.append(f"missing_full:{full_path}")
    if not lite_not_applicable and not lite_path.exists():
        issues.append(f"missing_lite:{lite_path}")
    if issues:
        return {"target": name, "pass": False, "issues": issues, "full": str(full_path), "lite": str(lite_path)}

    full_text = read_text(full_path)
    full_missing = missing_tokens(full_text, tokens)
    if full_missing:
        issues.append("full_missing_tokens:" + ",".join(full_missing))

    if not lite_not_applicable:
        lite_text = read_text(lite_path)
        lite_missing = missing_tokens(lite_text, tokens)
        if lite_missing:
            issues.append("lite_missing_tokens:" + ",".join(lite_missing))

    status = "not_applicable" if lite_not_applicable else None
    result: dict = {
        "target": name,
        "pass": not bool(issues),
        "issues": issues,
        "full": str(full_path),
        "lite": str(lite_path),
    }
    if status:
        result["status"] = status
    return result


def check_readme() -> dict:
    issues = []
    full_readme = FULL / "workflows" / "README.md"
    lite_readme = LITE / "workflows" / "README.md"
    required = ("I/P/O", "FSM/HFSM", "HAL")
    lite_not_applicable = not LITE.exists()

    if not full_readme.exists():
        issues.append("missing:workflows/README.md")
    if not lite_not_applicable and not lite_readme.exists():
        issues.append("missing:freertos-skill-lite/workflows/README.md")

    if not issues:
        full_text = read_text(full_readme)
        full_missing = [token for token in required if token not in full_text]
        if full_missing:
            issues.append("full_missing_arch_entry:" + ",".join(full_missing))

        if not lite_not_applicable:
            lite_text = read_text(lite_readme)
            lite_missing = [token for token in required if token not in lite_text]
            if lite_missing:
                issues.append("lite_missing_arch_entry:" + ",".join(lite_missing))

    result: dict = {
        "target": "workflow_readme_entry",
        "pass": not bool(issues),
        "issues": issues,
        "full": str(full_readme),
        "lite": str(lite_readme),
    }
    if lite_not_applicable:
        result["status"] = "not_applicable"
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Check architecture sync constraints")
    parser.add_argument("--json", action="store_true", help="Output json")
    args = parser.parse_args()

    checks = [
        check_pair(
            "software_architecture_design_prompt",
            FULL / "prompts" / "software_architecture_design.txt",
            LITE / "prompts" / "software_architecture_design.txt",
            ["I/P/O", "FSM", "HAL", "xxx_ops_t", "RTOS", "### A.", "### B.", "### C."],
        ),
        check_pair(
            "l2_architecture_review_workflow",
            FULL / "archive" / "workflows" / "l2_architecture_review.md",
            LITE / "archive" / "workflows" / "l2_architecture_review.md",
            ["Architecture Mandatory Checklist", "I/P/O", "FSM", "HAL", "P0:", "P1:", "P2:", "### A."],
        ),
        check_readme(),
    ]

    passed = all(item["pass"] for item in checks)

    if args.json:
        print(json.dumps({"pass": passed, "checks": checks}, ensure_ascii=False, indent=2))
        return 0 if passed else 1

    print(f"architecture_sync: {'PASS' if passed else 'FAIL'}")
    for item in checks:
        status = item.get("status")
        if item["pass"]:
            label = "NOT_APPLICABLE" if status == "not_applicable" else "PASS"
            print(f"- {item['target']}: {label}")
        else:
            print(f"- {item['target']}: FAIL")
            for issue in item["issues"]:
                print(f"  - {issue}")
    if not passed:
        print("Run after sync updates to clear all items.")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
