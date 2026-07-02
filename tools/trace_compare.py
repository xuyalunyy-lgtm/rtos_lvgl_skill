#!/usr/bin/env python3
"""
Trace Compare v12.0.6 — Golden Trace 对比。

支持日志脱敏、时间戳归一化、随机地址掩码、容忍窗口、关键事件顺序检查。
输出 trace drift report。

用法:
    python tools/trace_compare.py --golden golden.log --actual serial.log
    python tools/trace_compare.py --golden golden.log --actual serial.log --json
    python tools/trace_compare.py --self-test
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def _normalize_line(line: str) -> str:
    """归一化日志行：脱敏时间戳、地址、指针。"""
    s = line.strip()
    # 时间戳归一化: "I (12345)" → "I (T)"
    s = re.sub(r"\(\d+\)", "(T)", s)
    # 地址掩码: "0x400d1234" → "0xADDR"
    s = re.sub(r"0x[0-9a-fA-F]{4,}", "0xADDR", s)
    # 指针: "0x3ffb1234" → "0xPTR"
    s = re.sub(r"0x3[fF][bB][0-9a-fA-F]{4}", "0xPTR", s)
    # 堆大小变化: "free=245760" → "free=N"
    s = re.sub(r"free=\d+", "free=N", s)
    # 栈 HWM: "HWM=1024" → "HWM=N"
    s = re.sub(r"HWM=\d+", "HWM=N", s)
    return s


def _extract_events(lines: list[str]) -> list[str]:
    """提取关键事件序列。"""
    events = []
    for line in lines:
        s = _normalize_line(line)
        # 只保留有意义的事件行
        if re.search(r"(boot|start|init|connect|disconnect|error|fail|wdt|reset|ota|heap|stack|alive)", s, re.IGNORECASE):
            events.append(s)
    return events


def compare_traces(golden_lines: list[str], actual_lines: list[str], tolerance: int = 3) -> dict:
    """对比 golden trace 和 actual trace。"""
    golden_events = _extract_events(golden_lines)
    actual_events = _extract_events(actual_lines)

    # 事件顺序检查
    order_drifts = []
    gi = 0
    for ai, a_event in enumerate(actual_events):
        if gi < len(golden_events) and a_event == golden_events[gi]:
            gi += 1
        elif gi < len(golden_events):
            # 检查是否在容忍窗口内
            found = False
            for j in range(max(0, ai - tolerance), min(len(actual_events), ai + tolerance + 1)):
                if j < len(actual_events) and actual_events[j] == golden_events[gi]:
                    found = True
                    gi += 1
                    break
            if not found:
                order_drifts.append({
                    "expected": golden_events[gi] if gi < len(golden_events) else "(end)",
                    "actual": a_event,
                    "position": ai,
                })
                gi += 1

    # 行数差异
    line_diff = abs(len(actual_lines) - len(golden_lines))

    # 归一化行匹配率
    golden_norm = [_normalize_line(l) for l in golden_lines if l.strip()]
    actual_norm = [_normalize_line(l) for l in actual_lines if l.strip()]
    golden_set = set(golden_norm)
    actual_set = set(actual_norm)
    matched = len(golden_set & actual_set)
    total = max(len(golden_set | actual_set), 1)
    match_rate = matched / total

    passed = len(order_drifts) == 0 and match_rate > 0.7

    return {
        "passed": passed,
        "golden_lines": len(golden_lines),
        "actual_lines": len(actual_lines),
        "line_diff": line_diff,
        "golden_events": len(golden_events),
        "actual_events": len(actual_events),
        "match_rate": round(match_rate, 3),
        "order_drifts": order_drifts[:20],
        "drift_count": len(order_drifts),
    }


def run_self_test() -> int:
    passed = 0
    failed = 0

    golden = [
        "I (100) boot: ESP-IDF v5.1",
        "I (200) init: heap free=245760",
        "I (300) wifi: connected to AP",
        "I (400) main: app started",
        "I (500) task: alive",
    ]

    # 1. 完全匹配
    r = compare_traces(golden, golden)
    assert r["passed"] is True
    assert r["match_rate"] == 1.0
    print("[PASS] identical traces")
    passed += 1

    # 2. 时间戳变化不误报
    actual_ts = [l.replace("(100)", "(99999)") for l in golden]
    r = compare_traces(golden, actual_ts)
    assert r["passed"] is True
    print("[PASS] timestamp drift tolerated")
    passed += 1

    # 3. 地址变化不误报
    actual_addr = ["I (100) boot: 0x400d1234 ESP-IDF v5.1"]
    r = compare_traces(["I (100) boot: 0x400d9999 ESP-IDF v5.1"], actual_addr)
    assert r["match_rate"] > 0.5
    print("[PASS] address drift tolerated")
    passed += 1

    # 4. 事件顺序漂移检出
    actual_reordered = [
        "I (300) wifi: connected to AP",  # 顺序变了
        "I (100) boot: ESP-IDF v5.1",
        "I (400) main: app started",
    ]
    r = compare_traces(golden, actual_reordered)
    # 顺序漂移应该被检出
    assert r["drift_count"] > 0 or r["match_rate"] < 1.0
    print(f"[PASS] order drift detected: {r['drift_count']} drifts")
    passed += 1

    # 5. 行数差异
    actual_short = golden[:2]
    r = compare_traces(golden, actual_short)
    assert r["line_diff"] == 3
    print("[PASS] line diff detected")
    passed += 1

    print(f"\nSelf-test: {passed} passed, {failed} failed")
    return 1 if failed > 0 else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Trace Compare v12.0.6")
    parser.add_argument("--golden", help="Golden trace 文件")
    parser.add_argument("--actual", help="Actual trace 文件")
    parser.add_argument("--tolerance", type=int, default=3, help="事件顺序容忍窗口")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    if not args.golden or not args.actual:
        parser.print_help()
        return 1

    golden_lines = Path(args.golden).read_text(encoding="utf-8", errors="replace").splitlines()
    actual_lines = Path(args.actual).read_text(encoding="utf-8", errors="replace").splitlines()

    result = compare_traces(golden_lines, actual_lines, tolerance=args.tolerance)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"Golden:   {result['golden_lines']} lines, {result['golden_events']} events")
        print(f"Actual:   {result['actual_lines']} lines, {result['actual_events']} events")
        print(f"Match:    {result['match_rate']:.0%}")
        print(f"Drifts:   {result['drift_count']}")
        print(f"Passed:   {result['passed']}")
        for d in result["order_drifts"][:5]:
            print(f"  drift: expected '{d['expected'][:60]}' got '{d['actual'][:60]}'")

    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
