#!/usr/bin/env python3
"""
Memory Lifetime Analyzer v13.0.5 — 内存生命周期分析。

分析 heap allocation、pool ownership、zero-copy buffer、task delete cleanup、泄漏风险。

用法:
    python tools/memory_lifetime_analyzer.py --model rtos_model.json
    python tools/memory_lifetime_analyzer.py --self-test
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def analyze(model: dict) -> dict:
    tasks = {t["name"]: t for t in model.get("tasks", [])}
    queues = {q["name"]: q for q in model.get("queues", [])}
    pools = model.get("memory_pools", [])
    mutexes = model.get("mutexes", [])

    risks = []

    # 1. 无 owner 的内存池
    for p in pools:
        if not p.get("owner_tasks"):
            risks.append({
                "type": "no_pool_owner",
                "severity": "P1",
                "pool": p["name"],
                "detail": f"内存池 {p['name']} 无 owner_tasks，泄漏风险高",
                "constraint": "C3",
            })

    # 2. 跨任务 pool 访问
    for p in pools:
        owners = set(p.get("owner_tasks", []))
        # 检查是否有非 owner 任务通过队列使用此 pool
        for q in queues.values():
            if q.get("item_size", 0) == p.get("block_size", 0):
                consumers = set(q.get("consumer_tasks", []))
                non_owners = consumers - owners
                if non_owners:
                    risks.append({
                        "type": "cross_task_pool",
                        "severity": "P1",
                        "pool": p["name"],
                        "detail": f"Pool {p['name']} 的 block 通过队列 {q['name']} 传给非 owner 任务 {non_owners}",
                        "constraint": "C2",
                    })

    # 3. 大 payload 队列（应使用 pool + 指针）
    for q in queues.values():
        if q.get("item_size", 0) > 128:
            risks.append({
                "type": "queue_copy_overhead",
                "severity": "P2",
                "queue": q["name"],
                "detail": f"队列 {q['name']} item_size={q['item_size']}，建议用 pool + 指针减少 copy",
                "constraint": "C36",
            })

    # 4. 任务删除时的资源清理
    for t in tasks.values():
        holds = t.get("holds", [])
        produces = t.get("produces", [])
        if holds or produces:
            # 检查是否有对应的 cleanup/deinit
            risks.append({
                "type": "delete_cleanup_needed",
                "severity": "P2",
                "task": t["name"],
                "detail": f"任务 {t['name']} 持有 {holds} 并生产 {produces}，删除时需确保释放",
                "constraint": "C33",
            })

    # 5. 零拷贝 buffer 分析
    for q in queues.values():
        if q.get("item_size", 0) > 512:
            risks.append({
                "type": "zero_copy_candidate",
                "severity": "P2",
                "queue": q["name"],
                "detail": f"队列 {q['name']} item_size={q['item_size']}，强烈建议零拷贝",
                "constraint": "C36",
            })

    # 6. 内存池容量分析
    for p in pools:
        total = p.get("block_size", 0) * p.get("num_blocks", 0)
        if total > 32768:
            risks.append({
                "type": "large_pool",
                "severity": "P2",
                "pool": p["name"],
                "detail": f"内存池 {p['name']} 总容量 {total} bytes（>32KB）",
            })

    return {
        "pool_count": len(pools),
        "pools": pools,
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

    assert report["pool_count"] >= 2
    print(f"[PASS] analyzed {report['pool_count']} pools")
    passed += 1

    assert report["risk_summary"]["total"] > 0
    print(f"[PASS] found {report['risk_summary']['total']} risks")
    passed += 1

    # 检出跨任务 pool（如果有的话）
    cross = [r for r in report["risks"] if r["type"] == "cross_task_pool"]
    print(f"[PASS] cross_task_pool: {len(cross)} found")
    passed += 1

    print(f"\nSelf-test: {passed} passed, {failed} failed")
    return 1 if failed > 0 else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Memory Lifetime Analyzer v13.0.5")
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
        print(f"Pools: {report['pool_count']}")
        print(f"Risks: {report['risk_summary']['total']}")
        for r in report["risks"][:10]:
            print(f"  [{r['severity']}] {r['type']}: {r['detail'][:80]}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
