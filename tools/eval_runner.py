#!/usr/bin/env python3
"""
Eval Runner v11.0.7 — 评估运行器。

扩展 forward_tests 为 eval corpus，输出成功率、平均迭代次数、
阻断原因分布、效率估算。

用法:
    python tools/eval_runner.py --suite supervisor
    python tools/eval_runner.py --suite all
    python tools/eval_runner.py --suite all --json
    python tools/eval_runner.py --self-test
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


# ============================================================================
# 评估用例
# ============================================================================

def _run(cmd: str, timeout: int = 300) -> dict:
    try:
        proc = subprocess.run(
            cmd, shell=True, capture_output=True, encoding="utf-8", errors="replace",
            timeout=timeout, cwd=str(ROOT), env={**__import__("os").environ, "PYTHONUTF8": "1"},
        )
        return {"exit_code": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}
    except subprocess.TimeoutExpired:
        return {"exit_code": -1, "error": "timeout"}
    except Exception as e:
        return {"exit_code": -1, "error": str(e)}


# Supervisor 评估用例
SUPERVISOR_CASES = [
    {
        "name": "self_test",
        "cmd": f"{sys.executable} scripts/codex_supervisor.py --self-test",
        "expect_exit": 0,
    },
    {
        "name": "queue_list",
        "cmd": f"{sys.executable} scripts/codex_supervisor.py queue",
        "expect_exit": 0,
    },
    {
        "name": "gate_low_risk",
        "cmd": f"""{sys.executable} -c "
import json, sys, tempfile
sys.path.insert(0, 'scripts')
from codex_supervisor import PlanResult, JobDef, run_gate, asdict
plan = PlanResult(intent='test', files_to_change=['tools/x.py'], risk_level='low')
gate = run_gate(plan, JobDef())
print(json.dumps(asdict(gate)))
assert gate.decision == 'approve', f'Expected approve, got {{gate.decision}}'
" """,
        "expect_exit": 0,
    },
    {
        "name": "gate_protected_path",
        "cmd": f"""{sys.executable} -c "
import json, sys
sys.path.insert(0, 'scripts')
from codex_supervisor import PlanResult, JobDef, run_gate, asdict
plan = PlanResult(intent='bad', files_to_change=['.git/config'], risk_level='low')
gate = run_gate(plan, JobDef())
assert gate.decision == 'reject', f'Expected reject, got {{gate.decision}}'
" """,
        "expect_exit": 0,
    },
    {
        "name": "gate_high_risk",
        "cmd": f"""{sys.executable} -c "
import json, sys
sys.path.insert(0, 'scripts')
from codex_supervisor import PlanResult, JobDef, run_gate
plan = PlanResult(intent='high', files_to_change=['tools/x.py'], risk_level='high')
gate = run_gate(plan, JobDef())
assert gate.decision == 'needs_confirmation', f'Expected needs_confirmation, got {{gate.decision}}'
" """,
        "expect_exit": 0,
    },
]

# Evidence store 评估用例
EVIDENCE_CASES = [
    {
        "name": "store_self_test",
        "cmd": f"{sys.executable} tools/evidence_store.py --self-test",
        "expect_exit": 0,
    },
]

# Policy pack 评估用例
POLICY_CASES = [
    {
        "name": "policy_self_test",
        "cmd": f"{sys.executable} tools/policy_pack.py --self-test",
        "expect_exit": 0,
    },
]

# Pattern miner 评估用例
PATTERN_CASES = [
    {
        "name": "miner_self_test",
        "cmd": f"{sys.executable} tools/pattern_miner.py --self-test",
        "expect_exit": 0,
    },
]

# 核心工具评估用例
CORE_CASES = [
    {
        "name": "evidence_schema_self_test",
        "cmd": f"{sys.executable} tools/evidence_schema.py --self-test",
        "expect_exit": 0,
    },
    {
        "name": "run_review_self_test",
        "cmd": f"{sys.executable} tools/run_review.py --self-test",
        "expect_exit": 0,
    },
    {
        "name": "skill_iterate_check",
        "cmd": f"{sys.executable} scripts/skill_iterate.py --check --skip-self-test",
        "expect_exit": 0,
    },
]

