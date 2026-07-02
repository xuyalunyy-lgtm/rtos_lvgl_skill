#!/usr/bin/env python3
"""
Log Triage Matrix — 验证日志样例的四类分流正确性。

用法:
    python scripts/check_log_triage_matrix.py
    python scripts/check_log_triage_matrix.py --self-test
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
LOGS_DIR = TOOLS / "fixtures" / "logs"

EXPECTED = {
    "good_boot.log": {"should_have_symptoms": False},
    "bad_wdt_queue_full.log": {"symptom_ids": ["WDT_RESET"], "category": "software"},
    "bad_heap_drop.log": {"symptom_ids": ["HEAP_EXHAUSTION"], "category": "software"},
    "bad_audio_underrun.log": {"symptom_ids": ["AUDIO_UNDERRUN"], "category": "software"},
    "bad_sensor_timeout.log": {"symptom_ids": ["SENSOR_TIMEOUT"], "category": "mixed"},
    "bad_ota_rollback.log": {"symptom_ids": ["OTA_ROLLBACK"], "category": "software"},
    "bad_brownout.log": {"symptom_ids": ["BROWNOUT_RESET"], "category": "hardware"},
    "bad_i2c_no_ack.log": {"symptom_ids": ["PERIPHERAL_NO_ACK"], "category": "hardware"},
    "bad_lifecycle_chaos.log": {"symptom_ids": ["LIFECYCLE_CHAOS"], "category": "architecture"},
    "bad_priority_inversion.log": {"symptom_ids": ["UNCLEAR_TOPOLOGY"], "category": "architecture"},
}


def check_all() -> dict:
    sys.path.insert(0, str(TOOLS))
    from log_triage import triage

    results = []
    all_passed = True

    for log_name, expected in EXPECTED.items():
        log_path = LOGS_DIR / log_name
        if not log_path.exists():
            results.append({"log": log_name, "passed": False, "errors": ["文件不存在"]})
            all_passed = False
            continue

        log_text = log_path.read_text(encoding="utf-8")
        r = triage(log_text, "esp32")
        errors = []

        if expected.get("should_have_symptoms", True):
            # 检查症状是否被检测到
            all_symptom_ids = (
                [s["symptom_id"] for s in r["software_suspicions"]] +
                [s["symptom_id"] for s in r["hardware_suspicions"]] +
                [s["symptom_id"] for s in r["architecture_refactor_candidates"]]
            )
            for sid in expected.get("symptom_ids", []):
                if sid not in all_symptom_ids:
                    errors.append(f"未检测到 {sid}")

            # 检查分类
            cat = expected.get("category", "software")
            if cat == "hardware" and len(r["hardware_suspicions"]) == 0:
                errors.append("应有硬件怀疑但无")
            if cat == "architecture" and len(r["architecture_refactor_candidates"]) == 0:
                errors.append("应有架构重构候选但无")

            # 硬件怀疑必须有 hardware_challenge
            for hw in r["hardware_suspicions"]:
                if not hw.get("hardware_challenge"):
                    errors.append(f"{hw['symptom_id']} 缺少 hardware_challenge")

            # 架构候选必须有 architecture_refactor 或 architecture_flags
            for arch in r["architecture_refactor_candidates"]:
                if not arch.get("architecture_refactor") and not arch.get("architecture_flags"):
                    errors.append(f"{arch['symptom_id']} 缺少 architecture_refactor/flags")

            if len(r["constraints"]) == 0:
                errors.append("无约束")
            if len(r["next_actions"]) == 0:
                errors.append("无 next_actions")
        else:
            sw = len(r["software_suspicions"])
            hw = len(r["hardware_suspicions"])
            if sw + hw > 0:
                errors.append(f"不应检测到症状但检测到 sw={sw} hw={hw}")

        passed = len(errors) == 0
        if not passed:
            all_passed = False

        results.append({
            "log": log_name,
            "passed": passed,
            "errors": errors,
            "software": len(r["software_suspicions"]),
            "hardware": len(r["hardware_suspicions"]),
            "architecture": len(r["architecture_refactor_candidates"]),
        })

    return {
        "passed": all_passed,
        "total": len(results),
        "passed_count": sum(1 for r in results if r["passed"]),
        "results": results,
    }


def main() -> int:
    r = check_all()
    if "--json" in sys.argv:
        print(json.dumps(r, indent=2, ensure_ascii=False))
    else:
        print(f"Log Triage Matrix: {r['passed_count']}/{r['total']} passed")
        for pr in r["results"]:
            icon = "[PASS]" if pr["passed"] else "[FAIL]"
            cats = f"sw={pr['software']} hw={pr['hardware']} arch={pr['architecture']}"
            print(f"  {icon} {pr['log']}: {cats}")
            if pr["errors"]:
                for e in pr["errors"]:
                    print(f"    - {e}")
    return 0 if r["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
