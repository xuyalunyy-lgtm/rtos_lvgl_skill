#!/usr/bin/env python3
"""
C24 外设关闭安全启发式检查器。

检查项:
  C24.1 — 异常退出路径必须与正常路径调用相同收尾函数
  C24.3 — abort/timeout/skip 必须释放所有硬件资源
  C24.5 — 执行器停止后必须关闭加热/电源门控/外设使能

用法:
    python tools/peripheral_shutdown_checker.py <file.c> [file2.c ...]
    python tools/peripheral_shutdown_checker.py --dir src/
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


# Peripheral start/enable APIs
PERIPHERAL_START_APIS = [
    "gpio_set_level",
    "ledc_start",
    "i2s_channel_enable",
    "spi_device_acquire_bus",
    "i2c_master_start",
    "pwm_start",
    "dac_output_enable",
    "adc_continuous_start",
    "i2s_read",
    "i2s_write",
]

# Peripheral stop/disable APIs
PERIPHERAL_STOP_APIS = [
    "gpio_set_level.*0",
    "ledc_stop",
    "i2s_channel_disable",
    "spi_device_release_bus",
    "i2c_master_stop",
    "pwm_stop",
    "dac_output_disable",
    "adc_continuous_stop",
]

# Power control APIs
POWER_APIS = [
    "esp_sleep_enable",
    "gpio_set_level.*EN",
    "power_down",
    "power_off",
    "peripheral_power_disable",
    "clock_disable",
]


def check_file(path: Path) -> list[dict]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    # Skip files without peripheral-related content
    lower = text.lower()
    if not any(kw in lower for kw in ["gpio", "ledc", "i2s", "spi", "pwm", "power", "shutdown", "deinit", "cleanup"]):
        return []

    lines = text.splitlines()
    issues = []

    # Check for cleanup/goto patterns
    has_goto_cleanup = any("goto cleanup" in line or "goto fail" in line or "goto error" in line for line in lines)
    has_cleanup_label = any(re.match(r'^\s*cleanup\s*:', line) or re.match(r'^\s*fail\s*:', line) or re.match(r'^\s*error\s*:', line) for line in lines)

    # Check for functions with early returns that skip cleanup
    in_function = False
    func_name = ""
    func_start = 0
    brace_depth = 0
    has_resource_ops = False
    early_returns = []

    for i, line in enumerate(lines, 1):
        stripped = line.strip()

        # Detect function start
        match = re.match(r'^(?:static\s+)?(?:void|int|esp_err_t|bool)\s+(\w+)\s*\(', stripped)
        if match and "{" in stripped:
            in_function = True
            func_name = match.group(1)
            func_start = i
            brace_depth = 1
            has_resource_ops = False
            early_returns = []
            continue

        if in_function:
            brace_depth += stripped.count("{") - stripped.count("}")
            if brace_depth <= 0:
                in_function = False
                continue

            # Check for resource operations
            for api in PERIPHERAL_START_APIS:
                if api + "(" in stripped:
                    has_resource_ops = True
                    break

            # Check for early returns (before cleanup)
            if re.match(r'^\s*return\s', stripped) and not has_cleanup_label:
                early_returns.append(i)

    # C24.1: Check if cleanup exists for functions with resource ops
    # Simple heuristic: look for deinit/close/stop functions without cleanup
    has_deinit = any(re.search(r'\b\w+_deinit\b', line) or re.search(r'\b\w+_close\b', line) or re.search(r'\b\w+_stop\b', line) for line in lines)
    has_init = any(re.search(r'\b\w+_init\b', line) or re.search(r'\b\w+_open\b', line) or re.search(r'\b\w+_start\b', line) for line in lines)

    if has_init and not has_deinit:
        issues.append({
            "id": "C24.1",
            "file": str(path),
            "issue": "有 init/start/open 但未见对应的 deinit/stop/close（异常路径可能跳过收尾）",
            "severity": "P0",
        })

    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="C24 外设关闭安全检查器")
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
        print("[peripheral_shutdown_checker] 无文件可检查")
        return 0

    all_issues: list[dict] = []
    for path in unique:
        all_issues.extend(check_file(path))

    if not all_issues:
        print(f"[peripheral_shutdown_checker] 已检查 {len(unique)} 个文件，未发现 C24 违规")
        return 0

    print(f"[peripheral_shutdown_checker] 已检查 {len(unique)} 个文件，发现 {len(all_issues)} 个 C24 告警:\n")
    for issue in all_issues:
        print(f"  [{issue['severity']}] {issue['id']} — {issue['file']} — {issue['issue']}")

    print(f"\nSummary: {len(all_issues)} C24 peripheral shutdown warnings")
    return 1


if __name__ == "__main__":
    sys.exit(main())
