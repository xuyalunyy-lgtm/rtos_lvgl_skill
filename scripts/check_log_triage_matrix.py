#!/usr/bin/env python3
"""Validate log triage results against expected symptom matrices."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
LOGS_DIR = TOOLS / "fixtures" / "logs"
ROUTES_FILE = ROOT / "references" / "log_symptom_routes.json"

# Test cases for log-triage smoke checks.
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
        "allowed_extra_ids": ["HARDFAULT"],
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
        "log": "bad_lvgl_cross_thread.log",
        "expected_ids": ["LVGL_CRASH"],
        "allowed_extra_ids": [],
        "expected_exit": 0,
        "expected_category_counts": {"software": 1, "hardware": 0, "architecture": 0},
    },
    {
        "log": "bad_dma_cache_stale.log",
        "expected_ids": ["DMA_CACHE_ERROR"],
        "allowed_extra_ids": [],
        "expected_exit": 0,
        "expected_category_counts": {"software": 0, "hardware": 1, "architecture": 0},
    },
    {
        "log": "bad_zephyr_kernel_oops.log",
        "expected_ids": ["ZEPHYR_KERNEL_OOPS"],
        "allowed_extra_ids": [],
        "expected_exit": 0,
        "expected_category_counts": {"software": 1, "hardware": 0, "architecture": 0},
    },
    {
        "log": "bad_stack_overflow.log",
        "expected_ids": ["STACK_OVERFLOW"],
        "allowed_extra_ids": ["HARDFAULT"],
        "expected_exit": 0,
        "expected_category_counts": {"software": 2, "hardware": 0, "architecture": 1},
    },
    {
        "log": "bad_nvs_flash_full.log",
        "expected_ids": ["FLASH_NVS_FULL"],
        "allowed_extra_ids": [],
        "expected_exit": 0,
        "expected_category_counts": {"software": 1, "hardware": 0, "architecture": 0},
    },
    {
        "log": "bad_wifi_reconnect_storm.log",
        "expected_ids": ["NETWORK_RECONNECT_STORM"],
        "allowed_extra_ids": [],
        "expected_exit": 0,
        "expected_category_counts": {"software": 0, "hardware": 0, "architecture": 1},
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
        "allowed_extra_ids": ["WDT_RESET"],
        "expected_exit": 0,
        "expected_category_counts": {"software": 1, "hardware": 0, "architecture": 2},
    },
]


def _load_route_ids() -> tuple[set[str], list[str]]:
    """Load symptom IDs from route metadata for cross-checking matrix expectations."""
    try:
        payload = json.loads(ROUTES_FILE.read_text(encoding="utf-8"))
    except OSError as exc:
        return set(), [f"failed to read route metadata: {exc}"]
    except json.JSONDecodeError as exc:
        return set(), [f"routes metadata JSON parse error: {exc}"]

    symptoms = payload.get("symptoms")
    if not isinstance(symptoms, list):
        return set(), ["routes metadata payload missing top-level symptoms list"]

    ids: set[str] = set()
    for item in symptoms:
        if not isinstance(item, dict):
            continue
        sid = item.get("id")
        if isinstance(sid, str):
            ids.add(sid)
    if not ids:
        return set(), ["routes metadata contains no valid ids"]
    return ids, []


def _run_triage_cli(log_path: Path) -> dict:
    """Run log_triage.py and return normalized result fields."""
    cmd = [
        sys.executable,
        str(TOOLS / "log_triage.py"),
        "--log",
        str(log_path),
        "--platform",
        "esp32",
        "--json",
    ]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            cwd=str(ROOT),
            env={**os.environ, "PYTHONUTF8": "1"},
        )
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            data = {}
        return {
            "exit_code": proc.returncode,
            "data": data,
            "has_invalid_chars": "\\ufffd" in stdout,
            "stdout": stdout,
            "stderr": stderr,
        }
    except subprocess.TimeoutExpired:
        return {"exit_code": -1, "data": {}, "has_invalid_chars": False, "stdout": "timeout", "stderr": ""}


def _iter_symptom_ids(result: dict) -> set[str]:
    ids: set[str] = set()
    for key in ("software_suspicions", "hardware_suspicions", "architecture_refactor_candidates"):
        for item in result.get(key, []):
            sid = item.get("symptom_id") if isinstance(item, dict) else None
            if isinstance(sid, str):
                ids.add(sid)
    return ids


def check_all() -> dict:
    """Run all matrix cases and collect per-case pass/fail details."""
    valid_route_ids, route_load_errors = _load_route_ids()
    results = []
    all_passed = True

    for case in MATRIX:
        log_path = LOGS_DIR / case["log"]
        errors: list[str] = []

        if route_load_errors:
            errors.extend(route_load_errors)

        if not isinstance(case.get("expected_ids"), list):
            errors.append("expected_ids must be a list")
        if not isinstance(case.get("allowed_extra_ids"), list):
            errors.append("allowed_extra_ids must be a list")

        if not log_path.exists():
            errors.append(f"missing log file: {case['log']}")
            results.append({"log": case["log"], "passed": False, "errors": errors, "exit_code": -1, "symptoms": []})
            all_passed = False
            continue

        # Ensure matrix entries reference known routes.
        for key in ("expected_ids", "allowed_extra_ids"):
            for symptom_id in case.get(key, []) if isinstance(case.get(key), list) else []:
                if symptom_id and symptom_id not in valid_route_ids:
                    errors.append(f"{key[:-1]} refers to unknown symptom id: {symptom_id}")

        cli = _run_triage_cli(log_path)

        expected_exit = case.get("expected_exit", 0)
        if cli["exit_code"] != expected_exit:
            errors.append(f"exit_code={cli['exit_code']} expected={expected_exit}")

        if cli["has_invalid_chars"]:
            errors.append("stdout contains replacement characters; possible encoding issue")

        data = cli["data"]
        if not isinstance(data, dict) or not data:
            errors.append("JSON parse failed")
            if cli["stdout"]:
                errors.append(f"stdout preview: {cli['stdout'][:240]}")
            if cli["stderr"]:
                errors.append(f"stderr: {cli['stderr'][:240]}")
            results.append({"log": case["log"], "passed": False, "errors": errors, "exit_code": cli["exit_code"], "symptoms": []})
            all_passed = False
            continue

        all_ids = _iter_symptom_ids(data)

        expected = set(case.get("expected_ids", []))
        allowed_extra = set(case.get("allowed_extra_ids", []))
        allowed_all = expected | allowed_extra

        missing = expected - all_ids
        if missing:
            errors.append(f"expected symptoms missing: {sorted(missing)}")

        unexpected = all_ids - allowed_all
        if unexpected:
            errors.append(f"unexpected symptoms: {sorted(unexpected)}")

        for forbidden_id in case.get("forbidden_ids", []):
            if forbidden_id in all_ids:
                errors.append(f"forbidden symptom found: {forbidden_id}")

        for category, expected_count in case.get("expected_category_counts", {}).items():
            key = {
                "software": "software_suspicions",
                "hardware": "hardware_suspicions",
                "architecture": "architecture_refactor_candidates",
            }.get(category, category)
            value = data.get(key)
            actual = len(value) if isinstance(value, list) else 0
            if actual != expected_count:
                errors.append(f"{category} count={actual} expected={expected_count}")

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
        "passed_count": sum(1 for result in results if result["passed"]),
        "results": results,
    }


def main() -> int:
    result = check_all()
    if "--json" in sys.argv:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"Log Triage Matrix: {result['passed_count']}/{result['total']} passed")
        for row in result["results"]:
            icon = "[PASS]" if row["passed"] else "[FAIL]"
            print(f"  {icon} {row['log']}: exit={row['exit_code']} symptoms={row['symptoms']}")
            if row["errors"]:
                for error in row["errors"]:
                    print(f"    - {error}")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())