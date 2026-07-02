#!/usr/bin/env python3
"""
Log Triage Matrix v25 — 严格日志分流回归矩阵。

支持 expected_ids / forbidden_ids / expected_counts / expected_exit_code。
多出来的 P0/P1 症状默认 fail。

用法:
    python scripts/check_log_triage_matrix.py
    python scripts/check_log_triage_matrix.py --self-test
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
LOGS_DIR = TOOLS / "fixtures" / "logs"

# ── 严格矩阵定义 ──
MATRIX = [
    {
        "log": "good_boot.log",
        "expected_ids": [],
        "allowed_extra_ids": [],
        "expected_exit": 1,
        "expected_category_counts": {"software": 0, "hardware": 0, "architecture": 0},
    },
    {
        "log": "bad_wdt_queue_full.log",
        "expected_ids": ["WDT_RESET"],
        "allowed_extra_ids": ["HARDFAULT"],  # 联动症状
        "expected_exit": 0,
        "expected_category_counts": {"software": 2, "hardware": 0, "architecture": 2},
    },
    {
        "log": "bad_heap_drop.log",
        "expected_ids": ["HEAP_EXHAUSTION"],
        "allowed_extra_ids": [],
        "expected_exit": 0,
        "expected_category_counts": {"software": 1, "hardware": 0, "architecture": 1},
    },
    {
        "log": "bad_audio_underrun.log",
        "expected_ids": ["AUDIO_UNDERRUN"],
        "allowed_extra_ids": [],
        "expected_exit": 0,
        "expected_category_counts": {"software": 1, "hardware": 0, "architecture": 1},
    },
    {
        "log": "bad_sensor_timeout.log",
        "expected_ids": ["SENSOR_TIMEOUT"],
        "allowed_extra_ids": [],
        "expected_exit": 0,
        "expected_category_counts": {"software": 1, "hardware": 1, "architecture": 1},
    },
    {
        "log": "bad_ota_rollback.log",
        "expected_ids": ["OTA_ROLLBACK"],
        "allowed_extra_ids": [],
        "expected_exit": 0,
        "expected_category_counts": {"software": 1, "hardware": 0, "architecture": 1},
    },
    {
        "log": "bad_brownout.log",
        "expected_ids": ["BROWNOUT_RESET"],
        "allowed_extra_ids": [],
        "expected_exit": 0,
        "expected_category_counts": {"software": 0, "hardware": 1, "architecture": 0},
    },
    {
        "log": "bad_i2c_no_ack.log",
        "expected_ids": ["PERIPHERAL_NO_ACK"],
        "allowed_extra_ids": [],
        "expected_exit": 0,
        "expected_category_counts": {"software": 0, "hardware": 1, "architecture": 0},
    },
    {
        "log": "bad_lifecycle_chaos.log",
        "expected_ids": ["LIFECYCLE_CHAOS"],
        "allowed_extra_ids": [],
        "expected_exit": 0,
        "expected_category_counts": {"software": 0, "hardware": 0, "architecture": 1},
    },
    {
        "log": "bad_priority_inversion.log",
        "expected_ids": ["UNCLEAR_TOPOLOGY"],
        "allowed_extra_ids": ["WDT_RESET"],  # 联动症状
        "expected_exit": 0,
        "expected_category_counts": {"software": 1, "hardware": 0, "architecture": 2},
    },
]


def _run_triage_cli(log_path: Path) -> dict:
    """通过 CLI 子进程运行 log_triage，验证 exit code 和输出。"""
    cmd = [sys.executable, str(TOOLS / "log_triage.py"), "--log", str(log_path), "--platform", "esp32", "--json"]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, encoding="utf-8", errors="replace",
            timeout=30, cwd=str(ROOT), env={**os.environ, "PYTHONUTF8": "1"},
        )
        stdout = proc.stdout
        # Windows-safe 检查
        has_unsafe = any(ch in stdout for ch in ["⚠", "🔴", "🟡", "🟢"])
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            data = {}
        return {
            "exit_code": proc.returncode,
            "data": data,
            "has_unsafe_chars": has_unsafe,
            "stdout": stdout[:500],
        }
    except subprocess.TimeoutExpired:
        return {"exit_code": -1, "data": {}, "has_unsafe_chars": False, "stdout": "timeout"}


def check_all() -> dict:
    """运行完整矩阵。"""
    results = []
    all_passed = True

    for case in MATRIX:
        log_path = LOGS_DIR / case["log"]
        errors = []

        if not log_path.exists():
            results.append({"log": case["log"], "passed": False, "errors": ["文件不存在"]})
            all_passed = False
            continue

        # CLI 回归
        cli = _run_triage_cli(log_path)
        expected_exit = case.get("expected_exit", 0)
        if cli["exit_code"] != expected_exit:
            errors.append(f"exit_code={cli['exit_code']} expected={expected_exit}")

        # Windows-safe
        if cli["has_unsafe_chars"]:
            errors.append("输出包含非 ASCII 警告符号")

        r = cli["data"]
        if not r:
            errors.append("JSON 解析失败")
            results.append({"log": case["log"], "passed": False, "errors": errors})
            all_passed = False
            continue

        # 收集所有检测到的症状 ID
        all_ids = set()
        for key in ["software_suspicions", "hardware_suspicions", "architecture_refactor_candidates"]:
            for s in r.get(key, []):
                all_ids.add(s.get("symptom_id", ""))

        # expected_ids + allowed_extra_ids 精确合同
        expected = set(case.get("expected_ids", []))
        allowed_extra = set(case.get("allowed_extra_ids", []))
        allowed_all = expected | allowed_extra

        # 必须包含 expected_ids
        missing = expected - all_ids
        if missing:
            errors.append(f"expected symptoms missing: {sorted(missing)}")

        # 不允许超出 allowed_all 的额外症状
        extra = all_ids - allowed_all
        if extra:
            errors.append(f"unexpected symptoms: {sorted(extra)}")

        # forbidden_ids（向后兼容）
        for fid in case.get("forbidden_ids", []):
            if fid in all_ids:
                errors.append(f"forbidden {fid} found")

        # expected_category_counts
        for cat, expected_count in case.get("expected_category_counts", {}).items():
            key = {"software": "software_suspicions", "hardware": "hardware_suspicions",
                   "architecture": "architecture_refactor_candidates"}.get(cat, cat)
            actual = len(r.get(key, []))
            if actual != expected_count:
                errors.append(f"{cat} count={actual} expected={expected_count}")

        passed = len(errors) == 0
        if not passed:
            all_passed = False

        results.append({
            "log": case["log"],
            "passed": passed,
            "errors": errors,
            "exit_code": cli["exit_code"],
            "symptoms": sorted(all_ids),
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
            print(f"  {icon} {pr['log']}: exit={pr['exit_code']} symptoms={pr['symptoms']}")
            if pr["errors"]:
                for e in pr["errors"]:
                    print(f"    - {e}")
    return 0 if r["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
