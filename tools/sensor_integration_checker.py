#!/usr/bin/env python3
"""
C45 sensor-integration contract heuristic checker.

Checks:
  C45.1 sensor init/probe should verify identity/register map evidence
  C45.2 I2C/SPI transactions should be bounded by timeout/retry/backoff
  C45.3 data-ready polling should be interrupt/event driven or bounded
  C45.4 samples should carry timestamp, units/range/scale, and calibration context
  C45.5 calibration/self-test/warm-up must stay out of the hot read path

Usage:
    python tools/sensor_integration_checker.py <file.c> [file2.c ...]
    python tools/sensor_integration_checker.py --dir src/
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from static_c_scan import collect_c_like_files, extract_functions, line_at, make_issue, nearby, strip_comments


SENSOR_RE = re.compile(
    r"(sensor|imu|accel|gyro|mag|baro|pressure|humidity|temperature|therm|tof|proximity|"
    r"light|als|adc|adc_|motion|env_)",
    re.IGNORECASE,
)
INIT_RE = re.compile(r"(init|probe|start|configure|config|open)", re.IGNORECASE)
READ_RE = re.compile(r"(read|sample|fetch|get|poll|measure|capture|callback|isr)", re.IGNORECASE)
BUS_RE = re.compile(
    r"\b(?:i2c|spi|twi|sensor_bus|regmap)_[A-Za-z0-9_]*(?:read|write|transfer|transmit|receive|recv|send|xfer)[A-Za-z0-9_]*\s*\(",
    re.IGNORECASE,
)
TIMEOUT_RE = re.compile(r"(timeout|deadline|pdMS_TO_TICKS|retry|backoff|bounded|TRY_|WAIT_MS)", re.IGNORECASE)
FOREVER_RE = re.compile(r"\b(?:portMAX_DELAY|WAIT_FOREVER|osWaitForever|HAL_MAX_DELAY)\b", re.IGNORECASE)
WHOAMI_RE = re.compile(r"(WHO_AM_I|WHOAMI|chip_id|device_id|product_id|part_id|probe|verify|identity)", re.IGNORECASE)
REGMAP_RE = re.compile(r"(datasheet|regmap|register_map|register map|rev\s*[A-Z0-9])", re.IGNORECASE)
READY_LOOP_RE = re.compile(
    r"\b(?:while|for)\s*\([^)]*(?:ready|drdy|data_rdy|status|fifo|int_status|conversion)[^)]*\)",
    re.IGNORECASE,
)
WAIT_EVIDENCE_RE = re.compile(r"(xTaskNotifyWait|xSemaphoreTake|xQueueReceive|ulTaskNotifyTake|vTaskDelay|timeout|deadline)", re.IGNORECASE)
SAMPLE_TIME_RE = re.compile(r"(timestamp|time_us|time_ms|tick)", re.IGNORECASE)
SAMPLE_UNIT_RE = re.compile(r"(unit|units|scale|range|full_scale)", re.IGNORECASE)
CALIB_HOT_RE = re.compile(r"(calibrat|calib_|self_test|selftest|warmup|trim|offset_learn)", re.IGNORECASE)


def issue(path: Path, line: int, cid: str, severity: str, msg: str) -> dict[str, str]:
    return make_issue(path, line, cid, severity, msg)


def is_sensor_function(name: str, body: str, path: Path) -> bool:
    joined = f"{path.name} {name} {body[:500]}"
    return bool(SENSOR_RE.search(joined) or BUS_RE.search(body))


def function_line(func: dict[str, object]) -> int:
    return int(func.get("line", 1))


def check_function(path: Path, raw_text: str, code: str, func: dict[str, object]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    name = str(func["name"])
    body = str(func["body"])
    line = function_line(func)
    if not is_sensor_function(name, body, path):
        return issues

    body_has_bus = bool(BUS_RE.search(body))
    context = nearby(raw_text, raw_text.find(name), before=320, after=520)

    if INIT_RE.search(name) and body_has_bus:
        if not WHOAMI_RE.search(body):
            issues.append(issue(path, line, "C45.1", "P0", f"{name} initializes a sensor without identity/probe verification"))
        if not REGMAP_RE.search(context):
            issues.append(issue(path, line, "C45.1", "P1", f"{name} lacks nearby datasheet/register-map evidence for sensor registers"))

    if body_has_bus:
        if FOREVER_RE.search(body):
            issues.append(issue(path, line, "C45.2", "P0", f"{name} uses an unbounded wait for a sensor bus transaction"))
        if not TIMEOUT_RE.search(body):
            issues.append(issue(path, line, "C45.2", "P0", f"{name} performs sensor I2C/SPI transactions without timeout/retry evidence"))

    if READY_LOOP_RE.search(body) and not WAIT_EVIDENCE_RE.search(body):
        issues.append(issue(path, line, "C45.3", "P1", f"{name} polls data-ready/status without bounded wait or event evidence"))

    if READ_RE.search(name) and body_has_bus and not (SAMPLE_TIME_RE.search(body) and SAMPLE_UNIT_RE.search(body)):
        issues.append(issue(path, line, "C45.4", "P1", f"{name} reads sensor data without timestamp/unit/range/scale/calibration metadata"))

    if READ_RE.search(name) and CALIB_HOT_RE.search(body):
        issues.append(issue(path, line, "C45.5", "P2", f"{name} performs calibration/self-test/warm-up work in the hot read path"))

    return issues


def check_file(path: Path) -> list[dict[str, str]]:
    try:
        raw_text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    code = strip_comments(raw_text)
    functions = extract_functions(code)
    issues: list[dict[str, str]] = []
    for func in functions:
        issues.extend(check_function(path, raw_text, code, func))

    if BUS_RE.search(code) and not functions:
        issues.append(issue(path, line_at(code, BUS_RE.search(code).start()), "C45.2", "P0", "sensor bus transaction appears outside a parseable function"))
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="C45 sensor-integration contract checker")
    parser.add_argument("files", nargs="*", help="C/C++ files to check")
    parser.add_argument("--dir", "-d", help="Directory to scan recursively")
    args = parser.parse_args()

    targets = collect_c_like_files(args.files, args.dir)
    if not targets:
        print("[sensor_integration_checker] no files to check")
        return 0

    all_issues: list[dict[str, str]] = []
    for path in targets:
        all_issues.extend(check_file(path))

    if not all_issues:
        print(f"[sensor_integration_checker] checked {len(targets)} files, no C45 warnings")
        return 0

    print(f"[sensor_integration_checker] checked {len(targets)} files, found {len(all_issues)} C45 warnings:\n")
    for item in all_issues:
        print(f"  [{item['severity']}] {item['id']} - {item['file']} - {item['issue']}")
    print(f"\nSummary: {len(all_issues)} C45 sensor-integration warnings")
    return 1


if __name__ == "__main__":
    sys.exit(main())
