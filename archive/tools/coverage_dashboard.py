#!/usr/bin/env python3
"""
Coverage Dashboard v16.0.6 — 约束/框架/Checker 覆盖矩阵。

输出项目级覆盖矩阵：哪些约束有 checker、哪些只有人工规则、哪些框架被检测但没有检查器。

用法:
    python tools/coverage_dashboard.py --dir tools/fixtures/mini_esp32 --platform esp32
    python tools/coverage_dashboard.py --dir tools/fixtures/mini_esp32 --json
    python tools/coverage_dashboard.py --self-test
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def build_coverage(dir_path: str, platform: str = "") -> dict:
    """构建覆盖矩阵。"""
    from project_operating_model import build_operating_model
    model = build_operating_model(dir_path, platform)

    # 核心约束覆盖
    core_covered = set(model["constraint_coverage"]["core_covered"])

    # 所有 C1-C45
    all_core = {f"C{i}" for i in range(1, 46)}
    core_missing = sorted(all_core - core_covered)

    # 框架约束覆盖
    fw_constraints = model["constraint_coverage"]["framework_constraints"]
    fw_with_checker = [c for c in fw_constraints if c.get("has_checker")]
    fw_without_checker = [c for c in fw_constraints if not c.get("has_checker")]

    # 框架检测 vs 检查器
    fw_detected = {fw["framework_id"] for fw in model["frameworks"]}

    # 已注册检查器的框架
    fw_with_checkers = set()
    try:
        from framework_constraint_checker import CHECKERS
        fw_with_checkers = set(CHECKERS.keys())
    except ImportError:
        pass

    fw_no_checker = fw_detected - fw_with_checkers

    return {
        "project": model["project"],
        "platform": model["platform"],
        "core_constraints": {
            "total": len(all_core),
            "covered": sorted(core_covered),
            "covered_count": len(core_covered),
            "missing": core_missing,
            "missing_count": len(core_missing),
            "coverage_pct": round(len(core_covered) / len(all_core) * 100, 1),
        },
        "framework_constraints": {
            "total": len(fw_constraints),
            "with_checker": len(fw_with_checker),
            "without_checker": len(fw_without_checker),
            "without_checker_list": [c["id"] for c in fw_without_checker[:10]],
        },
        "framework_detection": {
            "detected": sorted(fw_detected),
            "with_checker": sorted(fw_with_checkers & fw_detected),
            "without_checker": sorted(fw_no_checker),
        },
        "gaps": {
            "core_missing": core_missing,
            "fw_no_checker": sorted(fw_no_checker),
            "fw_constraint_no_checker": [c["id"] for c in fw_without_checker[:10]],
        },
    }


def format_report(cov: dict) -> str:
    """格式化文本报告。"""
    lines = [
        "=" * 60,
        f"Coverage Dashboard: {cov['project']} ({cov['platform']})",
        "=" * 60,
        "",
        f"Core Constraints: {cov['core_constraints']['covered_count']}/{cov['core_constraints']['total']} ({cov['core_constraints']['coverage_pct']}%)",
    ]

    if cov["core_constraints"]["missing"]:
        lines.append(f"  Missing: {', '.join(cov['core_constraints']['missing'][:10])}")

    lines.extend([
        "",
        f"Framework Constraints: {cov['framework_constraints']['with_checker']}/{cov['framework_constraints']['total']} with checker",
    ])

    if cov["framework_constraints"]["without_checker_list"]:
        lines.append(f"  No checker: {', '.join(cov['framework_constraints']['without_checker_list'][:5])}")

    lines.extend([
        "",
        f"Frameworks Detected: {len(cov['framework_detection']['detected'])}",
        f"  With checker: {', '.join(cov['framework_detection']['with_checker']) or 'none'}",
        f"  Without checker: {', '.join(cov['framework_detection']['without_checker']) or 'none'}",
    ])

    if cov["gaps"]["core_missing"]:
        lines.extend(["", "Gaps to close:"])
        for g in cov["gaps"]["core_missing"][:5]:
            lines.append(f"  - {g}: no checker")

    return "\n".join(lines)


def run_self_test() -> int:
    passed = 0
    failed = 0

    mini = ROOT / "tools" / "fixtures" / "mini_esp32"
    if mini.is_dir():
        cov = build_coverage(str(mini), "esp32")
        assert cov["core_constraints"]["covered_count"] >= 30
        assert cov["core_constraints"]["coverage_pct"] >= 60
        print(f"[PASS] coverage: {cov['core_constraints']['coverage_pct']}% core, {cov['framework_constraints']['with_checker']} fw with checker")
        passed += 1

        report = format_report(cov)
        assert "Coverage Dashboard" in report
        print("[PASS] report format")
        passed += 1

    print(f"\nSelf-test: {passed} passed, {failed} failed")
    return 1 if failed > 0 else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Coverage Dashboard v16.0.6")
    parser.add_argument("--dir", help="项目目录")
    parser.add_argument("--platform", default="", help="平台")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    if not args.dir:
        parser.print_help()
        return 1

    cov = build_coverage(args.dir, args.platform)

    if args.json:
        print(json.dumps(cov, indent=2, ensure_ascii=False))
    else:
        print(format_report(cov))

    return 0


if __name__ == "__main__":
    sys.exit(main())
