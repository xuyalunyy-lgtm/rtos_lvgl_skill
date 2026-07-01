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

from pathlib import Path

from checker_io import make_issue, read_file, run_checker

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
                issues.append(make_issue(
                    path, i, "C21.1", "P0",
                    f"{api} 前未见状态保存（nvs_set_* / nvs_commit）",
                ))

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
                issues.append(make_issue(
                    path, i, "C21.4", "P1",
                    f"{api} 前未见外设断电（LCD/音频/WiFi）",
                ))

    return issues


def check_file(path: Path) -> list[dict]:
    result = read_file(path)
    if result is None:
        return []

    lines, _text = result
    issues = []
    issues.extend(check_state_save_before_sleep(path, lines))
    issues.extend(check_power_down_before_sleep(path, lines))
    return issues


if __name__ == "__main__":
    raise SystemExit(run_checker(check_file, "C21 低功耗管理检查器", ("C21",)))
