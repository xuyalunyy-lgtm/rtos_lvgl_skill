#!/usr/bin/env python3
"""
RTOS Simulator v13.0.7 — What-if 轻量模拟。

基于 system model 做 what-if：任务周期变化、queue 深度变化、优先级调整、锁持有时间变化。
输出推荐调整，不直接改代码。

用法:
    python tools/rtos_sim.py --model rtos_model.json
    python tools/rtos_sim.py --model rtos_model.json --what-if priority_change.json
    python tools/rtos_sim.py --self-test
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def simulate(model: dict, what_if: dict | None = None) -> dict:
    """基于模型做 what-if 模拟。"""
    tasks = list(model.get("tasks", []))
    queues = list(model.get("queues", []))
    mutexes = list(model.get("mutexes", []))
    recommendations = []

    # 应用 what-if 修改
    if what_if:
        for mod in what_if.get("task_priority_changes", []):
            for t in tasks:
                if t["name"] == mod["task"]:
                    old = t["priority"]
                    t["priority"] = mod["new_priority"]
                    recommendations.append({
                        "type": "applied_change",
                        "detail": f"任务 {mod['task']} 优先级 {old} → {mod['new_priority']}",
                    })

        for mod in what_if.get("queue_depth_changes", []):
            for q in queues:
                if q["name"] == mod["queue"]:
                    old = q["depth"]
                    q["depth"] = mod["new_depth"]
                    recommendations.append({
                        "type": "applied_change",
                        "detail": f"队列 {mod['queue']} 深度 {old} → {mod['new_depth']}",
                    })

        for mod in what_if.get("task_period_changes", []):
            for t in tasks:
                if t["name"] == mod["task"]:
                    old = t.get("period_ms", 0)
                    t["period_ms"] = mod["new_period_ms"]
                    recommendations.append({
                        "type": "applied_change",
                        "detail": f"任务 {mod['task']} 周期 {old}ms → {mod['new_period_ms']}ms",
                    })

    # 分析 CPU 利用率
    total_utilization = 0.0
    task_utils = []
    for t in tasks:
        period = t.get("period_ms", 0)
        wcet = t.get("wcet_ms", 0)
        if period > 0 and wcet > 0:
            util = wcet / period
            task_utils.append({"task": t["name"], "utilization": round(util, 3), "priority": t["priority"]})
            total_utilization += util

    # 多核分析
    core_utils = {}
    for t in tasks:
        core = t.get("core_affinity", -1)
        period = t.get("period_ms", 0)
        wcet = t.get("wcet_ms", 0)
        if core >= 0 and period > 0 and wcet > 0:
            core_utils.setdefault(core, 0.0)
            core_utils[core] += wcet / period

    # 队列溢出风险
    for q in queues:
        producers = q.get("producer_tasks", [])
        consumers = q.get("consumer_tasks", [])
        depth = q.get("depth", 0)
        if producers and consumers:
            prod_util = 0
            cons_util = 0
            for p_name in producers:
                for t in tasks:
                    if t["name"] == p_name and t.get("period_ms", 0) > 0:
                        prod_util += 1000 / t["period_ms"]
            for c_name in consumers:
                for t in tasks:
                    if t["name"] == c_name and t.get("period_ms", 0) > 0:
                        cons_util += 1000 / t["period_ms"]
            if prod_util > 0 and cons_util > 0 and prod_util > cons_util * 1.5:
                recommendations.append({
                    "type": "queue_overflow_risk",
                    "queue": q["name"],
                    "detail": f"队列 {q['name']} 生产速率({prod_util:.1f}/s) > 消费速率({cons_util:.1f}/s)，建议增加深度或优化消费",
                })

    # CPU 利用率告警
    if total_utilization > 0.7:
        recommendations.append({
            "type": "high_cpu_utilization",
            "detail": f"总 CPU 利用率 {total_utilization:.0%}（>70%），可能影响实时性",
        })

    # 优先级建议
    sorted_tasks = sorted(task_utils, key=lambda t: -t["utilization"])
    if len(sorted_tasks) >= 2:
        high_util = sorted_tasks[0]
        if high_util["utilization"] > 0.3 and high_util["priority"] < 5:
            recommendations.append({
                "type": "priority_suggestion",
                "task": high_util["task"],
                "detail": f"任务 {high_util['task']} 利用率 {high_util['utilization']:.0%} 但优先级仅 {high_util['priority']}，建议提升",
            })

    return {
        "total_cpu_utilization": round(total_utilization, 3),
        "core_utilization": {str(k): round(v, 3) for k, v in core_utils.items()},
        "task_utilizations": sorted_tasks,
        "recommendations": recommendations,
        "what_if_applied": what_if is not None,
    }


def run_self_test() -> int:
    passed = 0
    failed = 0

    from rtos_model import generate_fixture_model
    model = generate_fixture_model()

    # 1. 基本模拟
    result = simulate(model)
    assert "total_cpu_utilization" in result
    assert "recommendations" in result
    print(f"[PASS] simulation: cpu={result['total_cpu_utilization']:.0%}, {len(result['recommendations'])} recs")
    passed += 1

    # 2. What-if 优先级变化
    what_if = {"task_priority_changes": [{"task": "audio_task", "new_priority": 8}]}
    result2 = simulate(model, what_if)
    assert result2["what_if_applied"] is True
    assert any("audio_task" in r.get("detail", "") for r in result2["recommendations"])
    print("[PASS] what-if priority change")
    passed += 1

    # 3. What-if queue 深度变化
    what_if2 = {"queue_depth_changes": [{"queue": "audio_frame_q", "new_depth": 16}]}
    result3 = simulate(model, what_if2)
    assert any("audio_frame_q" in r.get("detail", "") for r in result3["recommendations"])
    print("[PASS] what-if queue depth change")
    passed += 1

    print(f"\nSelf-test: {passed} passed, {failed} failed")
    return 1 if failed > 0 else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="RTOS Simulator v13.0.7")
    parser.add_argument("--model")
    parser.add_argument("--what-if", help="What-if 修改 JSON")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    if not args.model:
        parser.print_help()
        return 1

    model = json.loads(Path(args.model).read_text(encoding="utf-8"))
    what_if = json.loads(Path(args.what_if).read_text(encoding="utf-8")) if args.what_if else None

    result = simulate(model, what_if)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"CPU: {result['total_cpu_utilization']:.0%}")
        if result["core_utilization"]:
            print(f"Cores: {result['core_utilization']}")
        print(f"Recommendations: {len(result['recommendations'])}")
        for r in result["recommendations"]:
            print(f"  {r['type']}: {r['detail'][:80]}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
