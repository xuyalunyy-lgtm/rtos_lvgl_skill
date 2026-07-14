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

import re
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
SKILL_ROOT = TOOLS_DIR.parent

# 从文件名推断约束 ID
CONSTRAINT_FROM_FILENAME = re.compile(r"(?:^|[^a-zA-Z])(C\d+)(?:[^a-zA-Z]|$)")

# good/bad 文件名模式
GOOD_PATTERN = re.compile(r"good_", re.IGNORECASE)
BAD_PATTERN = re.compile(r"bad_", re.IGNORECASE)

# 已注册的约束 ID（来自 checker_registry.py 的 ALL_CHECKERS）
REGISTERED_CONSTRAINTS = {
    "C1", "C2", "C3", "C4", "C5", "C7", "C8", "C9", "C10",
    "C11", "C12", "C13", "C14", "C15", "C16",
    "C18", "C19", "C20", "C21", "C22", "C23", "C24",
    "C25", "C26", "C27", "C28", "C29", "C31", "C32", "C33",
    "C34", "C35", "C36", "C37", "C39", "C42", "C43", "C44", "C45",
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
        for f in sorted(search_dir.iterdir()):
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
    }
    name_lower = filename.lower()
    for key, cids in mapping.items():
        if key in name_lower:
            return cids
    return []


def check_coverage() -> tuple[list[dict], list[dict]]:
    """检查约束样本覆盖率。返回 (issues, summary)。"""
    samples = scan_samples()
    issues = []
    summary = []

    for cid in sorted(REGISTERED_CONSTRAINTS):
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
                "constraint": cid,
                "type": "missing_good",
                "message": f"{cid}: no good sample found in examples/ or fixtures/",
            })
        if bad_count == 0:
            issues.append({
                "constraint": cid,
                "type": "missing_bad",
                "message": f"{cid}: no bad sample found in examples/ or fixtures/",
            })

    return issues, summary


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="C41 regression sample coverage checker")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    issues, summary = check_coverage()

    good_covered = sum(1 for s in summary if s["good_samples"] > 0)
    bad_covered = sum(1 for s in summary if s["bad_samples"] > 0)
    total = len(REGISTERED_CONSTRAINTS)

    if args.json:
        import json
        json.dump({
            "total_constraints": total,
            "good_coverage": f"{good_covered}/{total}",
            "bad_coverage": f"{bad_covered}/{total}",
            "issues": issues,
            "summary": summary,
        }, sys.stdout, ensure_ascii=False, indent=2)
        print()
    else:
        print(f"C41 Regression Sample Coverage: {total} constraints")
        print(f"  Good samples: {good_covered}/{total}")
        print(f"  Bad samples:  {bad_covered}/{total}")
        if issues:
            print(f"\nMissing samples ({len(issues)}):")
            for issue in issues:
                print(f"  - {issue['message']}")
        else:
            print("\nAll constraints have good + bad samples.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
