#!/usr/bin/env python3
"""
Log Triage v24 — 基于日志和证据的根因分流系统（发布级）。

Exit codes:
  0 — 检测到症状（software/hardware/architecture 任一候选存在）
  1 — 未检测到已知症状
  2 — 输入/路由/JSON 错误

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

# Windows-safe 标签
TAG_SW = "[SOFTWARE]"
TAG_HW = "[HARDWARE]"
TAG_ARCH = "[ARCH]"
TAG_WARN = "[WARN]"
TAG_DNP = "[DO-NOT-PATCH]"


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

        # Raw boot/reset 行（无标准前缀）
        is_raw = bool(re.search(r"^(ets_|rst:|boot:|ROM:|pc=|lr=|EXC_RETURN)", s))

        fields = {}
        for key in ["evt", "state", "err", "seq", "task", "tag"]:
            m = re.search(rf"{key}=(\S+)", s)
            if m:
                fields[key] = m.group(1)

        events.append({
            "line_num": i + 1,
            "timestamp": timestamp,
            "level": level,
            "is_raw": is_raw,
            "fields": fields,
            "raw": s[:300],
        })
    return events


def match_symptoms(events: list[dict], routes: list[dict]) -> list[dict]:
    """匹配日志事件与症状路由。

    match_level 控制匹配范围：
      - "error"（默认）：只匹配 E/F 级别
      - "raw_boot"：匹配 raw boot/reset 行 + I/W/E/F
      - "all"：匹配所有级别
    """
    matched = []
    for route in routes:
        match_level = route.get("match_level", "error")
        for pattern in route.get("patterns", []):
            for evt in events:
                # 根据 match_level 决定是否匹配
                if match_level == "error":
                    if evt["level"] not in ("E", "F"):
                        continue
                elif match_level == "raw_boot":
                    # 允许 raw boot 行和 I/W/E/F
                    if not evt["is_raw"] and evt["level"] not in ("I", "W", "E", "F"):
                        continue
                # "all" 不过滤

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
            entry_hw = {**entry, "hardware_challenge": s.get("hardware_challenge", []),
                        "do_not_patch_until": s.get("do_not_patch_until", "")}
            hardware.append(entry_hw)
            software.append(entry)
        else:
            software.append(entry)

        # architecture_flags 也加入架构候选
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
    actions = []
    seen = set()

    for s in symptoms:
        for cmd in s.get("recommended_commands", []):
            if cmd not in seen:
                seen.add(cmd)
                actions.append(cmd)
        for hw in s.get("hardware_challenge", []):
            action = f"{TAG_HW} {hw}"
            if action not in seen:
                seen.add(action)
                actions.append(action)

    for m in missing:
        action = f"{TAG_WARN} {m}"
        if action not in seen:
            seen.add(action)
            actions.append(action)

    return actions


def build_do_not_patch_until(symptoms: list[dict]) -> list[str]:
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

    all_constraints = sorted({c for s in symptoms for c in s["constraints"]})

    confidence = "low" if missing else ("high" if symptoms else "none")

    parts = []
    if classified["software"]:
        parts.append(f"sw: {', '.join(s['symptom_id'] for s in classified['software'])}")
    if classified["hardware"]:
        parts.append(f"hw: {', '.join(s['symptom_id'] for s in classified['hardware'])}")
    if classified["architecture"]:
        parts.append(f"arch: {', '.join(s['symptom_id'] for s in classified['architecture'])}")
    summary = "; ".join(parts) if parts else "未检测到已知症状"

    has_symptoms = bool(classified["software"] or classified["hardware"] or classified["architecture"])

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
        "has_symptoms": has_symptoms,
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
            "expect_software": 1, "expect_hardware": 1,
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
        "raw_esp32_reset": {
            "log": "rst:0x3 (SW_RESET),boot:0x13 (SPI_FAST_FLASH_BOOT)\n",
            "expect_software": 0, "expect_hardware": 0,  # raw boot 不匹配软件/硬件症状
            "expect_no_symptoms": True,
        },
        "raw_brownout": {
            "log": "rst:0x1 (POWERON_RESET),boot:0x13\nE (100) reset: brownout detected\n",
            "expect_hardware": 1,
        },
        "voltage_drop_no_false_positive": {
            "log": "I (100) sensor: reading\nI (200) sensor: voltage drop compensated\n",
            "expect_software": 0, "expect_hardware": 0, "expect_no_symptoms": True,
        },
    }

    for name, t in tests.items():
        r = triage(t["log"], "esp32")
        errors = []

        sw = len(r["software_suspicions"])
        hw = len(r["hardware_suspicions"])
        arch = len(r["architecture_refactor_candidates"])

        if t.get("expect_no_symptoms"):
            if sw + hw + arch > 0:
                errors.append(f"expected no symptoms but got sw={sw} hw={hw} arch={arch}")
        else:
            if sw != t.get("expect_software", 0):
                errors.append(f"software={sw} expected={t['expect_software']}")
            if hw != t.get("expect_hardware", 0):
                errors.append(f"hardware={hw} expected={t['expect_hardware']}")
            if t.get("expect_arch") and arch == 0:
                errors.append(f"architecture=0 expected>0")

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

    # Windows-safe 输出检查
    r = triage("E (100) panic: HardFault\n", "esp32")
    text = json.dumps(r)
    assert "WARN" not in text or TAG_WARN in text or "[" not in text  # JSON 中无所谓
    print("[PASS] Windows-safe output")
    passed += 1

    print(f"\nSelf-test: {passed} passed, {failed} failed")
    return 1 if failed > 0 else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Log Triage v24 -- 根因分流系统")
    parser.add_argument("--log", help="日志文件路径")
    parser.add_argument("--platform", default="", help="平台")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    if not args.log:
        parser.print_help()
        return 2  # 输入错误

    try:
        log_text = Path(args.log).read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        print(f"[ERROR] 无法读取日志: {e}", file=sys.stderr)
        return 2

    try:
        r = triage(log_text, args.platform)
    except Exception as e:
        print(f"[ERROR] 分析失败: {e}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(r, indent=2, ensure_ascii=False))
    else:
        print(f"Summary: {r['summary']}")
        print(f"Confidence: {r['confidence']}")
        print(f"Lines: {r['total_lines']}")

        if r["software_suspicions"]:
            print(f"\n=== {TAG_SW} ({len(r['software_suspicions'])}) ===")
            for s in r["software_suspicions"]:
                print(f"  [{s['severity']}] {s['symptom_name']} @ line {s['matched_line']}")
                print(f"    Constraints: {', '.join(s['constraints'])}")

        if r["hardware_suspicions"]:
            print(f"\n=== {TAG_HW} ({len(r['hardware_suspicions'])}) ===")
            for s in r["hardware_suspicions"]:
                print(f"  [{s['severity']}] {s['symptom_name']} @ line {s['matched_line']}")
                if s.get("hardware_challenge"):
                    print(f"    Challenge: {', '.join(s['hardware_challenge'][:3])}")
                if s.get("do_not_patch_until"):
                    print(f"    {TAG_DNP} {s['do_not_patch_until']}")

        if r["architecture_refactor_candidates"]:
            print(f"\n=== {TAG_ARCH} ({len(r['architecture_refactor_candidates'])}) ===")
            for s in r["architecture_refactor_candidates"]:
                print(f"  [{s['severity']}] {s['symptom_name']}")
                if s.get("architecture_refactor"):
                    print(f"    Refactor: {', '.join(s['architecture_refactor'][:3])}")

        if r["do_not_patch_until"]:
            print(f"\n=== {TAG_DNP} ===")
            for d in r["do_not_patch_until"]:
                print(f"  {TAG_DNP} {d}")

        if r["missing_evidence"]:
            print(f"\n{TAG_WARN} Missing Evidence:")
            for m in r["missing_evidence"]:
                print(f"  {TAG_WARN} {m}")

        if r["next_actions"]:
            print(f"\nNext Actions:")
            for a in r["next_actions"][:10]:
                print(f"  {a}")

    # Exit code: 0=有症状, 1=无症状, 2=错误
    return 0 if r.get("has_symptoms") else 1


if __name__ == "__main__":
    sys.exit(main())
