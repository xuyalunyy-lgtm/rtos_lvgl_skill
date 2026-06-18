#!/usr/bin/env python3
"""
C21 低功耗管理启发式检查器。

检查项:
  C21.1 — 深度睡眠前必须保存状态到 NVS/Flash
  C21.4 — 深度睡眠前必须关闭外设电源

用法:
    python tools/low_power_checker.py <file.c> [file2.c ...]
    python tools/low_power_checker.py --dir src/
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Deep sleep entry APIs
DEEP_SLEEP_APIS = [
    "esp_deep_sleep_start",
    "esp_deep_sleep",
    "esp_light_sleep_start",
    "HAL_PWR_EnterSTOPMode",
    "HAL_PWR_EnterSTANDBYMode",
]

# State save indicators
STATE_SAVE_INDICATORS = [
    "nvs_set_",
    "nvs_commit",
    "flash_write",
    "eeprom_write",
    "HAL_FLASH_Program",
]

# Power down indicators — specific shutdown functions only
POWER_DOWN_INDICATORS = [
    "esp_wifi_stop",
    "esp_wifi_deinit",
    "i2s_channel_disable",
    "i2s_del_channel",
    "ledc_stop",
    "ledc_set_duty.*0",  # PWM duty = 0
    "spi_bus_free",
    "i2c_driver_delete",
    "gpio_hold_en",
    "power_down_peripherals",
]


def check_state_save_before_sleep(path: Path, lines: list[str]) -> list[dict]:
    """C21.1 — deep_sleep 前必须有状态保存"""
    issues = []

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("/*"):
            continue

        for api in DEEP_SLEEP_APIS:
            if api + "(" not in stripped and api + "()" not in stripped:
                continue

            # Check previous 20 lines for state save
            has_state_save = False
            for j in range(max(0, i - 20), i):
                prev_line = lines[j]
                if any(indicator in prev_line for indicator in STATE_SAVE_INDICATORS):
                    has_state_save = True
                    break

            if not has_state_save:
                issues.append({
                    "id": "C21.1",
                    "file": f"{path}:{i}",
                    "issue": f"{api} 前未见状态保存（nvs_set_* / nvs_commit）",
                    "severity": "P0",
                })

    return issues


def check_power_down_before_sleep(path: Path, lines: list[str]) -> list[dict]:
    """C21.4 — deep_sleep 前必须关闭外设电源"""
    issues = []

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("/*"):
            continue

        for api in DEEP_SLEEP_APIS:
            if api + "(" not in stripped and api + "()" not in stripped:
                continue

            # Check previous 30 lines for power down
            has_power_down = False
            for j in range(max(0, i - 30), i):
                prev_line = lines[j]
                if any(indicator in prev_line for indicator in POWER_DOWN_INDICATORS):
                    has_power_down = True
                    break

            if not has_power_down:
                issues.append({
                    "id": "C21.4",
                    "file": f"{path}:{i}",
                    "issue": f"{api} 前未见外设断电（LCD/音频/WiFi）",
                    "severity": "P1",
                })

    return issues


def check_file(path: Path) -> list[dict]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    lines = text.splitlines()
    issues = []
    issues.extend(check_state_save_before_sleep(path, lines))
    issues.extend(check_power_down_before_sleep(path, lines))
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="C21 低功耗管理检查器")
    parser.add_argument("files", nargs="*", help="待检查 .c 文件")
    parser.add_argument("--dir", "-d", help="递归检查目录")
    args = parser.parse_args()

    targets: list[Path] = []
    for f in args.files:
        p = Path(f)
        if p.is_file():
            targets.append(p)
        elif p.is_dir():
            targets.extend(sorted(p.rglob("*.c")))

    if args.dir:
        d = Path(args.dir)
        if d.is_dir():
            targets.extend(sorted(d.rglob("*.c")))

    seen: set[Path] = set()
    unique: list[Path] = []
    for t in targets:
        r = t.resolve()
        if r not in seen:
            seen.add(r)
            unique.append(r)

    if not unique:
        print("[low_power_checker] 无文件可检查")
        return 0

    all_issues: list[dict] = []
    for path in unique:
        all_issues.extend(check_file(path))

    if not all_issues:
        print(f"[low_power_checker] 已检查 {len(unique)} 个文件，未发现 C21 违规")
        return 0

    print(f"[low_power_checker] 已检查 {len(unique)} 个文件，发现 {len(all_issues)} 个 C21 告警:\n")
    for issue in all_issues:
        print(f"  [{issue['severity']}] {issue['id']} — {issue['file']} — {issue['issue']}")

    print(f"\nSummary: {len(all_issues)} C21 low-power warnings")
    return 1


if __name__ == "__main__":
    sys.exit(main())
