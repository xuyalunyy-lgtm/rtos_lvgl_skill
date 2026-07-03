#!/usr/bin/env python3
"""
Telemetry Parser v12.0.3 — 串口日志遥测解析。

解析 boot_ok、reset_reason、heap、stack_hwm、WDT、task_alive、
network、OTA、audio_underrun、sensor_timeout。

用法:
    python tools/telemetry_parser.py --log serial.log --json
    python tools/telemetry_parser.py --log serial.log --format table
    python tools/telemetry_parser.py --self-test
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# ── 解析规则 ──
PARSE_RULES = [
    {
        "event_type": "boot_ok",
        "pattern": r"(?:boot.*(?:ok|started|complete)|ESP-IDF|app_main|starting)",
        "extract": lambda m: {"value": True},
    },
    {
        "event_type": "reset_reason",
        "pattern": r"(?:reset.*reason|rst.*reason)[:\s]*(\w+)",
        "extract": lambda m: {"value": m.group(1)},
    },
    {
        "event_type": "heap_info",
        "pattern": r"(?:heap|HEAP|free).*?(\d{4,})",
        "extract": lambda m: {"value": int(m.group(1)), "unit": "bytes"},
    },
    {
        "event_type": "stack_hwm",
        "pattern": r"(?:stack|HWM|high.watermark).*?(\d{3,})",
        "extract": lambda m: {"value": int(m.group(1)), "unit": "bytes"},
    },
    {
        "event_type": "wdt_trigger",
        "pattern": r"(?:WDT|watchdog|task_wdt|TIMERG)",
        "extract": lambda m: {"value": True},
    },
    {
        "event_type": "task_alive",
        "pattern": r"(?:task|TASK)\s*['\"]?(\w+)['\"]?\s*(?:alive|heartbeat|tick|running)",
        "extract": lambda m: {"task_name": m.group(1), "value": True},
    },
    {
        "event_type": "network_connect",
        "pattern": r"(?:wifi|WIFI|sta).*(?:connected|CONNECTED|got_ip|GOT_IP)",
        "extract": lambda m: {"value": True},
    },
    {
        "event_type": "network_disconnect",
        "pattern": r"(?:wifi|WIFI|sta).*(?:disconnect|DISCONNECT|lost)",
        "extract": lambda m: {"value": True},
    },
    {
        "event_type": "ota_start",
        "pattern": r"(?:OTA|ota).*(?:begin|start|downloading)",
        "extract": lambda m: {"value": True},
    },
    {
        "event_type": "ota_complete",
        "pattern": r"(?:OTA|ota).*(?:complete|success|finished)",
        "extract": lambda m: {"value": True},
    },
    {
        "event_type": "ota_rollback",
        "pattern": r"(?:OTA|ota).*(?:rollback|ROLLBACK|revert)",
        "extract": lambda m: {"value": True},
    },
    {
        "event_type": "audio_underrun",
        "pattern": r"(?:audio|AUDIO|i2s).*(?:underrun|UNDERRUN|underflow|xrun)",
        "extract": lambda m: {"value": True},
    },
    {
        "event_type": "sensor_timeout",
        "pattern": r"(?:sensor|SENSOR|i2c|spi).*(?:timeout|TIMEOUT|no.response|not.ready)",
        "extract": lambda m: {"value": True},
    },
    {
        "event_type": "error",
        "pattern": r"\b(?:E\s*\(|ERROR|FATAL|panic|abort|assert)",
        "extract": lambda m: {"value": True},
    },
]


def parse_log(lines: list[str]) -> list[dict]:
    """解析日志行，返回遥测条目列表。"""
    entries = []
    for line in lines:
        line_stripped = line.strip()
        if not line_stripped:
            continue
        for rule in PARSE_RULES:
            m = re.search(rule["pattern"], line_stripped, re.IGNORECASE)
            if m:
                details = rule["extract"](m)
                entry = {
                    "event_type": rule["event_type"],
                    "raw_line": line_stripped[:300],
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    **details,
                }
                entries.append(entry)
                break  # 每行只匹配第一个规则
    return entries


def summarize(entries: list[dict]) -> dict:
    """汇总遥测条目。"""
    from collections import Counter
    type_counts = Counter(e["event_type"] for e in entries)

    heap_values = [e["value"] for e in entries if e["event_type"] == "heap_info" and isinstance(e.get("value"), int)]
    stack_values = [e["value"] for e in entries if e["event_type"] == "stack_hwm" and isinstance(e.get("value"), int)]

    return {
        "total_events": len(entries),
        "event_counts": dict(type_counts),
        "boot_ok": type_counts.get("boot_ok", 0) > 0,
        "wdt_triggered": type_counts.get("wdt_trigger", 0) > 0,
        "heap_min": min(heap_values) if heap_values else None,
        "stack_hwm_min": min(stack_values) if stack_values else None,
        "network_connected": type_counts.get("network_connect", 0) > 0,
        "ota_rollback": type_counts.get("ota_rollback", 0) > 0,
        "error_count": type_counts.get("error", 0),
    }


def run_self_test() -> int:
    passed = 0
    failed = 0

    # 测试日志
    test_log = [
        "I (100) boot: ESP-IDF v5.1 starting",
        "I (200) heap: free=245760",
        "I (300) wifi: connected to AP 'test'",
        "I (400) main: app_main started",
        "I (500) task: audio_task alive",
        "W (600) audio: underrun detected",
        "E (700) sensor: i2c timeout",
        "I (800) ota: rollback to previous",
        "I (900) stack: HWM=1024",
        "E (1000) WDT: task_wdt triggered",
    ]

    entries = parse_log(test_log)
    assert len(entries) >= 7, f"Expected >=7 entries, got {len(entries)}"
    print(f"[PASS] parsed {len(entries)} events")
    passed += 1

    # 检查各事件类型
    types = {e["event_type"] for e in entries}
    assert "boot_ok" in types
    assert "heap_info" in types
    assert "network_connect" in types
    assert "wdt_trigger" in types
    assert "ota_rollback" in types
    print(f"[PASS] event types: {sorted(types)}")
    passed += 1

    # 汇总
    summary = summarize(entries)
    assert summary["boot_ok"] is True
    assert summary["wdt_triggered"] is True
    assert summary["heap_min"] == 245760
    assert summary["ota_rollback"] is True
    print(f"[PASS] summary: boot_ok={summary['boot_ok']}, wdt={summary['wdt_triggered']}")
    passed += 1

    # 空日志
    empty = parse_log([])
    assert len(empty) == 0
    print("[PASS] empty log")
    passed += 1

    print(f"\nSelf-test: {passed} passed, {failed} failed")
    return 1 if failed > 0 else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Telemetry Parser v12.0.3")
    parser.add_argument("--log", help="日志文件路径")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--format", choices=["json", "table", "summary"], default="json")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    if not args.log:
        parser.print_help()
        return 1

    lines = Path(args.log).read_text(encoding="utf-8", errors="replace").splitlines()
    entries = parse_log(lines)
    summary = summarize(entries)

    fmt = args.format if args.format != "json" else ("json" if args.json else "table")

    if fmt == "json" or args.json:
        output = {"entries": entries, "summary": summary}
        print(json.dumps(output, indent=2, ensure_ascii=False))
    elif fmt == "summary":
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    else:
        print(f"Events: {summary['total_events']}")
        print(f"Boot OK: {summary['boot_ok']}")
        print(f"WDT: {summary['wdt_triggered']}")
        print(f"Heap min: {summary['heap_min']}")
        print(f"Errors: {summary['error_count']}")
        for e in entries[:20]:
            print(f"  [{e['event_type']:20s}] {e['raw_line'][:80]}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
