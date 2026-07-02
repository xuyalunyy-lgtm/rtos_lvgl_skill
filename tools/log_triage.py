#!/usr/bin/env python3
"""
Log Triage v23.0.2 — 日志快速定位 bug。

输入串口/崩溃/运行日志，输出时间线、异常信号、根因候选、约束 ID、缺失证据、下一步命令。

用法:
    python tools/log_triage.py --log serial.log --platform esp32
    python tools/log_triage.py --log serial.log --platform esp32 --json
    python tools/log_triage.py --self-test
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ROUTES_FILE = ROOT / "references" / "log_symptom_routes.json"


def load_symptom_routes() -> list[dict]:
    """加载症状路由表。"""
    if ROUTES_FILE.exists():
        data = json.loads(ROUTES_FILE.read_text(encoding="utf-8"))
        return data.get("symptoms", [])
    return []


def parse_log(lines: list[str]) -> list[dict]:
    """解析日志行，提取时间戳和关键字段。"""
    events = []
    for i, line in enumerate(lines):
        line_stripped = line.strip()
        if not line_stripped:
            continue

        # 时间戳提取
        timestamp = ""
        ts_match = re.search(r"[DIWEF]\s*\((\d+)\)", line_stripped)
        if ts_match:
            timestamp = ts_match.group(1)

        # 结构化字段提取
        fields = {}
        for key in ["evt", "state", "err", "seq", "task", "tag"]:
            m = re.search(rf"{key}=(\S+)", line_stripped)
            if m:
                fields[key] = m.group(1)

        # 日志级别
        level = ""
        level_match = re.search(r"^([DIWEF])\s*\(", line_stripped)
        if level_match:
            level = level_match.group(1)

        events.append({
            "line_num": i + 1,
            "timestamp": timestamp,
            "level": level,
            "fields": fields,
            "raw": line_stripped[:300],
        })
    return events


def match_symptoms(events: list[dict], routes: list[dict]) -> list[dict]:
    """匹配日志事件与症状路由。只匹配 E/F 级别日志行（排除正常 I/D 日志）。"""
    matched = []
    for route in routes:
        patterns = route.get("patterns", [])
        for pattern in patterns:
            for evt in events:
                # 只在 E/F 级别日志中匹配症状（排除正常启动/信息日志）
                if evt["level"] not in ("E", "F"):
                    continue
                if re.search(pattern, evt["raw"], re.IGNORECASE):
                    matched.append({
                        "symptom_id": route["id"],
                        "symptom_name": route["name"],
                        "severity": route["severity"],
                        "constraints": route["constraints"],
                        "root_cause_hints": route["root_cause_hints"],
                        "recommended_commands": route["recommended_commands"],
                        "matched_line": evt["line_num"],
                        "matched_text": evt["raw"][:100],
                        "timestamp": evt["timestamp"],
                    })
                    break  # 每个症状只匹配一次
            else:
                continue
            break
    return matched


def detect_missing_evidence(events: list[dict]) -> list[str]:
    """检测日志中缺失的结构化字段。"""
    missing = []
    has_structured = any(e["fields"] for e in events)

    if not has_structured:
        missing.append("日志缺少结构化字段 (evt/state/err/seq/task)，置信度受限")

    # 检查是否有时间戳
    has_timestamp = any(e["timestamp"] for e in events)
    if not has_timestamp:
        missing.append("日志缺少时间戳")

    # 检查是否有错误级别
    has_error = any(e["level"] in ("E", "F") for e in events)
    if not has_error:
        missing.append("日志中未发现 E/F 级别日志")

    return missing


def build_timeline(events: list[dict], symptoms: list[dict]) -> list[dict]:
    """构建时间线。"""
    timeline = []
    symptom_lines = {s["matched_line"]: s for s in symptoms}

    for evt in events:
        entry = {
            "line": evt["line_num"],
            "timestamp": evt["timestamp"],
            "level": evt["level"],
            "text": evt["raw"][:150],
        }
        if evt["line_num"] in symptom_lines:
            s = symptom_lines[evt["line_num"]]
            entry["symptom"] = s["symptom_id"]
            entry["severity"] = s["severity"]
        timeline.append(entry)

    return timeline


def triage(log_text: str, platform: str = "") -> dict:
    """主分析函数。"""
    lines = log_text.splitlines()
    routes = load_symptom_routes()

    # 1. 解析日志
    events = parse_log(lines)

    # 2. 匹配症状
    symptoms = match_symptoms(events, routes)

    # 3. 检测缺失证据
    missing = detect_missing_evidence(events)

    # 4. 构建时间线
    timeline = build_timeline(events, symptoms)

    # 5. 收集约束
    all_constraints = []
    for s in symptoms:
        all_constraints.extend(s["constraints"])
    all_constraints = sorted(set(all_constraints))

    # 6. 收集推荐命令
    all_commands = []
    for s in symptoms:
        all_commands.extend(s["recommended_commands"])
    all_commands = sorted(set(all_commands))

    # 7. 置信度评估
    confidence = "high" if not missing and symptoms else ("medium" if symptoms else "low")

    # 8. 摘要
    summary_parts = []
    for s in symptoms:
        summary_parts.append(f"{s['symptom_name']}({s['severity']})")
    summary = ", ".join(summary_parts) if summary_parts else "未检测到已知症状"

    return {
        "summary": summary,
        "platform": platform,
        "total_lines": len(events),
        "symptoms": symptoms,
        "timeline": timeline[:50],  # 限制输出长度
        "constraints": all_constraints,
        "missing_evidence": missing,
        "recommended_commands": all_commands,
        "confidence": confidence,
    }


def run_self_test() -> int:
    passed = 0
    failed = 0

    # 测试日志样本
    test_logs = {
        "good_boot": "I (100) boot: ESP-IDF v5.1\nI (200) main: starting\nI (300) wifi: connected\nI (400) main: initialized\n",
        "bad_wdt": "I (100) boot: starting\nI (200) task: running\nE (5000) task_wdt: Task watchdog timeout\nE (5001) task_wdt: TWDT\n",
        "bad_heap": "I (100) heap: free=1000\nE (200) malloc: pvPortMalloc failed\nE (201) heap: out of memory\n",
        "bad_queue": "I (100) queue: sending\nE (200) queue: xQueueSend failed, queue full\nE (201) queue: drop\n",
        "bad_ota": "I (100) ota: begin\nI (200) ota: writing\nE (300) ota: rollback detected\n",
        "bad_hardfault": "I (100) boot: starting\nE (200) panic: HardFault\nE (201) panic: Guru Meditation Error\n",
    }

    for name, log_text in test_logs.items():
        r = triage(log_text, "esp32")
        assert "summary" in r
        assert "symptoms" in r
        assert "constraints" in r
        assert "missing_evidence" in r
        assert "recommended_commands" in r

        if name == "good_boot":
            assert len(r["symptoms"]) == 0, f"good_boot should have no symptoms"
            print(f"[PASS] {name}: no symptoms detected")
        else:
            assert len(r["symptoms"]) > 0, f"{name} should have symptoms"
            assert len(r["constraints"]) > 0, f"{name} should have constraints"
            assert len(r["recommended_commands"]) > 0, f"{name} should have commands"
            print(f"[PASS] {name}: {r['symptoms'][0]['symptom_id']} → {r['constraints']}")
        passed += 1

    # 缺失证据检测
    minimal_log = "just some text\nno structure here\n"
    r = triage(minimal_log)
    assert len(r["missing_evidence"]) > 0
    print(f"[PASS] missing evidence detected: {len(r['missing_evidence'])} items")
    passed += 1

    print(f"\nSelf-test: {passed} passed, {failed} failed")
    return 1 if failed > 0 else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Log Triage v23.0.2")
    parser.add_argument("--log", help="日志文件路径")
    parser.add_argument("--platform", default="", help="平台")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    if not args.log:
        parser.print_help()
        return 1

    log_text = Path(args.log).read_text(encoding="utf-8", errors="replace")
    r = triage(log_text, args.platform)

    if args.json:
        print(json.dumps(r, indent=2, ensure_ascii=False))
    else:
        print(f"Summary: {r['summary']}")
        print(f"Confidence: {r['confidence']}")
        print(f"Lines: {r['total_lines']}")
        if r["symptoms"]:
            print(f"\nSymptoms ({len(r['symptoms'])}):")
            for s in r["symptoms"]:
                print(f"  [{s['severity']}] {s['symptom_name']} @ line {s['matched_line']}")
                print(f"    Constraints: {', '.join(s['constraints'])}")
                print(f"    Hints: {', '.join(s['root_cause_hints'][:3])}")
        if r["missing_evidence"]:
            print(f"\nMissing Evidence:")
            for m in r["missing_evidence"]:
                print(f"  - {m}")
        if r["recommended_commands"]:
            print(f"\nRecommended Commands:")
            for c in r["recommended_commands"]:
                print(f"  {c}")

    return 0 if r["symptoms"] else 1


if __name__ == "__main__":
    sys.exit(main())
