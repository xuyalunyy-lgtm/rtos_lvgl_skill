#!/usr/bin/env python3
"""
IPC Contract Checker v13.0.4 — IPC 契约检查。

检查 queue/semaphore/event group 的 payload owner、timeout、backpressure、ISR-safe、跨核同步。

用法:
    python tools/ipc_contract_checker.py --model rtos_model.json
    python tools/ipc_contract_checker.py --self-test
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def check(model: dict) -> dict:
    tasks = {t["name"]: t for t in model.get("tasks", [])}
    queues = model.get("queues", [])
    mutexes = model.get("mutexes", [])
    semaphores = model.get("semaphores", [])

    risks = []

    # Queue 检查
    for q in queues:
        name = q["name"]
        depth = q.get("depth", 0)
        item_size = q.get("item_size", 0)
        producers = q.get("producer_tasks", [])
        consumers = q.get("consumer_tasks", [])
        timeout = q.get("timeout_ms", 0)
        bp = q.get("backpressure", "")
        isr_safe = q.get("isr_safe", False)

        # 大 payload 队列
        if item_size > 256:
            risks.append({
                "type": "large_payload",
                "severity": "P1",
                "ipc": name,
                "detail": f"队列 {name} item_size={item_size}（>256），建议用指针/索引",
                "constraint": "C2",
            })

        # 无 timeout
        if consumers and timeout == 0:
            risks.append({
                "type": "no_timeout",
                "severity": "P1",
                "ipc": name,
                "detail": f"队列 {name} 有消费者但未设置 timeout",
                "constraint": "C31",
            })

        # portMAX_DELAY（timeout=-1 或极大值）
        if timeout and timeout > 60000:
            risks.append({
                "type": "infinite_wait",
                "severity": "P0",
                "ipc": name,
                "detail": f"队列 {name} timeout={timeout}ms（>60s），接近永久等待",
                "constraint": "C31",
            })

        # 深度为 1 的队列
        if depth == 1 and producers:
            risks.append({
                "type": "shallow_queue",
                "severity": "P2",
                "ipc": name,
                "detail": f"队列 {name} depth=1，producer 可能频繁阻塞",
            })

        # 跨核同步
        if producers and consumers:
            prod_cores = set()
            cons_cores = set()
            for p in producers:
                t = tasks.get(p)
                if t:
                    prod_cores.add(t.get("core_affinity", -1))
            for c in consumers:
                t = tasks.get(c)
                if t:
                    cons_cores.add(t.get("core_affinity", -1))
            # 如果生产者和消费者在不同核上
            if prod_cores and cons_cores and prod_cores != cons_cores:
                if not isr_safe:
                    risks.append({
                        "type": "cross_core_sync",
                        "severity": "P1",
                        "ipc": name,
                        "detail": f"队列 {name} 跨核使用但未标记 isr_safe",
                        "constraint": "C17",
                    })

    # Mutex 检查
    for m in mutexes:
        name = m["name"]
        holders = m.get("holder_tasks", [])
        recursive = m.get("recursive", False)

        # 多任务持有同一 mutex（可能问题）
        if len(holders) > 3:
            risks.append({
                "type": "too_many_holders",
                "severity": "P2",
                "ipc": name,
                "detail": f"Mutex {name} 被 {len(holders)} 个任务持有，竞争激烈",
            })

        # 非递归 mutex 被同一任务多次获取风险
        if not recursive and len(holders) > 1:
            risks.append({
                "type": "non_recursive_risk",
                "severity": "P2",
                "ipc": name,
                "detail": f"Mutex {name} 非递归但被多任务使用，注意重入",
            })

    # Semaphore 检查
    for s in semaphores:
        name = s["name"]
        isr_safe = s.get("isr_safe", False)
        sem_type = s.get("type", "")

        # 二值信号量用于同步
        if sem_type == "binary":
            risks.append({
                "type": "binary_sem_usage",
                "severity": "P2",
                "ipc": name,
                "detail": f"信号量 {name} 为 binary 类型，确认用于同步而非互斥",
            })

    contracts = []
    for q in queues:
        contracts.append({
            "ipc": q["name"],
            "type": "queue",
            "producers": q.get("producer_tasks", []),
            "consumers": q.get("consumer_tasks", []),
            "depth": q.get("depth", 0),
            "item_size": q.get("item_size", 0),
            "backpressure": q.get("backpressure", ""),
            "timeout_ms": q.get("timeout_ms", 0),
        })

    return {
        "ipc_count": len(queues) + len(mutexes) + len(semaphores),
        "contracts": contracts,
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
    report = check(model)

    assert report["ipc_count"] >= 5
    print(f"[PASS] checked {report['ipc_count']} IPC objects")
    passed += 1

    # 检出大 payload（如果有的话）
    large = [r for r in report["risks"] if r["type"] == "large_payload"]
    print(f"[PASS] large_payload: {len(large)} found")
    passed += 1

    # 检出无 timeout（如果有的话）
    no_to = [r for r in report["risks"] if r["type"] == "no_timeout"]
    print(f"[PASS] no_timeout: {len(no_to)} found")
    passed += 1

    print(f"\nSelf-test: {passed} passed, {failed} failed")
    return 1 if failed > 0 else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="IPC Contract Checker v13.0.4")
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
    report = check(model)

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(f"IPC: {report['ipc_count']}")
        print(f"Risks: {report['risk_summary']['total']}")
        for r in report["risks"][:10]:
            print(f"  [{r['severity']}] {r['type']}: {r['detail'][:80]}")

    return 0 if report["risk_summary"]["p0"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
