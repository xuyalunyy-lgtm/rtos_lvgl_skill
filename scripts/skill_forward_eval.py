#!/usr/bin/env python3
"""
Skill Forward Eval — 离线确定性行为回归。

默认模式：校验 eval case schema、expected markers、fixture outputs。
可选 live 模式：调用 Codex/agent 实际跑 prompt（不进入默认 release gate）。

用法:
    python scripts/skill_forward_eval.py --self-test
    python scripts/skill_forward_eval.py --dry-run
    python scripts/skill_forward_eval.py --json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
LOGS_DIR = TOOLS / "fixtures" / "logs"

# ── Eval Cases ──
EVAL_CASES = [
    {
        "id": "crash_triage",
        "name": "Crash 日志快速定位",
        "description": "从 WDT 日志快速定位 bug 并给出证据链",
        "input_fixture": "bad_wdt_queue_full.log",
        "expected_markers": ["WDT_RESET", "C31", "next_actions"],
        "forbidden_markers": [],
        "check_type": "log_triage",
    },
    {
        "id": "hardware_challenge",
        "name": "硬件问题质疑",
        "description": "brownout/I2C 异常必须质疑硬件",
        "input_fixture": "bad_brownout.log",
        "expected_markers": ["BROWNOUT_RESET", "hardware_challenge"],
        "forbidden_markers": [],
        "check_type": "log_triage",
    },
    {
        "id": "architecture_refactor",
        "name": "架构重构建议",
        "description": "生命周期混乱必须建议重构",
        "input_fixture": "bad_lifecycle_chaos.log",
        "expected_markers": ["LIFECYCLE_CHAOS", "architecture_refactor"],
        "forbidden_markers": [],
        "check_type": "log_triage",
    },
    {
        "id": "codegen_contract",
        "name": "代码生成约束",
        "description": "manifest contract 校验必须能识别 lifecycle/exit_policy 等字段",
        "input_fixture": None,
        "expected_markers": ["passed", "contract_summary", "tasks"],
        "forbidden_markers": [],
        "check_type": "manifest_contract",
    },
    {
        "id": "release_usage",
        "name": "Release 使用场景",
        "description": "文档必须说明 skill 使用方式",
        "input_fixture": None,
        "expected_markers": ["skill", "workflow", "platform"],
        "forbidden_markers": [],
        "check_type": "doc_check",
    },
]


def _check_log_triage(case: dict) -> dict:
    """检查 log_triage 对 fixture 的输出。"""
    fixture = case.get("input_fixture")
    if not fixture:
        return {"passed": False, "errors": ["no input_fixture"]}

    log_path = LOGS_DIR / fixture
    if not log_path.exists():
        return {"passed": False, "errors": [f"fixture not found: {fixture}"]}

    sys.path.insert(0, str(TOOLS))
    from log_triage import triage

    log_text = log_path.read_text(encoding="utf-8")
    r = triage(log_text, "esp32")

    errors = []
    r_text = json.dumps(r)

    for marker in case.get("expected_markers", []):
        if marker not in r_text:
            errors.append(f"expected marker missing: {marker}")

    for marker in case.get("forbidden_markers", []):
        if marker in r_text:
            errors.append(f"forbidden marker found: {marker}")

    return {"passed": len(errors) == 0, "errors": errors, "output_summary": r.get("summary", "")}


def _check_manifest_contract(case: dict) -> dict:
    """检查 manifest contract 输出。"""
    sys.path.insert(0, str(TOOLS))
    from manifest_contract import validate

    # 用 voice-screen preset 生成的 manifest 做测试
    preset_dir = ROOT / "scene_presets"
    if not preset_dir.exists():
        return {"passed": False, "errors": ["scene_presets not found"]}

    # 用一个简单 manifest 测试 contract 校验
    test_manifest = {
        "schema_version": "1.2", "generator": "test", "platform": "esp32",
        "generated_files": [{"path": "main.c"}],
        "tasks": [{"name": "t1", "entry": "t1_func", "stack_bytes": 2048, "priority": 5,
                   "lifecycle": "long_running", "exit_policy": "stop_token", "watchdog": "feed",
                   "produces": [], "consumes": [], "holds": []}],
        "queues": [], "locks": [], "timers": [], "memory_pools": [],
        "constraints": {"required": ["C8"], "covered": ["C8"]},
        "verification_commands": ["python tools/codegen_gate.py --self-test"],
    }
    r = validate(test_manifest, strict=True)

    errors = []
    r_text = json.dumps(r)

    for marker in case.get("expected_markers", []):
        if marker not in r_text:
            errors.append(f"expected marker missing: {marker}")

    return {"passed": len(errors) == 0, "errors": errors}


def _check_doc(case: dict) -> dict:
    """检查文档是否包含预期关键词。"""
    # 检查 usage_examples.md
    doc = ROOT / "references" / "usage_examples.md"
    if not doc.exists():
        return {"passed": False, "errors": ["usage_examples.md not found"]}

    text = doc.read_text(encoding="utf-8").lower()
    errors = []

    for marker in case.get("expected_markers", []):
        if marker.lower() not in text:
            errors.append(f"expected marker missing in docs: {marker}")

    return {"passed": len(errors) == 0, "errors": errors}


CHECKERS = {
    "log_triage": _check_log_triage,
    "manifest_contract": _check_manifest_contract,
    "doc_check": _check_doc,
}


def run_all(dry_run: bool = False) -> dict:
    """运行所有 eval cases。"""
    results = []
    all_passed = True

    for case in EVAL_CASES:
        checker = CHECKERS.get(case.get("check_type", ""))
        if not checker:
            results.append({"id": case["id"], "passed": False, "errors": [f"unknown check_type: {case['check_type']}"]})
            all_passed = False
            continue

        if dry_run:
            results.append({"id": case["id"], "name": case["name"], "passed": True, "errors": [], "dry_run": True})
            continue

        r = checker(case)
        if not r["passed"]:
            all_passed = False

        results.append({
            "id": case["id"],
            "name": case["name"],
            "passed": r["passed"],
            "errors": r.get("errors", []),
            "output_summary": r.get("output_summary", ""),
        })

    return {
        "passed": all_passed,
        "total": len(results),
        "passed_count": sum(1 for r in results if r["passed"]),
        "results": results,
    }


def run_self_test() -> int:
    passed = 0
    failed = 0

    # 1. Eval cases 结构
    assert len(EVAL_CASES) >= 5
    for c in EVAL_CASES:
        assert "id" in c
        assert "expected_markers" in c
        assert "check_type" in c
    print(f"[PASS] {len(EVAL_CASES)} eval cases defined")
    passed += 1

    # 2. Dry-run
    r = run_all(dry_run=True)
    assert r["passed"] is True
    assert r["total"] == len(EVAL_CASES)
    print(f"[PASS] dry-run: {r['total']} cases")
    passed += 1

    # 3. 真实运行
    r = run_all(dry_run=False)
    print(f"[PASS] real run: {r['passed_count']}/{r['total']} passed")
    for cr in r["results"]:
        icon = "[PASS]" if cr["passed"] else "[FAIL]"
        print(f"  {icon} {cr['id']}: {cr.get('output_summary', '')[:60]}")
        if cr["errors"]:
            for e in cr["errors"]:
                print(f"    - {e}")
    if r["passed"]:
        passed += 1
    else:
        failed += 1

    print(f"\nSelf-test: {passed} passed, {failed} failed")
    return 1 if failed > 0 else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Skill Forward Eval")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    r = run_all(dry_run=args.dry_run)

    if args.json:
        print(json.dumps(r, indent=2, ensure_ascii=False))
    else:
        print(f"Forward Eval: {r['passed_count']}/{r['total']} passed")
        for cr in r["results"]:
            icon = "[PASS]" if cr["passed"] else "[FAIL]"
            print(f"  {icon} {cr['id']}: {cr['name']}")

    return 0 if r["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
