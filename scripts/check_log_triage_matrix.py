#!/usr/bin/env python3
"""
Log Triage Matrix — 验证所有日志样本的 triage 结果。

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

# 预期结果
EXPECTED = {
    "good_boot.log": {"symptom_count": 0, "should_have_symptoms": False},
    "bad_wdt_queue_full.log": {"symptom_ids": ["WDT_RESET"], "constraint_count_min": 1},
    "bad_heap_drop.log": {"symptom_ids": ["HEAP_EXHAUSTION"], "constraint_count_min": 1},
    "bad_audio_underrun.log": {"symptom_ids": ["AUDIO_UNDERRUN"], "constraint_count_min": 1},
    "bad_sensor_timeout.log": {"symptom_ids": ["SENSOR_TIMEOUT"], "constraint_count_min": 1},
    "bad_ota_rollback.log": {"symptom_ids": ["OTA_ROLLBACK"], "constraint_count_min": 1},
}


def check_all() -> dict:
    """检查所有日志样本。"""
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
            if len(r["symptoms"]) == 0:
                errors.append("未检测到症状")
            for sid in expected.get("symptom_ids", []):
                found = any(s["symptom_id"] == sid for s in r["symptoms"])
                if not found:
                    errors.append(f"未检测到 {sid}")
            if len(r["constraints"]) < expected.get("constraint_count_min", 0):
                errors.append(f"约束数不足: {len(r['constraints'])}")
            if len(r["recommended_commands"]) == 0:
                errors.append("无推荐命令")
        else:
            if len(r["symptoms"]) > 0:
                errors.append(f"不应检测到症状但检测到 {len(r['symptoms'])} 个")

        # 所有日志都应有 missing_evidence 检测
        if not r["missing_evidence"]:
            errors.append("未检测缺失证据")

        passed = len(errors) == 0
        if not passed:
            all_passed = False

        results.append({
            "log": log_name,
            "passed": passed,
            "errors": errors,
            "symptoms": [s["symptom_id"] for s in r["symptoms"]],
            "constraints": r["constraints"],
        })

    return {
        "passed": all_passed,
        "total": len(results),
        "passed_count": sum(1 for r in results if r["passed"]),
        "results": results,
    }


def run_self_test() -> int:
    r = check_all()
    print(f"Log Triage Matrix: {r['passed_count']}/{r['total']} passed")
    for pr in r["results"]:
        icon = "[PASS]" if pr["passed"] else "[FAIL]"
        print(f"  {icon} {pr['log']}: {pr['symptoms']}")
        if pr["errors"]:
            for e in pr["errors"]:
                print(f"    - {e}")
    return 0 if r["passed"] else 1


def main() -> int:
    r = check_all()
    if "--json" in sys.argv:
        print(json.dumps(r, indent=2, ensure_ascii=False))
    else:
        print(f"Log Triage Matrix: {r['passed_count']}/{r['total']} passed")
        for pr in r["results"]:
            icon = "[PASS]" if pr["passed"] else "[FAIL]"
            print(f"  {icon} {pr['log']}: {pr['symptoms']}")
    return 0 if r["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