SUITES = {
    "supervisor": SUPERVISOR_CASES,
    "evidence": EVIDENCE_CASES,
    "policy": POLICY_CASES,
    "pattern": PATTERN_CASES,
    "core": CORE_CASES,
    "all": SUPERVISOR_CASES + EVIDENCE_CASES + POLICY_CASES + PATTERN_CASES + CORE_CASES,
}


# ============================================================================
# 运行器
# ============================================================================

def run_eval(suite_name: str) -> dict:
    """运行评估套件。"""
    cases = SUITES.get(suite_name, [])
    if not cases:
        return {"error": f"未知套件: {suite_name}"}

    eval_id = f"eval-{int(time.time())}"
    results = []
    passed = 0
    failed = 0
    skipped = 0
    block_reasons: dict[str, int] = {}

    for case in cases:
        start = time.time()
        r = _run(case["cmd"], timeout=case.get("timeout", 300))
        duration = time.time() - start

        actual_exit = r.get("exit_code", -1)
        expect_exit = case.get("expect_exit", 0)
        case_passed = actual_exit == expect_exit

        status = "pass" if case_passed else "fail"
        block_reason = ""

        if not case_passed:
            failed += 1
            if actual_exit == -1:
                block_reason = r.get("error", "unknown")
            else:
                block_reason = f"exit_code={actual_exit} (expected {expect_exit})"
            block_reasons[block_reason] = block_reasons.get(block_reason, 0) + 1
        else:
            passed += 1

        results.append({
            "name": case["name"],
            "status": status,
            "duration_seconds": round(duration, 2),
            "block_reason": block_reason,
        })

    total = passed + failed + skipped
    return {
        "eval_id": eval_id,
        "suite": suite_name,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_cases": total,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "success_rate": round(passed / total, 3) if total > 0 else 0,
        "avg_iterations": 1.0,
        "block_reasons": block_reasons,
        "cases": results,
    }


def run_self_test() -> int:
    passed = 0
    failed = 0

    # 1. 套件定义完整
    assert "supervisor" in SUITES
    assert "all" in SUITES
    assert len(SUITES["all"]) > 5
    print(f"[PASS] {len(SUITES)} suites, {len(SUITES['all'])} total cases")
    passed += 1

    # 2. 运行 supervisor self_test 用例
    case = SUPERVISOR_CASES[0]
    r = _run(case["cmd"], timeout=60)
    assert r["exit_code"] == case["expect_exit"], f"exit={r['exit_code']}"
    print(f"[PASS] supervisor self_test")
    passed += 1

    # 3. 运行 evidence self_test 用例
    case = EVIDENCE_CASES[0]
    r = _run(case["cmd"], timeout=60)
    assert r["exit_code"] == case["expect_exit"]
    print(f"[PASS] evidence self_test")
    passed += 1

    # 4. 运行 policy self_test 用例
    case = POLICY_CASES[0]
    r = _run(case["cmd"], timeout=60)
    assert r["exit_code"] == case["expect_exit"]
    print(f"[PASS] policy self_test")
    passed += 1

    # 5. run_eval 结构
    result = run_eval("evidence")
    assert "eval_id" in result
    assert "success_rate" in result
    assert result["passed"] >= 1
    print(f"[PASS] run_eval: {result['passed']}/{result['total_cases']}")
    passed += 1

    print(f"\nSelf-test: {passed} passed, {failed} failed")
    return 1 if failed > 0 else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Eval Runner v11.0.7")
    parser.add_argument("--suite", default="all", choices=list(SUITES.keys()))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--output", "-o")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    result = run_eval(args.suite)

    if args.output:
        Path(args.output).write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"结果已保存: {args.output}")

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"\n{'='*50}")
        print(f"套件: {result['suite']}")
        print(f"通过: {result['passed']}/{result['total_cases']} ({result['success_rate']:.0%})")
        if result.get("block_reasons"):
            print("阻断原因:")
            for reason, count in result["block_reasons"].items():
                print(f"  {reason}: {count}")
        print(f"{'='*50}")
        for c in result.get("cases", []):
            icon = "[OK]" if c["status"] == "pass" else "[X]"
            print(f"  {icon} {c['name']} ({c['duration_seconds']}s)")

    return 0 if result.get("failed", 1) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
