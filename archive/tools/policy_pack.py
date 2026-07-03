#!/usr/bin/env python3
"""
Policy Pack v11.0.3 — 可复用门禁策略包。

将 gate 规则、风险偏好、允许命令、保护路径、验证命令抽成可复用策略包。
内置 4 个策略：local_safe、ci_review_only、auto_low_risk、release_strict。

用法:
    python tools/policy_pack.py list
    python tools/policy_pack.py show local_safe
    python tools/policy_pack.py validate .codex/policies/local_safe.json
    python tools/policy_pack.py apply local_safe --plan plan.json
    python tools/policy_pack.py --self-test
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POLICIES_DIR = ROOT / ".codex" / "policies"


def list_policies() -> list[dict]:
    """列出所有可用策略。"""
    policies = []
    if not POLICIES_DIR.is_dir():
        return policies
    for f in sorted(POLICIES_DIR.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            policies.append({
                "policy_id": data.get("policy_id", f.stem),
                "name": data.get("name", ""),
                "description": data.get("description", ""),
                "risk_preference": data.get("risk_preference", ""),
            })
        except Exception:
            pass
    return policies


def load_policy(policy_id: str) -> dict:
    """加载策略。"""
    path = POLICIES_DIR / f"{policy_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"策略不存在: {policy_id}")
    return json.loads(path.read_text(encoding="utf-8"))


def validate_policy(data: dict) -> list[str]:
    """校验策略结构，返回错误列表。"""
    errors = []
    required = ["policy_id", "name", "risk_preference"]
    for f in required:
        if f not in data:
            errors.append(f"缺少必填字段: {f}")

    valid_risk = {"auto_low", "auto_medium", "manual_high", "reject_critical"}
    if data.get("risk_preference") not in valid_risk:
        errors.append(f"risk_preference 无效: {data.get('risk_preference')} (允许: {valid_risk})")

    if not isinstance(data.get("allowed_path_prefixes", []), list):
        errors.append("allowed_path_prefixes 必须是数组")
    if not isinstance(data.get("blocked_path_prefixes", []), list):
        errors.append("blocked_path_prefixes 必须是数组")
    if not isinstance(data.get("verification_commands", []), list):
        errors.append("verification_commands 必须是数组")

    return errors


def apply_policy(policy_id: str, plan_path: str) -> dict:
    """用策略校验计划，返回决策。"""
    policy = load_policy(policy_id)
    plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))

    violations = []
    warnings = []

    risk_map = {"auto_low": 0, "auto_medium": 1, "manual_high": 2, "reject_critical": 3}
    risk_order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
    pref = risk_map.get(policy.get("risk_preference", "auto_low"), 0)
    plan_risk = risk_order.get(plan.get("risk_level", "medium"), 1)

    # 风险检查
    if plan.get("risk_level") == "critical" and policy.get("risk_preference") == "reject_critical":
        violations.append("critical 风险被策略拒绝")
    if plan_risk > pref:
        warnings.append(f"计划风险 {plan.get('risk_level')} 超过策略偏好 {policy.get('risk_preference')}")

    # 路径检查
    blocked = policy.get("blocked_path_prefixes", [])
    for f in plan.get("files_to_change", []):
        for b in blocked:
            if f.startswith(b) or f == b:
                violations.append(f"策略禁止修改: {f}")

    # 命令检查
    blocked_cmds = policy.get("blocked_command_patterns", [])
    for cmd_entry in plan.get("commands", []):
        cmd = cmd_entry.get("cmd", "") if isinstance(cmd_entry, dict) else str(cmd_entry)
        for bc in blocked_cmds:
            if bc in cmd:
                violations.append(f"策略禁止命令: {cmd}")

    decision = "reject" if violations else ("needs_review" if warnings else "approve")
    return {
        "decision": decision,
        "policy_id": policy_id,
        "violations": violations,
        "warnings": warnings,
    }


def run_self_test() -> int:
    passed = 0
    failed = 0

    # 1. List policies
    policies = list_policies()
    assert len(policies) >= 4, f"Expected >=4 policies, got {len(policies)}"
    print(f"[PASS] {len(policies)} policies found")
    passed += 1

    # 2. Load each policy
    for p in policies:
        try:
            data = load_policy(p["policy_id"])
            assert "policy_id" in data
            print(f"[PASS] load {p['policy_id']}")
            passed += 1
        except Exception as e:
            print(f"[FAIL] load {p['policy_id']}: {e}")
            failed += 1

    # 3. Validate each policy
    for p in policies:
        data = load_policy(p["policy_id"])
        errors = validate_policy(data)
        if errors:
            print(f"[FAIL] validate {p['policy_id']}: {errors}")
            failed += 1
        else:
            print(f"[PASS] validate {p['policy_id']}")
            passed += 1

    # 4. Apply local_safe to low-risk plan
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({"intent": "test", "risk_level": "low", "files_to_change": ["tools/x.py"]}, f)
        plan_path = f.name
    try:
        r = apply_policy("local_safe", plan_path)
        assert r["decision"] == "approve"
        print("[PASS] local_safe + low risk → approve")
        passed += 1
    finally:
        import os
        os.unlink(plan_path)

    # 5. Apply release_strict to any change
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({"intent": "test", "risk_level": "low", "files_to_change": ["tools/x.py"]}, f)
        plan_path = f.name
    try:
        r = apply_policy("release_strict", plan_path)
        assert r["decision"] == "reject"
        print("[PASS] release_strict + tools/ change → reject")
        passed += 1
    finally:
        os.unlink(plan_path)

    print(f"\nSelf-test: {passed} passed, {failed} failed")
    return 1 if failed > 0 else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Policy Pack v11.0.3")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("list", help="列出所有策略")

    p_show = sub.add_parser("show", help="显示策略详情")
    p_show.add_argument("policy_id")

    p_val = sub.add_parser("validate", help="校验策略文件")
    p_val.add_argument("path")

    p_apply = sub.add_parser("apply", help="用策略校验计划")
    p_apply.add_argument("policy_id")
    p_apply.add_argument("--plan", required=True)

    parser.add_argument("--self-test", action="store_true")

    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    if not args.command:
        parser.print_help()
        return 1

    if args.command == "list":
        for p in list_policies():
            print(f"  {p['policy_id']:20s} {p['name']}")
        return 0

    if args.command == "show":
        data = load_policy(args.policy_id)
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return 0

    if args.command == "validate":
        data = json.loads(Path(args.path).read_text(encoding="utf-8"))
        errors = validate_policy(data)
        if errors:
            print("校验失败:")
            for e in errors:
                print(f"  - {e}")
            return 1
        print("校验通过。")
        return 0

    if args.command == "apply":
        r = apply_policy(args.policy_id, args.plan)
        print(json.dumps(r, indent=2, ensure_ascii=False))
        return 0 if r["decision"] != "reject" else 1

    return 1


if __name__ == "__main__":
    sys.exit(main())
