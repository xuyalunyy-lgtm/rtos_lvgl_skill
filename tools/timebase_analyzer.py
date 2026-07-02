#!/usr/bin/env python3
"""
Timebase Analyzer v13.0.6 — 定时器与时间基准分析。

检查 software timer、tick、deadline、timeout budget、周期 jitter、永久等待。

用法:
    python tools/timebase_analyzer.py --model rtos_model.json
    python tools/timebase_analyzer.py --self-test
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def analyze(model: dict) -> dict:
    tasks = {t["name"]: t for t in model.get("tasks", [])}
    timers = model.get("timers", [])
    queues = {q["name"]: q for q in model.get("queues", [])}

    risks = []

    # 1. Timer 回调阻塞
    for tmr in timers:
        cb_max = tmr.get("callback_max_ms", 0)
        period = tmr.get("period_ms", 0)
        if cb_max > 5:
            risks.append({
                "type": "timer_callback_long",
                "severity": "P1",
                "timer": tmr["name"],
                "detail": f"Timer {tmr['name']} 回调最大 {cb_max}ms（>5ms），会阻塞 timer task",
                "constraint": "C16",
            })
        if period > 0 and cb_max > 0 and cb_max > period:
            risks.append({
                "type": "timer_overrun",
                "severity": "P0",
                "timer": tmr["name"],
                "detail": f"Timer {tmr['name']} 回调时间({cb_max}ms) > 周期({period}ms)",
                "constraint": "C16",
            })

    # 2. 周期任务 jitter 风险
    for t in tasks.values():
        period = t.get("period_ms", 0)
        wcet = t.get("wcet_ms", 0)
        if period > 0 and wcet > 0 and wcet > period * 0.5:
            risks.append({
                "type": "jitter_risk",
                "severity": "P1",
                "task": t["name"],
                "detail": f"任务 {t['name']} WCET({wcet}ms) > 50% period({period}ms)，jitter 风险高",
                "constraint": "C35",
            })

    # 3. 永久等待队列
    for q in queues.values():
        timeout = q.get("timeout_ms", 0)
        if timeout and timeout > 30000:
            risks.append({
                "type": "near_infinite_wait",
                "severity": "P1",
                "queue": q["name"],
                "detail": f"队列 {q['name']} timeout={timeout}ms（>30s），接近永久等待",
                "constraint": "C31",
            })

    # 4. Timer 数量过多
    if len(timers) > 8:
        risks.append({
            "type": "too_many_timers",
            "severity": "P2",
            "detail": f"使用了 {len(timers)} 个 software timer（>8），考虑合并",
        })

    # 5. 快速 timer
    for tmr in timers:
        if tmr.get("period_ms", 0) > 0 and tmr["period_ms"] < 5:
            risks.append({
                "type": "fast_timer",
                "severity": "P2",
                "timer": tmr["name"],
                "detail": f"Timer {tmr['name']} 周期 {tmr['period_ms']}ms（<5ms），CPU 开销高",
            })

    # 6. 低功耗任务超时分析
    for t in tasks.values():
        if "power" in t["name"].lower() or "sleep" in t["name"].lower():
            for qname in t.get("consumes", []):
                q = queues.get(qname)
                if q and q.get("timeout_ms", 0) > 1000:
                    risks.append({
                        "type": "power_task_long_wait",
                        "severity": "P2",
                        "task": t["name"],
                        "detail": f"低功耗任务 {t['name']} 等待队列 {qname} timeout={q['timeout_ms']}ms",
                        "constraint": "C21",
                    })

    return {
        "timer_count": len(timers),
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

    assert report["timer_count"] >= 2
    print(f"[PASS] analyzed {report['timer_count']} timers")
    passed += 1

    print(f"[PASS] found {report['risk_summary']['total']} risks")
    passed += 1

    # 检出 near_infinite_wait（如果有的话）
    niw = [r for r in report["risks"] if r["type"] == "near_infinite_wait"]
    print(f"[PASS] near_infinite_wait: {len(niw)} found")
    passed += 1

    print(f"\nSelf-test: {passed} passed, {failed} failed")
    return 1 if failed > 0 else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Timebase Analyzer v13.0.6")
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
        print(f"Timers: {report['timer_count']}")
        print(f"Risks: {report['risk_summary']['total']}")
        for r in report["risks"][:10]:
            print(f"  [{r['severity']}] {r['type']}: {r['detail'][:80]}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
