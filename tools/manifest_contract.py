#!/usr/bin/env python3
"""
Manifest Contract Validator v20.0.1 — 校验 manifest 1.2 合同。

校验必填字段、枚举值、跨引用、timeout、full_policy、drop_counter、
task lifecycle、lock budget、timer callback budget、memory pool owner。

用法:
    python tools/manifest_contract.py --manifest generation_manifest.json --strict
    python tools/manifest_contract.py --self-test
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# ── 枚举定义 ──
VALID_LIFECYCLE = {"long_running", "on_demand", "periodic"}
VALID_EXIT_POLICY = {"stop_token", "never_exit", "delete_on_complete"}
VALID_WATCHDOG = {"feed", "notify", "none"}
VALID_FULL_POLICY = {"drop_oldest", "drop_newest", "block", "overwrite", "fail_immediately"}
VALID_LOCK_TYPE = {"mutex", "recursive_mutex", "binary_semaphore", "counting_semaphore"}
VALID_CALLBACK_POLICY = {"deferred", "direct", "notify_only"}
VALID_EVIDENCE_TYPE = {"code", "config", "topology", "comment", "structure"}


def validate(manifest: dict, strict: bool = False) -> dict:
    """校验 manifest 合同，返回统一结构。"""
    errors = []
    warnings = []
    violations = []

    version = manifest.get("schema_version", "1.0")

    # ── 基础字段 ──
    for f in ["schema_version", "generator", "platform", "generated_files", "constraints"]:
        if f not in manifest:
            errors.append(f"缺少必填字段: {f}")

    if errors:
        return _result(False, errors, warnings, violations)

    # ── Tasks ──
    tasks = manifest.get("tasks", [])
    task_names = set()
    for i, t in enumerate(tasks):
        prefix = f"tasks[{i}]({t.get('name', '?')})"

        # 必填字段
        for f in ["name", "entry", "stack_bytes", "priority", "lifecycle", "exit_policy"]:
            if not t.get(f) and t.get(f) != 0:
                errors.append(f"{prefix} 缺少 {f}")

        task_names.add(t.get("name", ""))

        # 枚举值
        if t.get("lifecycle") and t["lifecycle"] not in VALID_LIFECYCLE:
            errors.append(f"{prefix} lifecycle 无效: {t['lifecycle']}")
        if t.get("exit_policy") and t["exit_policy"] not in VALID_EXIT_POLICY:
            errors.append(f"{prefix} exit_policy 无效: {t['exit_policy']}")
        if t.get("watchdog") and t["watchdog"] not in VALID_WATCHDOG:
            errors.append(f"{prefix} watchdog 无效: {t['watchdog']}")

        # 周期任务额外要求
        if t.get("lifecycle") == "periodic":
            if not t.get("period_ms"):
                errors.append(f"{prefix} 周期任务缺少 period_ms")
            if not t.get("deadline_ms") and strict:
                errors.append(f"{prefix} 周期任务缺少 deadline_ms")
            if not t.get("wcet_ms") and strict:
                warnings.append(f"{prefix} 周期任务缺少 wcet_ms")

        # 栈大小检查
        if t.get("stack_bytes") and t["stack_bytes"] < 512:
            violations.append(f"{prefix} stack_bytes < 512 ({t['stack_bytes']})")

    # ── Queues ──
    queues = manifest.get("queues", [])
    queue_names = set()
    for i, q in enumerate(queues):
        prefix = f"queues[{i}]({q.get('name', '?')})"

        for f in ["name", "depth", "item_type", "item_size", "producer_tasks", "consumer_tasks",
                   "send_timeout_ms", "recv_timeout_ms", "full_policy", "drop_counter"]:
            if not q.get(f) and q.get(f) != 0:
                errors.append(f"{prefix} 缺少 {f}")

        queue_names.add(q.get("name", ""))

        # 枚举值
        if q.get("full_policy") and q["full_policy"] not in VALID_FULL_POLICY:
            errors.append(f"{prefix} full_policy 无效: {q['full_policy']}")

        # 消费者检查
        if not q.get("consumer_tasks"):
            errors.append(f"{prefix} 缺少 consumer_tasks")

        # 生产者检查
        if not q.get("producer_tasks"):
            errors.append(f"{prefix} 缺少 producer_tasks")

        # 超时检查
        if q.get("send_timeout_ms") and q["send_timeout_ms"] > 10000:
            warnings.append(f"{prefix} send_timeout_ms > 10s ({q['send_timeout_ms']})")

    # ── Locks ──
    locks = manifest.get("locks", [])
    for i, l in enumerate(locks):
        prefix = f"locks[{i}]({l.get('name', '?')})"

        for f in ["name", "type", "holder_tasks", "lock_order"]:
            if not l.get(f) and l.get(f) != 0 and l.get(f) is not False:
                errors.append(f"{prefix} 缺少 {f}")
        # max_hold_ms 必须 > 0
        if not l.get("max_hold_ms") or l["max_hold_ms"] <= 0:
            errors.append(f"{prefix} 缺少 max_hold_ms (必须 > 0)")
        # priority_inheritance 必须显式设置
        if l.get("priority_inheritance") is None:
            errors.append(f"{prefix} 缺少 priority_inheritance")

        if l.get("type") and l["type"] not in VALID_LOCK_TYPE:
            errors.append(f"{prefix} type 无效: {l['type']}")

        if l.get("max_hold_ms") and l["max_hold_ms"] > 100:
            violations.append(f"{prefix} max_hold_ms > 100ms ({l['max_hold_ms']})")

    # ── Timers ──
    timers = manifest.get("timers", [])
    for i, t in enumerate(timers):
        prefix = f"timers[{i}]({t.get('name', '?')})"

        for f in ["name", "period_ms", "auto_reload", "callback_max_ms", "callback_policy"]:
            if not t.get(f) and t.get(f) != 0 and t.get(f) is not False:
                errors.append(f"{prefix} 缺少 {f}")
        if t.get("notifies_tasks") is None:
            errors.append(f"{prefix} 缺少 notifies_tasks")

        if t.get("callback_policy") and t["callback_policy"] not in VALID_CALLBACK_POLICY:
            errors.append(f"{prefix} callback_policy 无效: {t['callback_policy']}")

        if t.get("callback_max_ms") and t.get("period_ms") and t["callback_max_ms"] > t["period_ms"]:
            errors.append(f"{prefix} callback_max_ms > period_ms")

    # ── Memory Pools ──
    pools = manifest.get("memory_pools", [])
    for i, p in enumerate(pools):
        prefix = f"memory_pools[{i}]({p.get('name', '?')})"

        for f in ["name", "block_size", "num_blocks", "owner_tasks", "full_policy", "runtime_expand_allowed"]:
            if not p.get(f) and p.get(f) != 0 and p.get(f) is not False:
                errors.append(f"{prefix} 缺少 {f}")

        if p.get("runtime_expand_allowed") and strict:
            violations.append(f"{prefix} runtime_expand_allowed=true 需显式例外")

    # ── Cross-reference 检查 ──
    if strict:
        # task 的 produces/consumes 引用的 queue 必须存在
        for t in tasks:
            for qname in t.get("produces", []) + t.get("consumes", []):
                if qname and qname not in queue_names:
                    errors.append(f"task {t.get('name')} 引用不存在的 queue: {qname}")

        # queue 的 producer/consumer 引用的 task 必须存在（允许 "external" 表示外部输入）
        for q in queues:
            for tname in q.get("producer_tasks", []) + q.get("consumer_tasks", []):
                if tname and tname not in task_names and tname != "external":
                    errors.append(f"queue {q.get('name')} 引用不存在的 task: {tname}")

        # lock 的 holder_tasks 引用的 task 必须存在
        for l in locks:
            for tname in l.get("holder_tasks", []):
                if tname and tname not in task_names:
                    errors.append(f"lock {l.get('name')} 引用不存在的 task: {tname}")

    # ── Constraints ──
    constraints = manifest.get("constraints", {})
    c29_covered = any(str(c).startswith("C29") for c in constraints.get("covered", []))
    if strict and c29_covered:
        for f in [
            "module_responsibility",
            "public_api",
            "dependencies",
            "forbidden_dependencies",
            "events_in",
            "events_out",
            "owned_resources",
        ]:
            if f not in manifest:
                errors.append(f"C29 module boundary missing field: {f}")

    if strict:
        # deferred 必须有 reason 和 evidence
        for d in constraints.get("deferred", []):
            if not d.get("reason"):
                errors.append(f"deferred 约束 {d.get('id')} 缺少 reason")
            if not d.get("evidence"):
                errors.append(f"deferred 约束 {d.get('id')} 缺少 evidence")

        # evidence 必须有 constraint_id 和 detail
        for e in constraints.get("evidence", []):
            if not e.get("constraint_id"):
                errors.append(f"evidence 缺少 constraint_id")
            if not e.get("detail"):
                errors.append(f"evidence 缺少 detail")
            if e.get("evidence_type") and e["evidence_type"] not in VALID_EVIDENCE_TYPE:
                errors.append(f"evidence_type 无效: {e['evidence_type']}")

    passed = len(errors) == 0 and len(violations) == 0

    return {
        "passed": passed,
        "errors": errors,
        "warnings": warnings,
        "violations": violations,
        "contract_summary": {
            "tasks": len(tasks),
            "queues": len(queues),
            "locks": len(locks),
            "timers": len(timers),
            "memory_pools": len(pools),
            "constraints_required": len(constraints.get("required", [])),
            "constraints_covered": len(constraints.get("covered", [])),
            "constraints_deferred": len(constraints.get("deferred", [])),
        },
    }


def _result(passed: bool, errors: list, warnings: list, violations: list) -> dict:
    return {
        "passed": passed,
        "errors": errors,
        "warnings": warnings,
        "violations": violations,
        "contract_summary": {},
    }


def run_self_test() -> int:
    passed = 0
    failed = 0

    # 1. 合法 manifest
    good = {
        "schema_version": "1.2", "generator": "test", "platform": "esp32",
        "generated_files": [{"path": "main.c"}],
        "tasks": [
            {"name": "t1", "entry": "t1_func", "stack_bytes": 2048, "priority": 5,
             "lifecycle": "long_running", "exit_policy": "stop_token", "watchdog": "feed",
             "produces": ["q1"], "consumes": [], "holds": []},
            {"name": "t2", "entry": "t2_func", "stack_bytes": 2048, "priority": 4,
             "lifecycle": "long_running", "exit_policy": "stop_token", "watchdog": "feed",
             "produces": [], "consumes": ["q1"], "holds": []},
        ],
        "queues": [{"name": "q1", "depth": 8, "item_type": "int", "item_size": 4,
                    "producer_tasks": ["t1"], "consumer_tasks": ["t2"],
                    "send_timeout_ms": 50, "recv_timeout_ms": 50,
                    "full_policy": "drop_oldest", "drop_counter": "s_drop"}],
        "locks": [{"name": "m1", "type": "mutex", "holder_tasks": ["t1"],
                   "max_hold_ms": 50, "lock_order": 1, "priority_inheritance": True}],
        "timers": [{"name": "tmr1", "period_ms": 1000, "auto_reload": True,
                    "callback_max_ms": 5, "notifies_tasks": [], "callback_policy": "deferred"}],
        "memory_pools": [{"name": "pool1", "block_size": 256, "num_blocks": 4,
                          "owner_tasks": ["t1"], "full_policy": "block", "runtime_expand_allowed": False}],
        "constraints": {"required": ["C8"], "covered": ["C8"]},
    }
    r = validate(good, strict=True)
    assert r["passed"] is True, f"Expected pass, got {r['errors']}"
    print("[PASS] valid manifest → pass")
    passed += 1

    # 2. 缺 lifecycle
    bad = {**good, "tasks": [{**good["tasks"][0], "lifecycle": ""}]}
    r = validate(bad)
    assert r["passed"] is False
    assert any("lifecycle" in e for e in r["errors"])
    print("[PASS] missing lifecycle → fail")
    passed += 1

    # 3. queue 缺 consumer
    bad = {**good, "queues": [{**good["queues"][0], "consumer_tasks": []}]}
    r = validate(bad)
    assert r["passed"] is False
    assert any("consumer" in e for e in r["errors"])
    print("[PASS] queue no consumer → fail")
    passed += 1

    # 4. queue 缺 full_policy
    bad = {**good, "queues": [{**good["queues"][0], "full_policy": ""}]}
    r = validate(bad)
    assert r["passed"] is False
    assert any("full_policy" in e for e in r["errors"])
    print("[PASS] queue no full_policy → fail")
    passed += 1

    # 5. periodic task 缺 deadline
    bad = {**good, "tasks": [{**good["tasks"][0], "lifecycle": "periodic", "period_ms": 100, "deadline_ms": 0}]}
    r = validate(bad, strict=True)
    assert r["passed"] is False
    assert any("deadline" in e for e in r["errors"])
    print("[PASS] periodic task no deadline → fail")
    passed += 1

    # 6. lock 缺 max_hold_ms
    bad = {**good, "locks": [{**good["locks"][0], "max_hold_ms": 0}]}
    r = validate(bad)
    assert r["passed"] is False
    assert any("max_hold_ms" in e for e in r["errors"])
    print("[PASS] lock no max_hold_ms → fail")
    passed += 1

    # 7. timer callback > period
    bad = {**good, "timers": [{**good["timers"][0], "callback_max_ms": 2000}]}
    r = validate(bad)
    assert r["passed"] is False
    assert any("callback_max_ms" in e for e in r["errors"])
    print("[PASS] timer callback > period → fail")
    passed += 1

    # 8. cross-reference: task 引用不存在的 queue
    bad_task = {**good["tasks"][0], "produces": ["nonexistent_q"]}
    bad = {**good, "tasks": [bad_task, good["tasks"][1]]}
    r = validate(bad, strict=True)
    assert r["passed"] is False
    assert any("nonexistent_q" in e for e in r["errors"])
    print("[PASS] task references missing queue → fail")
    passed += 1

    print(f"\nSelf-test: {passed} passed, {failed} failed")
    return 1 if failed > 0 else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Manifest Contract Validator v20.0.1")
    parser.add_argument("--manifest", help="manifest JSON 路径")
    parser.add_argument("--strict", action="store_true", help="严格模式")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    if not args.manifest:
        parser.print_help()
        return 1

    data = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    r = validate(data, strict=args.strict)

    if args.json:
        print(json.dumps(r, indent=2, ensure_ascii=False))
    else:
        if r["passed"]:
            print("[PASS] Manifest contract: PASS")
        else:
            print("[FAIL] Manifest contract: FAIL")
            for e in r["errors"]:
                print(f"  - {e}")
        if r["warnings"]:
            print("Warnings:")
            for w in r["warnings"]:
                print(f"  - {w}")

    return 0 if r["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
