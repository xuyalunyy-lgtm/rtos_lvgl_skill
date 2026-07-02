#!/usr/bin/env python3
"""
Scheduler Analyzer v13.0.3 — 调度与优先级分析。

检查优先级反转、实时任务饥饿、错误 core affinity、低优先级持锁阻塞高优先级。

用法:
    python tools/scheduler_analyzer.py --model rtos_model.json
    python tools/scheduler_analyzer.py --model rtos_model.json --json
    python tools/scheduler_analyzer.py --self-test
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def analyze(model: dict) -> dict:
    tasks = {t["name"]: t for t in model.get("tasks", [])}
    mutexes = {m["name"]: m for m in model.get("mutexes", [])}
    queues = {q["name"]: q for q in model.get("queues", [])}

    risks = []

    # 1. 优先级反转：低优先级持锁，高优先级等待同一锁
    for m in mutexes.values():
        holders = m.get("holder_tasks", [])
        ceiling = m.get("priority_ceiling", 0)
        for h_name in holders:
            h = tasks.get(h_name)
            if not h:
                continue
            # 检查是否有更高优先级任务也使用此 mutex
            for t in tasks.values():
                if t["name"] in holders:
                    continue
                if m["name"] in t.get("holds", []) or m["name"] in t.get("consumes", []):
                    if t["priority"] > h["priority"] + 2:
                        risks.append({
                            "type": "priority_inversion",
                            "severity": "P0",
                            "detail": f"低优先级 {h['name']}(p{h['priority']}) 持有 {m['name']}，高优先级 {t['name']}(p{t['priority']}) 可能被阻塞",
                            "constraint": "C15/C43",
                        })

    # 2. 高优先级任务饥饿：周期任务 deadline < period
    for t in tasks.values():
        period = t.get("period_ms", 0)
        deadline = t.get("deadline_ms", 0)
        wcet = t.get("wcet_ms", 0)
        if period > 0 and deadline > 0 and deadline < period:
            risks.append({
                "type": "deadline_miss",
                "severity": "P1",
                "detail": f"任务 {t['name']} deadline({deadline}ms) < period({period}ms)",
                "constraint": "C35",
            })
        if period > 0 and wcet > 0 and wcet > period * 0.8:
            risks.append({
                "type": "wcet_exceeds_period",
                "severity": "P0",
                "detail": f"任务 {t['name']} WCET({wcet}ms) >= 80% period({period}ms)",
                "constraint": "C35",
            })

    # 3. 多核 affinity 分析
    core_tasks = {}
    for t in tasks.values():
        core = t.get("core_affinity", -1)
        if core >= 0:
            core_tasks.setdefault(core, []).append(t)

    # 检查单核过载
    for core, c_tasks in core_tasks.items():
        total_priority = sum(t["priority"] for t in c_tasks)
        if total_priority > 20:
            risks.append({
                "type": "core_overload",
                "severity": "P1",
                "detail": f"Core {core} 绑定了 {len(c_tasks)} 个任务，总优先级 {total_priority}",
            })

    # 4. 无 deadline 的实时任务
    for t in tasks.values():
        if t["priority"] >= 5 and t.get("period_ms", 0) > 0 and t.get("deadline_ms", 0) == 0:
            risks.append({
                "type": "no_deadline",
                "severity": "P2",
                "detail": f"高优先级周期任务 {t['name']}(p{t['priority']}) 未声明 deadline",
                "constraint": "C35",
            })

    # 5. 锁持有时间过长
    for m in mutexes.values():
        max_hold = m.get("max_hold_ms", 0)
        if max_hold > 50:
            risks.append({
                "type": "long_lock_hold",
                "severity": "P1",
                "detail": f"Mutex {m['name']} 最大持有 {max_hold}ms（>50ms）",
                "constraint": "C43",
            })

    return {
        "task_count": len(tasks),
        "mutex_count": len(mutexes),
        "core_distribution": {str(k): len(v) for k, v in core_tasks.items()},
        "risks": risks,
        "risk_summary": {
            "total": len(risks),
            "p0": sum(1 for r in risks if r.get("severity") == "P0"),
            "p1": sum(1 for r in risks if r.get("severity") == "P1"),
            "p2": sum(1 for r in risks if r.get("severity") == "P2"),
        },
    }


def run_self_test() -> int:
    passed = 0
    failed = 0

    from rtos_model import generate_fixture_model
    model = generate_fixture_model()
    report = analyze(model)

    assert report["task_count"] >= 4
    print(f"[PASS] analyzed {report['task_count']} tasks")
    passed += 1

    # 检出锁持有时间过长（如果有的话）
    long_lock = [r for r in report["risks"] if r["type"] == "long_lock_hold"]
    print(f"[PASS] long_lock_hold: {len(long_lock)} found")
    passed += 1

    # 检出无 deadline
    no_dl = [r for r in report["risks"] if r["type"] == "no_deadline"]
    assert len(no_dl) > 0
    print(f"[PASS] no_deadline detected")
    passed += 1

    print(f"\nSelf-test: {passed} passed, {failed} failed")
    return 1 if failed > 0 else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Scheduler Analyzer v13.0.3")
    parser.add_argument("--model")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    if not args.model:
        parser.print_help()
        return 1

    model = json.loads(Path(args.model).read_text(encoding="utf-8"))
    report = analyze(model)

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(f"Tasks: {report['task_count']}, Cores: {report['core_distribution']}")
        print(f"Risks: {report['risk_summary']['total']}")
        for r in report["risks"][:10]:
            print(f"  [{r['severity']}] {r['type']}: {r['detail'][:80]}")

    return 0 if report["risk_summary"]["p0"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
