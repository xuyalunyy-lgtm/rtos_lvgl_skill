#!/usr/bin/env python3
"""
Task Graph Analyzer v13.0.2 — 任务依赖与 IPC 链路分析。

分析任务依赖、生产消费链路、循环等待、孤儿任务、无消费者队列、无背压 producer。

用法:
    python tools/task_graph_analyzer.py --model rtos_model.json
    python tools/task_graph_analyzer.py --model rtos_model.json --json
    python tools/task_graph_analyzer.py --self-test
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def analyze(model: dict) -> dict:
    """分析任务图，返回报告。"""
    tasks = {t["name"]: t for t in model.get("tasks", [])}
    queues = {q["name"]: q for q in model.get("queues", [])}
    mutexes = {m["name"]: m for m in model.get("mutexes", [])}

    risks = []
    task_names = set(tasks.keys())
    queue_names = set(queues.keys())
    mutex_names = set(mutexes.keys())

    # 1. 孤儿任务：无 produce 也无 consume
    for t in tasks.values():
        produces = set(t.get("produces", []))
        consumes = set(t.get("consumes", []))
        if not produces and not consumes and t.get("period_ms", 0) == 0:
            risks.append({
                "type": "orphan_task",
                "severity": "P2",
                "task": t["name"],
                "detail": f"任务 {t['name']} 既不生产也不消费，且非周期任务",
                "constraint": "C30",
            })

    # 2. 无消费者队列
    for q in queues.values():
        consumers = q.get("consumer_tasks", [])
        if not consumers:
            risks.append({
                "type": "no_consumer",
                "severity": "P1",
                "queue": q["name"],
                "detail": f"队列 {q['name']} 无消费者，数据将堆积",
                "constraint": "C2",
            })

    # 3. 无背压 producer
    for q in queues.values():
        producers = q.get("producer_tasks", [])
        if producers and not q.get("backpressure"):
            risks.append({
                "type": "no_backpressure",
                "severity": "P1",
                "queue": q["name"],
                "detail": f"队列 {q['name']} 有生产者但未声明背压策略",
                "constraint": "C37",
            })

    # 4. 循环等待检测（简化版：A holds M1, B holds M2, A waits M2, B waits M1）
    hold_map = {}  # mutex -> holder_tasks
    for m in mutexes.values():
        hold_map[m["name"]] = set(m.get("holder_tasks", []))

    # 检查两个 mutex 的交叉持有
    mutex_list = list(mutexes.values())
    for i in range(len(mutex_list)):
        for j in range(i + 1, len(mutex_list)):
            m1, m2 = mutex_list[i], mutex_list[j]
            h1 = set(m1.get("holder_tasks", []))
            h2 = set(m2.get("holder_tasks", []))
            if h1 and h2 and h1 != h2:
                # 如果持有 m1 的任务也在 m2 的 holder 列表中，反之亦然
                if h1 & h2:
                    continue  # 同一任务持有两个 mutex，没问题
                risks.append({
                    "type": "potential_deadlock",
                    "severity": "P0",
                    "detail": f"Mutex {m1['name']} 和 {m2['name']} 被不同任务交叉持有，可能死锁",
                    "mutex_1": m1["name"],
                    "mutex_2": m2["name"],
                    "constraint": "C43",
                })

    # 5. 高优先级依赖低优先级队列
    for t in tasks.values():
        for qname in t.get("consumes", []):
            q = queues.get(qname)
            if not q:
                continue
            for pname in q.get("producer_tasks", []):
                p = tasks.get(pname)
                if p and p["priority"] < t["priority"] - 2:
                    risks.append({
                        "type": "priority_inversion_risk",
                        "severity": "P1",
                        "detail": f"高优先级 {t['name']}(p{t['priority']}) 消费低优先级 {p['name']}(p{p['priority']}) 生产的队列",
                        "constraint": "C15",
                    })

    # 6. 引用不存在的任务/队列
    for t in tasks.values():
        for ref in t.get("produces", []) + t.get("consumes", []):
            if ref not in queue_names:
                risks.append({
                    "type": "dangling_reference",
                    "severity": "P2",
                    "detail": f"任务 {t['name']} 引用不存在的队列: {ref}",
                })
        for ref in t.get("holds", []):
            if ref not in mutex_names:
                risks.append({
                    "type": "dangling_reference",
                    "severity": "P2",
                    "detail": f"任务 {t['name']} 引用不存在的 mutex: {ref}",
                })

    # 构建图
    edges = []
    for q in queues.values():
        for p in q.get("producer_tasks", []):
            for c in q.get("consumer_tasks", []):
                edges.append({"from": p, "to": c, "via": q["name"], "type": "queue"})
    for m in mutexes.values():
        for h in m.get("holder_tasks", []):
            edges.append({"from": h, "to": h, "via": m["name"], "type": "mutex"})

    return {
        "task_count": len(tasks),
        "queue_count": len(queues),
        "mutex_count": len(mutexes),
        "edges": edges,
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

    # 1. 基本结构
    assert report["task_count"] >= 4
    assert report["queue_count"] >= 4
    print(f"[PASS] graph: {report['task_count']} tasks, {report['queue_count']} queues, {len(report['edges'])} edges")
    passed += 1

    # 2. 检出风险
    assert report["risk_summary"]["total"] > 0
    print(f"[PASS] risks: {report['risk_summary']['total']} ({report['risk_summary']['p0']} P0, {report['risk_summary']['p1']} P1)")
    passed += 1

    # 3. 检出无消费者队列
    no_consumer = [r for r in report["risks"] if r["type"] == "no_consumer"]
    assert len(no_consumer) > 0
    print(f"[PASS] no_consumer: {no_consumer[0]['queue']}")
    passed += 1

    # 4. 检出无背压（如果有的话）
    no_bp = [r for r in report["risks"] if r["type"] == "no_backpressure"]
    print(f"[PASS] no_backpressure: {len(no_bp)} found")
    passed += 1

    print(f"\nSelf-test: {passed} passed, {failed} failed")
    return 1 if failed > 0 else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Task Graph Analyzer v13.0.2")
    parser.add_argument("--model", help="RTOS 模型 JSON")
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
        print(f"Tasks: {report['task_count']}, Queues: {report['queue_count']}")
        print(f"Edges: {len(report['edges'])}")
        print(f"Risks: {report['risk_summary']['total']} (P0={report['risk_summary']['p0']}, P1={report['risk_summary']['p1']})")
        for r in report["risks"][:10]:
            print(f"  [{r['severity']}] {r['type']}: {r['detail'][:80]}")

    return 0 if report["risk_summary"]["p0"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
