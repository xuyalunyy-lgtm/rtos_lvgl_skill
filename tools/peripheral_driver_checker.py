#!/usr/bin/env python3
"""
C18 外设驱动安全启发式检查器。

检查项:
  C18.1 — GPIO 方向必须在使用前配置（gpio_config 先于 gpio_set_level）
  C18.2 — I2C 设备地址禁止硬编码猜测（须来自 datasheet）
  C18.4 — DMA 通道分配须文档化

用法:
    python tools/peripheral_driver_checker.py <file.c> [file2.c ...]
    python tools/peripheral_driver_checker.py --dir src/
"""

from __future__ import annotations

import re
from pathlib import Path

from checker_io import make_issue, read_file, run_checker
from sdk_lookup import SdkLookup

lookup = SdkLookup("esp32")

_GPIO_SET_APIS = lookup.get_apis("GPIO_SET")
_GPIO_CONFIG_APIS = lookup.get_apis("GPIO_CONFIG")
_I2C_TRANSFER_APIS = lookup.get_apis("I2C_TRANSFER")

_GPIO_SET_RE = re.compile(r"(?:" + "|".join(re.escape(a) for a in _GPIO_SET_APIS) + r")\s*\(\s*(\w+)")
_GPIO_CONFIG_RE = re.compile(
    r"(?:" + "|".join(re.escape(a) for a in _GPIO_CONFIG_APIS) + r")|gpio_reset_pin"
)
_I2C_TRANSFER_RE = re.compile(
    r"(?:" + "|".join(re.escape(a) for a in _I2C_TRANSFER_APIS) + r")\s*\([^)]*"
    r"(?:0x[0-9a-fA-F]{2})\s*[,)]"
)


def check_gpio_config_before_use(path: Path, lines: list[str]) -> list[dict]:
    """C18.1 — gpio_set_level 前须有 gpio_config"""
    issues = []
    gpio_set_calls = []
    gpio_config_calls = []

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("/*"):
            continue
        if any(api in stripped for api in _GPIO_SET_APIS):
            # Extract pin
            m = _GPIO_SET_RE.search(stripped)
            if m:
                gpio_set_calls.append((i, m.group(1)))
        if _GPIO_CONFIG_RE.search(stripped):
            gpio_config_calls.append(i)

    # Check if gpio_set_level appears before any gpio_config
    if gpio_set_calls and not gpio_config_calls:
        for line_no, pin in gpio_set_calls[:3]:  # Report first 3
            issues.append(make_issue(path, line_no, "C18.1", "P0",
                f"gpio_set_level({pin}) 未见 gpio_config 配置方向"))
    elif gpio_set_calls and gpio_config_calls:
        first_config = min(gpio_config_calls)
        for line_no, pin in gpio_set_calls:
            if line_no < first_config:
                issues.append(make_issue(path, line_no, "C18.1", "P0",
                    f"gpio_set_level({pin}) 在 gpio_config 之前调用"))

    return issues


def check_i2c_hardcoded_address(path: Path, lines: list[str]) -> list[dict]:
    """C18.2 — I2C 地址禁止硬编码（须用宏或配置）"""
    issues = []

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("/*"):
            continue
        if _I2C_TRANSFER_RE.search(stripped):
            # Check if it's using a macro (all caps + underscore)
            addr_match = re.search(r"(0x[0-9a-fA-F]{2})", stripped)
            if addr_match:
                # Check context: if it's a #define, skip
                if "#define" in stripped:
                    continue
                # Check if using a named constant
                before_addr = stripped[:stripped.index(addr_match.group(1))]
                if not re.search(r"[A-Z_]{3,}\s*,\s*$", before_addr):
                    issues.append(make_issue(path, i, "C18.2", "P1",
                        f"I2C 地址硬编码 {addr_match.group(1)}，须用 datasheet 定义的宏"))

    return issues


def check_dma_channel_docs(path: Path, lines: list[str]) -> list[dict]:
    """C18.4 — DMA 通道分配须文档化"""
    issues = []
    dma_pattern = re.compile(r"DMA\s*CHANNEL\s*(\d+)|dma_ch(?:annel)?\s*=\s*(\d+)", re.IGNORECASE)

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("/*"):
            continue
        if dma_pattern.search(stripped):
            # Check if there's a comment explaining the channel
            if "//" not in stripped and "/*" not in stripped:
                # Check previous line for comment
                prev_line = lines[i - 2].strip() if i >= 2 else ""
                if not (prev_line.startswith("//") or prev_line.startswith("/*")):
                    issues.append(make_issue(path, i, "C18.4", "P1",
                        "DMA 通道分配缺少注释说明用途"))

    return issues


def check_file(path: Path) -> list[dict]:
    result = read_file(path)
    if result is None:
        return []

    lines, text = result
    issues = []
    issues.extend(check_gpio_config_before_use(path, lines))
    issues.extend(check_i2c_hardcoded_address(path, lines))
    issues.extend(check_dma_channel_docs(path, lines))
    return issues


if __name__ == "__main__":
    raise SystemExit(run_checker(check_file, "C18 外设驱动安全检查器", ("C18",)))
