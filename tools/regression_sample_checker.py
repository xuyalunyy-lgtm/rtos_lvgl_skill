#!/usr/bin/env python3
"""
C41 回归样本覆盖率检查器。

检查项:
  C41.1 — 每个已注册约束应有至少一个 good 样本
  C41.2 — 每个已注册约束应有至少一个 bad 样本

扫描 examples/ 和 tools/fixtures/ 目录，建立约束 ID → 样本文件映射。

用法:
    python tools/regression_sample_checker.py
    python tools/regression_sample_checker.py --json
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from checker_io import configure_stdout, output_json

TOOLS_DIR = Path(__file__).resolve().parent
SKILL_ROOT = TOOLS_DIR.parent

# 从文件名推断约束 ID
CONSTRAINT_FROM_FILENAME = re.compile(r"(?:^|[^a-zA-Z])(C\d+)(?:[^a-zA-Z]|$)")

# good/bad 文件名模式
GOOD_PATTERN = re.compile(r"good_", re.IGNORECASE)
BAD_PATTERN = re.compile(r"bad_", re.IGNORECASE)

def registered_constraints() -> set[str]:
    """Read registered root constraints from the single checker registry."""
    from checker_registry import ALL_CHECKERS

    # C41 audits other checker constraints; requiring a C41 fixture for the
    # coverage checker itself would be a recursive, permanently failing rule.
    return {
        root for spec in ALL_CHECKERS for domain in spec.domains
        if (root := domain.split(".", 1)[0]) != "C41"
    }


def scan_samples() -> dict[str, dict[str, list[str]]]:
    """扫描样本目录，返回 {constraint_id: {good: [paths], bad: [paths]}}。"""
    samples: dict[str, dict[str, list[str]]] = {}

    search_dirs = [
        SKILL_ROOT / "examples",
        SKILL_ROOT / "tools" / "fixtures",
    ]

    for search_dir in search_dirs:
        if not search_dir.is_dir():
            continue
        for f in sorted(search_dir.rglob("*")):
            if not f.is_file():
                continue
            if f.suffix not in (".c", ".h", ".cpp", ".json", ".yaml", ".txt"):
                continue
            name = f.name
            is_good = bool(GOOD_PATTERN.search(name))
            is_bad = bool(BAD_PATTERN.search(name))
            if not is_good and not is_bad:
                continue

            # 从文件名提取约束 ID
            constraint_ids = CONSTRAINT_FROM_FILENAME.findall(name)
            # 也检查 fixtures 中以 checker 名命名的文件
            if not constraint_ids:
                # 尝试从 checker_registry 的 SELF_TEST_CASES 映射
                constraint_ids = _infer_constraint_from_fixture(name)

            for cid in constraint_ids:
                cid = cid.upper()
                if cid not in samples:
                    samples[cid] = {"good": [], "bad": []}
                rel_path = str(f.relative_to(SKILL_ROOT))
                if is_good:
                    samples[cid]["good"].append(rel_path)
                else:
                    samples[cid]["bad"].append(rel_path)

    return samples


def _infer_constraint_from_fixture(filename: str) -> list[str]:
    """从 fixtures 文件名推断约束 ID。"""
    mapping = {
        "cjson": ["C3"],
        "isr": ["C4"],
        "lvgl": ["C1"],
        "queue": ["C2"],
        "timeout_budget": ["C31"],
        "efficiency_budget": ["C36"],
        "lock_budget": ["C43"],
        "critical_section": ["C44"],
        "sensor_integration": ["C45"],
        "boot_sequence": ["C8"],
        "stack_alloc": ["C7"],
        "lifecycle": ["C33"],
        "peripheral_shutdown": ["C24"],
        "backpressure": ["C37"],
        "critical_path": ["C35"],
        "priority": ["C15"],
        "observability": ["C32"],
        "config_matrix": ["C39"],
        "state_machine": ["C13"],
        "timer": ["C16"],
        "log_desensitize": ["C14"],
        "test_macro": ["C5"],
        "coding_style": ["C11"],
        "function_length": ["C11"],
        "return_check": ["C12"],
        "logging": ["C14"],
        "board_resource": ["C42"],
        "module_boundary": ["C29"],
        "secret": ["C9"],
        "ota": ["C22"],
        "hotpath": ["C34"],
        "multi_core_ipc": ["C17"],
        "fault_isolation": ["C38"],
        "api_sequence": ["C20", "C23"],
        "ble_protocol": ["C46"],
        "ai_generated": ["C48"],
    }
    name_lower = filename.lower()
    for key, cids in mapping.items():
        if key in name_lower:
            return cids
    return []


def check_coverage(
    samples: dict[str, dict[str, list[str]]] | None = None,
    constraints: set[str] | None = None,
) -> tuple[list[dict], list[dict]]:
    """检查约束样本覆盖率。返回 (issues, summary)。"""
    samples = samples if samples is not None else scan_samples()
    issues = []
    summary = []

    for cid in sorted(constraints if constraints is not None else registered_constraints()):
        entry = samples.get(cid, {"good": [], "bad": []})
        good_count = len(entry["good"])
        bad_count = len(entry["bad"])

        summary.append({
            "constraint": cid,
            "good_samples": good_count,
            "bad_samples": bad_count,
            "good_files": entry["good"][:3],
            "bad_files": entry["bad"][:3],
        })

        if good_count == 0:
            issues.append({
                "id": "C41.1",
                "severity": "P1",
                "file": "examples/ or tools/fixtures/",
                "line": 0,
                "issue": f"{cid}: no good sample found in examples/ or fixtures/",
                "constraint": cid,
                "type": "missing_good",
            })
        if bad_count == 0:
            issues.append({
                "id": "C41.2",
                "severity": "P1",
                "file": "examples/ or tools/fixtures/",
                "line": 0,
                "issue": f"{cid}: no bad sample found in examples/ or fixtures/",
                "constraint": cid,
                "type": "missing_bad",
            })

    return issues, summary


def run_self_test() -> int:
    complete = {"C6": {"good": ["good_C6.json"], "bad": ["bad_C6.json"]}}
    issues, summary = check_coverage(complete, {"C6"})
    assert not issues and summary[0]["constraint"] == "C6"

    incomplete = {"C6": {"good": ["good_C6.json"], "bad": []}}
    issues, _summary = check_coverage(incomplete, {"C6"})
    assert len(issues) == 1 and issues[0]["type"] == "missing_bad"
    print("[PASS] regression sample checker self-test")
    return 0


def main() -> int:
    import argparse
    configure_stdout()
    parser = argparse.ArgumentParser(description="C41 regression sample coverage checker")
    parser.add_argument("files", nargs="*", help="reserved for checker-harness fixture compatibility")
    parser.add_argument("--self-test", action="store_true", help="run deterministic coverage-classification tests")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--jsonl", action="store_true", help="Emit checker-result/v1 JSON Lines output")
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    issues, summary = check_coverage()

    good_covered = sum(1 for s in summary if s["good_samples"] > 0)
    bad_covered = sum(1 for s in summary if s["bad_samples"] > 0)
    total = len(registered_constraints())

    payload = {
        "protocol_version": "checker-result/v1",
        "checker": "C41 regression sample coverage",
        "domains": ["C41"],
        "files_checked": sum(item["good_samples"] + item["bad_samples"] for item in summary),
        "violations": len(issues),
        "issues": issues,
        "total_constraints": total,
        "good_coverage": f"{good_covered}/{total}",
        "bad_coverage": f"{bad_covered}/{total}",
        "summary": summary,
    }
    if args.jsonl:
        print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    elif args.json:
        output_json(payload)
    else:
        print(f"C41 Regression Sample Coverage: {total} constraints")
        print(f"  Good samples: {good_covered}/{total}")
        print(f"  Bad samples:  {bad_covered}/{total}")
        if issues:
            print(f"\nMissing samples ({len(issues)}):")
            for issue in issues:
                print(f"  - {issue['issue']}")
        else:
            print("\nAll constraints have good + bad samples.")

    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
