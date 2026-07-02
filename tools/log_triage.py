#!/usr/bin/env python3
"""
Log Triage v23 — 基于日志和证据的根因分流系统。

输出四类分流：software_suspicions / hardware_suspicions / architecture_refactor_candidates / missing_evidence。
遇到板级风险必须质疑硬件，遇到系统性缺陷必须建议重构。

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
    if ROUTES_FILE.exists():
        return json.loads(ROUTES_FILE.read_text(encoding="utf-8")).get("symptoms", [])
    return []


def parse_log(lines: list[str]) -> list[dict]:
    """解析日志行，提取时间戳、级别、结构化字段。"""
    events = []
    for i, line in enumerate(lines):
        s = line.strip()
        if not s:
            continue

        timestamp = ""
        ts_m = re.search(r"[DIWEF]\s*\((\d+)\)", s)
        if ts_m:
            timestamp = ts_m.group(1)

        level = ""
        lv_m = re.search(r"^([DIWEF])\s*\(", s)
        if lv_m:
            level = lv_m.group(1)

        fields = {}
        for key in ["evt", "state", "err", "seq", "task", "tag"]:
            m = re.search(rf"{key}=(\S+)", s)
            if m:
                fields[key] = m.group(1)

        events.append({
            "line_num": i + 1,
            "timestamp": timestamp,
            "level": level,
            "fields": fields,
            "raw": s[:300],
        })
    return events


def match_symptoms(events: list[dict], routes: list[dict]) -> list[dict]:
    """匹配 E/F 级别日志与症状路由。"""
    matched = []
    for route in routes:
        for pattern in route.get("patterns", []):
            for evt in events:
                if evt["level"] not in ("E", "F"):
                    continue
                if re.search(pattern, evt["raw"], re.IGNORECASE):
                    matched.append({
                        "symptom_id": route["id"],
                        "symptom_name": route["name"],
                        "category": route.get("category", "software"),
                        "severity": route["severity"],
                        "constraints": route["constraints"],
                        "root_cause_hints": route.get("root_cause_hints", []),
                        "recommended_commands": route.get("recommended_commands", []),
                        "hardware_challenge": route.get("hardware_challenge", []),
                        "architecture_flags": route.get("architecture_flags", []),
                        "architecture_refactor": route.get("architecture_refactor", []),
                        "do_not_patch_until": route.get("do_not_patch_until", ""),
                        "matched_line": evt["line_num"],
                        "matched_text": evt["raw"][:150],
                        "timestamp": evt["timestamp"],
                    })
                    break
            else:
                continue
            break
    return matched


def classify_symptoms(symptoms: list[dict]) -> dict:
    """将症状分流到四类。"""
    software = []
    hardware = []
    architecture = []

    for s in symptoms:
        cat = s.get("category", "software")
        entry = {
            "symptom_id": s["symptom_id"],
            "symptom_name": s["symptom_name"],
            "severity": s["severity"],
            "constraints": s["constraints"],
            "root_cause_hints": s["root_cause_hints"],
            "matched_line": s["matched_line"],
            "matched_text": s["matched_text"],
        }

        if cat == "hardware":
            entry["hardware_challenge"] = s.get("hardware_challenge", [])
            entry["do_not_patch_until"] = s.get("do_not_patch_until", "")
            hardware.append(entry)
        elif cat == "architecture":
            entry["architecture_refactor"] = s.get("architecture_refactor", [])
            entry["do_not_patch_until"] = s.get("do_not_patch_until", "")
            architecture.append(entry)
        elif cat == "mixed":
            # 同时出现在 software 和 hardware
            entry_hw = {**entry, "hardware_challenge": s.get("hardware_challenge", []),
                        "do_not_patch_until": s.get("do_not_patch_until", "")}
            hardware.append(entry_hw)
            software.append(entry)
        else:
            software.append(entry)

        # 即使是 software，如果有 architecture_flags，也要加入架构候选
        if s.get("architecture_flags"):
            arch_entry = {
                "symptom_id": s["symptom_id"],
                "symptom_name": s["symptom_name"],
                "severity": s["severity"],
                "constraints": s["constraints"],
                "architecture_flags": s["architecture_flags"],
                "root_cause_hints": s["root_cause_hints"],
            }
            architecture.append(arch_entry)

    return {"software": software, "hardware": hardware, "architecture": architecture}


def detect_missing_evidence(events: list[dict]) -> list[str]:
    """检测缺失证据。"""
    missing = []

    has_structured = any(e["fields"] for e in events)
    if not has_structured:
        missing.append("日志缺少结构化字段 (evt/state/err/seq/task)，置信度受限")

    has_timestamp = any(e["timestamp"] for e in events)
    if not has_timestamp:
        missing.append("日志缺少时间戳")

    has_error = any(e["level"] in ("E", "F") for e in events)
    if not has_error:
        missing.append("日志中未发现 E/F 级别日志")

    return missing


def build_next_actions(symptoms: list[dict], missing: list[str]) -> list[str]:
    """构建下一步行动。"""
    actions = []

    # 从症状收集推荐命令
    seen = set()
    for s in symptoms:
        for cmd in s.get("recommended_commands", []):
            if cmd not in seen:
                seen.add(cmd)
                actions.append(cmd)

    # 硬件验证路径
    for s in symptoms:
        if s.get("hardware_challenge"):
            for hw in s["hardware_challenge"]:
                action = f"[硬件] {hw}"
                if action not in seen:
                    seen.add(action)
                    actions.append(action)

    # 缺失证据补充
    for m in missing:
        action = f"[补充] {m}"
        if action not in seen:
            seen.add(action)
            actions.append(action)

    return actions


def build_do_not_patch_until(symptoms: list[dict]) -> list[str]:
    """收集所有 do_not_patch_until 条件。"""
    reasons = []
    seen = set()
    for s in symptoms:
        dnp = s.get("do_not_patch_until", "")
        if dnp and dnp not in seen:
            seen.add(dnp)
            reasons.append(dnp)
    return reasons


def triage(log_text: str, platform: str = "") -> dict:
    """主分析函数。"""
    lines = log_text.splitlines()
    routes = load_symptom_routes()

    events = parse_log(lines)
    symptoms = match_symptoms(events, routes)
    missing = detect_missing_evidence(events)
    classified = classify_symptoms(symptoms)
    next_actions = build_next_actions(symptoms, missing)
    do_not_patch = build_do_not_patch_until(symptoms)

    # 收集所有约束
    all_constraints = sorted({c for s in symptoms for c in s["constraints"]})

    # 置信度
    if missing:
        confidence = "low"
    elif symptoms:
        confidence = "high"
    else:
        confidence = "none"

    # 摘要
    parts = []
    if classified["software"]:
        parts.append(f"软件: {', '.join(s['symptom_id'] for s in classified['software'])}")
    if classified["hardware"]:
        parts.append(f"硬件: {', '.join(s['symptom_id'] for s in classified['hardware'])}")
    if classified["architecture"]:
        parts.append(f"架构: {', '.join(s['symptom_id'] for s in classified['architecture'])}")
    summary = "; ".join(parts) if parts else "未检测到已知症状"

    return {
        "summary": summary,
        "platform": platform,
        "total_lines": len(events),
        "software_suspicions": classified["software"],
        "hardware_suspicions": classified["hardware"],
        "architecture_refactor_candidates": classified["architecture"],
        "constraints": all_constraints,
        "missing_evidence": missing,
        "next_actions": next_actions,
        "do_not_patch_until": do_not_patch,
        "confidence": confidence,
    }


# ── 自测 ──

def run_self_test() -> int:
    passed = 0
    failed = 0

    tests = {
        "good_boot": {
            "log": "I (100) boot: ESP-IDF v5.1\nI (200) main: starting\nI (300) wifi: connected\n",
            "expect_software": 0, "expect_hardware": 0, "expect_arch": 0,
        },
        "wdt_reset": {
            "log": "I (100) boot: starting\nE (5000) task_wdt: Task watchdog timeout\n",
            "expect_software": 1, "expect_hardware": 0,
        },
        "hardfault": {
            "log": "I (100) boot: starting\nE (200) panic: HardFault\n",
            "expect_software": 1, "expect_hardware": 0,
        },
        "heap_exhaustion": {
            "log": "I (100) heap: free=1000\nE (200) malloc: pvPortMalloc failed\n",
            "expect_software": 1, "expect_hardware": 0,
        },
        "queue_full": {
            "log": "I (100) queue: sending\nE (200) queue: xQueueSend failed, queue full\n",
            "expect_software": 1, "expect_hardware": 0,
        },
        "ota_rollback": {
            "log": "I (100) ota: begin\nE (300) ota: rollback detected\n",
            "expect_software": 1, "expect_hardware": 0,
        },
        "brownout": {
            "log": "I (100) boot: starting\nE (200) reset: brownout detected\n",
            "expect_software": 0, "expect_hardware": 1,
        },
        "peripheral_no_ack": {
            "log": "I (100) i2c: init\nE (200) i2c: no ack from 0x76\n",
            "expect_software": 0, "expect_hardware": 1,
        },
        "sensor_timeout_hw": {
            "log": "I (100) sensor: init\nE (200) sensor: i2c timeout\nE (201) sensor: no response\n",
            "expect_software": 1, "expect_hardware": 1,  # mixed → appears in both
        },
        "dma_cache": {
            "log": "I (100) dma: init\nE (200) dma: cache dirty, stale data\n",
            "expect_software": 0, "expect_hardware": 1,
        },
        "lifecycle_chaos": {
            "log": "I (100) module: init\nE (200) module: double free detected\n",
            "expect_software": 0, "expect_hardware": 0, "expect_arch": 1,
        },
        "unclear_topology": {
            "log": "I (100) task: starting\nE (200) deadlock: priority inversion detected\n",
            "expect_software": 0, "expect_hardware": 0, "expect_arch": 1,
        },
    }

    for name, t in tests.items():
        r = triage(t["log"], "esp32")
        errors = []

        sw = len(r["software_suspicions"])
        hw = len(r["hardware_suspicions"])
        arch = len(r["architecture_refactor_candidates"])

        if sw != t.get("expect_software", 0):
            errors.append(f"software={sw} expected={t['expect_software']}")
        if hw != t.get("expect_hardware", 0):
            errors.append(f"hardware={hw} expected={t['expect_hardware']}")
        if t.get("expect_arch") and arch == 0:
            errors.append(f"architecture=0 expected>0")

        if name != "good_boot":
            if len(r["constraints"]) == 0:
                errors.append("no constraints")
            if len(r["next_actions"]) == 0:
                errors.append("no next_actions")

        if errors:
            print(f"[FAIL] {name}: {errors}")
            failed += 1
        else:
            cats = []
            if sw: cats.append(f"sw={sw}")
            if hw: cats.append(f"hw={hw}")
            if arch: cats.append(f"arch={arch}")
            print(f"[PASS] {name}: {', '.join(cats) if cats else 'clean'}")
            passed += 1

    # 缺失证据
    minimal = "just text\n"
    r = triage(minimal)
    assert len(r["missing_evidence"]) > 0
    print(f"[PASS] missing evidence: {len(r['missing_evidence'])} items")
    passed += 1

    print(f"\nSelf-test: {passed} passed, {failed} failed")
    return 1 if failed > 0 else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Log Triage v23 — 根因分流系统")
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

        if r["software_suspicions"]:
            print(f"\n=== Software Suspicions ({len(r['software_suspicions'])}) ===")
            for s in r["software_suspicions"]:
                print(f"  [{s['severity']}] {s['symptom_name']} @ line {s['matched_line']}")
                print(f"    Constraints: {', '.join(s['constraints'])}")

        if r["hardware_suspicions"]:
            print(f"\n=== Hardware Suspicions ({len(r['hardware_suspicions'])}) ===")
            for s in r["hardware_suspicions"]:
                print(f"  [{s['severity']}] {s['symptom_name']} @ line {s['matched_line']}")
                if s.get("hardware_challenge"):
                    print(f"    Hardware: {', '.join(s['hardware_challenge'][:3])}")
                if s.get("do_not_patch_until"):
                    print(f"    ⚠ {s['do_not_patch_until']}")

        if r["architecture_refactor_candidates"]:
            print(f"\n=== Architecture Refactor Candidates ({len(r['architecture_refactor_candidates'])}) ===")
            for s in r["architecture_refactor_candidates"]:
                print(f"  [{s['severity']}] {s['symptom_name']}")
                if s.get("architecture_refactor"):
                    print(f"    Refactor: {', '.join(s['architecture_refactor'][:3])}")

        if r["do_not_patch_until"]:
            print(f"\n=== Do NOT Patch Until ===")
            for d in r["do_not_patch_until"]:
                print(f"  ⚠ {d}")

        if r["missing_evidence"]:
            print(f"\nMissing Evidence:")
            for m in r["missing_evidence"]:
                print(f"  - {m}")

        if r["next_actions"]:
            print(f"\nNext Actions:")
            for a in r["next_actions"][:10]:
                print(f"  {a}")

    return 0 if r["software_suspicions"] or r["hardware_suspicions"] else 1


if __name__ == "__main__":
    sys.exit(main())
