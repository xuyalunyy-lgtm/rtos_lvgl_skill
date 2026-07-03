#!/usr/bin/env python3
"""
C42 板级资源契约启发式检查器。

检查项:
  C42.1 — GPIO 使用前必须 gpio_config 配置

用法:
    python tools/board_resource_checker.py <file.c> [file2.c ...]
    python tools/board_resource_checker.py --dir src/
"""

from __future__ import annotations

import re
from pathlib import Path

from checker_io import make_issue, read_file, run_checker
from sdk_lookup import SdkLookup

lookup = SdkLookup("esp32")

_GPIO_SET_APIS = "|".join(re.escape(a) for a in lookup.get_apis("GPIO_SET"))
_GPIO_CONFIG_APIS = "|".join(re.escape(a) for a in lookup.get_apis("GPIO_CONFIG"))

GPIO_SET_RE = re.compile(rf'(?:{_GPIO_SET_APIS})\s*\(\s*(?:GPIO_NUM_)?(\d+)')
GPIO_CONFIG_RE = re.compile(rf'(?:{_GPIO_CONFIG_APIS}).*pin_bit_mask.*1ULL\s*<<\s*(?:GPIO_NUM_)?(\d+)')


def check_file(path: Path) -> list[dict]:
    result = read_file(path)
    if result is None:
        return []

    lines, text = result
    issues = []
    gpio_pins = {}

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("/*"):
            continue

        match = GPIO_SET_RE.search(stripped)
        if match:
            pin = match.group(1)
            if pin not in gpio_pins:
                gpio_pins[pin] = []
            gpio_pins[pin].append(i)

        cfg_match = GPIO_CONFIG_RE.search(stripped)
        if cfg_match:
            pin = cfg_match.group(1)
            if pin in gpio_pins:
                del gpio_pins[pin]

    for pin, lines_used in gpio_pins.items():
        issues.append(make_issue(path, lines_used[0], "C42.1", "P0",
            f"GPIO {pin} used without gpio_config (no owner declaration)"))

    return issues


if __name__ == "__main__":
    raise SystemExit(run_checker(check_file, "C42 板级资源检查器", ("C42",)))
