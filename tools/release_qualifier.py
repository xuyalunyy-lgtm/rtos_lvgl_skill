#!/usr/bin/env python3
"""
Release Qualifier v12.0.7 — 发布资格评估门禁。

聚合 supervisor report、HIL result、Eval result、pattern miner 候选，
输出 pass/warn/fail 三态发布结论。

用法:
    python tools/release_qualifier.py --run .codex/runs/<id> --hil hil_result.json
    python tools/release_qualifier.py --eval eval_result.json --json
    python tools/release_qualifier.py --self-test
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def qualify(
    supervisor_report: dict | None = None,
    hil_result: dict | None = None,
    eval_result: dict | None = None,
    evidence_summary: dict | None = None,
) -> dict:
    """执行发布资格评估。"""
    qid = f"rq-{int(datetime.now().timestamp())}"
    checks = []
    blockers = []
    acceptable_risks = []
    reproduce = []

    # Check 1: Supervisor 状态
    if supervisor_report:
        status = supervisor_report.get("status", "unknown")
        passed = status == "success"
        checks.append({
            "name": "supervisor_status",
            "result": "pass" if passed else "fail",
            "detail": f"status={status}",
            "blocking": True,
        })
        if not passed:
            blockers.append(f"Supervisor 状态: {status}")
        reproduce.append(f"python scripts/codex_supervisor.py status --run-id {supervisor_report.get('run_id', '?')}")
    else:
        checks.append({"name": "supervisor_status", "result": "skip", "detail": "未提供", "blocking": False})

    # Check 2: HIL 结果
    if hil_result:
        status = hil_result.get("status", "unknown")
        dry_run = hil_result.get("dry_run", False)
        if dry_run:
            checks.append({
                "name": "hil_result",
                "result": "warn",
                "detail": f"dry-run, status={status}",
                "blocking": False,
            })
            acceptable_risks.append("HIL 为 dry-run，未验证真实硬件")
        else:
            passed = status == "pass"
            checks.append({
                "name": "hil_result",
                "result": "pass" if passed else "fail",
                "detail": f"status={status}, board={hil_result.get('board_id', '?')}",
                "blocking": True,
            })
            if not passed:
                blockers.append(f"HIL 失败: {hil_result.get('failure_reason', status)}")
    else:
        checks.append({"name": "hil_result", "result": "skip", "detail": "未提供", "blocking": False})
        acceptable_risks.append("未运行 HIL 验证")

    # Check 3: Eval 结果
    if eval_result:
        rate = eval_result.get("success_rate", 0)
        passed = rate >= 0.8
        checks.append({
            "name": "eval_result",
            "result": "pass" if passed else ("warn" if rate >= 0.5 else "fail"),
            "detail": f"success_rate={rate:.0%}",
            "blocking": rate < 0.5,
        })
        if rate < 0.5:
            blockers.append(f"评估通过率过低: {rate:.0%}")
    else:
        checks.append({"name": "eval_result", "result": "skip", "detail": "未提供", "blocking": False})

    # Check 4: Pattern miner 候选
    if evidence_summary:
        candidates = evidence_summary.get("open_candidates", 0)
        if candidates > 5:
            checks.append({
                "name": "pattern_candidates",
                "result": "warn",
                "detail": f"{candidates} 个未处理候选",
                "blocking": False,
            })
            acceptable_risks.append(f"{candidates} 个 learning candidate 未处理")
        else:
            checks.append({
                "name": "pattern_candidates",
                "result": "pass",
                "detail": f"{candidates} 个未处理候选",
                "blocking": False,
            })
    else:
        checks.append({"name": "pattern_candidates", "result": "skip", "detail": "未提供", "blocking": False})

    # 综合结论
    has_blocker = any(c.get("blocking") and c["result"] == "fail" for c in checks)
    has_warn = any(c["result"] == "warn" for c in checks)

    if has_blocker:
        conclusion = "fail"
    elif has_warn:
        conclusion = "warn"
    else:
        conclusion = "pass"

    return {
        "qualification_id": qid,
        "conclusion": conclusion,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "inputs": {
            "supervisor_report": supervisor_report.get("run_id", "") if supervisor_report else "",
            "hil_result": hil_result.get("run_id", "") if hil_result else "",
            "eval_result": eval_result.get("eval_id", "") if eval_result else "",
        },
        "checks": checks,
        "blockers": blockers,
        "acceptable_risks": acceptable_risks,
        "reproduce_commands": reproduce,
    }


def run_self_test() -> int:
    passed = 0
    failed = 0

    # 1. 全部通过
    r = qualify(
        supervisor_report={"run_id": "r1", "status": "success"},
        hil_result={"run_id": "h1", "status": "pass", "dry_run": False},
        eval_result={"eval_id": "e1", "success_rate": 0.95},
    )
    assert r["conclusion"] == "pass"
    print("[PASS] all pass → pass")
    passed += 1

    # 2. HIL 失败阻断
    r = qualify(
        supervisor_report={"run_id": "r1", "status": "success"},
        hil_result={"run_id": "h1", "status": "fail", "failure_reason": "boot_fail"},
    )
    assert r["conclusion"] == "fail"
    assert len(r["blockers"]) > 0
    print("[PASS] HIL fail → fail")
    passed += 1

    # 3. HIL dry-run 降级为 warn
    r = qualify(
        supervisor_report={"run_id": "r1", "status": "success"},
        hil_result={"run_id": "h1", "status": "pass", "dry_run": True},
    )
    assert r["conclusion"] == "warn"
    print("[PASS] HIL dry-run → warn")
    passed += 1

    # 4. Supervisor 失败阻断
    r = qualify(supervisor_report={"run_id": "r1", "status": "failed"})
    assert r["conclusion"] == "fail"
    print("[PASS] supervisor fail → fail")
    passed += 1

    # 5. 无输入 → skip
    r = qualify()
    assert r["conclusion"] == "pass"  # 无阻断项
    print("[PASS] no inputs → pass (no blockers)")
    passed += 1

    print(f"\nSelf-test: {passed} passed, {failed} failed")
    return 1 if failed > 0 else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Release Qualifier v12.0.7")
    parser.add_argument("--run", help="Supervisor report JSON 路径")
    parser.add_argument("--hil", help="HIL result JSON 路径")
    parser.add_argument("--eval", help="Eval result JSON 路径")
    parser.add_argument("--evidence", help="Evidence summary JSON 路径")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    def _load(p): return json.loads(Path(p).read_text(encoding="utf-8")) if p and Path(p).exists() else None

    r = qualify(
        supervisor_report=_load(args.run),
        hil_result=_load(args.hil),
        eval_result=_load(args.eval),
        evidence_summary=_load(args.evidence),
    )

    if args.json:
        print(json.dumps(r, indent=2, ensure_ascii=False))
    else:
        icon = {"pass": "✅", "warn": "⚠️", "fail": "❌"}.get(r["conclusion"], "?")
        print(f"{icon} 结论: {r['conclusion']}")
        for c in r["checks"]:
            ci = {"pass": "✅", "warn": "⚠️", "fail": "❌", "skip": "⏭"}.get(c["result"], "?")
            print(f"  {ci} {c['name']}: {c['detail']}")
        if r["blockers"]:
            print("阻断项:")
            for b in r["blockers"]:
                print(f"  - {b}")

    return 0 if r["conclusion"] != "fail" else 1


if __name__ == "__main__":
    sys.exit(main())
