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

import argparse
import re
import sys
from pathlib import Path


def check_gpio_config_before_use(path: Path, lines: list[str]) -> list[dict]:
    """C18.1 — gpio_set_level 前须有 gpio_config"""
    issues = []
    gpio_set_calls = []
    gpio_config_calls = []

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("/*"):
            continue
        if "gpio_set_level" in stripped:
            # Extract pin
            m = re.search(r"gpio_set_level\s*\(\s*(\w+)", stripped)
            if m:
                gpio_set_calls.append((i, m.group(1)))
        if "gpio_config" in stripped or "gpio_reset_pin" in stripped or "gpio_set_direction" in stripped:
            gpio_config_calls.append(i)

    # Check if gpio_set_level appears before any gpio_config
    if gpio_set_calls and not gpio_config_calls:
        for line_no, pin in gpio_set_calls[:3]:  # Report first 3
            issues.append({
                "id": "C18.1",
                "file": f"{path}:{line_no}",
                "issue": f"gpio_set_level({pin}) 未见 gpio_config 配置方向",
                "severity": "P0",
            })
    elif gpio_set_calls and gpio_config_calls:
        first_config = min(gpio_config_calls)
        for line_no, pin in gpio_set_calls:
            if line_no < first_config:
                issues.append({
                    "id": "C18.1",
                    "file": f"{path}:{line_no}",
                    "issue": f"gpio_set_level({pin}) 在 gpio_config 之前调用",
                    "severity": "P0",
                })

    return issues


def check_i2c_hardcoded_address(path: Path, lines: list[str]) -> list[dict]:
    """C18.2 — I2C 地址禁止硬编码（须用宏或配置）"""
    issues = []
    # Pattern: i2c_master_write/read with literal hex address
    i2c_pattern = re.compile(
        r"i2c_master_(?:write|read|write_read|transmit)\s*\([^)]*"
        r"(?:0x[0-9a-fA-F]{2})\s*[,)]"
    )

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("/*"):
            continue
        if i2c_pattern.search(stripped):
            # Check if it's using a macro (all caps + underscore)
            addr_match = re.search(r"(0x[0-9a-fA-F]{2})", stripped)
            if addr_match:
                # Check context: if it's a #define, skip
                if "#define" in stripped:
                    continue
                # Check if using a named constant
                before_addr = stripped[:stripped.index(addr_match.group(1))]
                if not re.search(r"[A-Z_]{3,}\s*,\s*$", before_addr):
                    issues.append({
                        "id": "C18.2",
                        "file": f"{path}:{i}",
                        "issue": f"I2C 地址硬编码 {addr_match.group(1)}，须用 datasheet 定义的宏",
                        "severity": "P1",
                    })

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
                    issues.append({
                        "id": "C18.4",
                        "file": f"{path}:{i}",
                        "issue": "DMA 通道分配缺少注释说明用途",
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
    issues.extend(check_gpio_config_before_use(path, lines))
    issues.extend(check_i2c_hardcoded_address(path, lines))
    issues.extend(check_dma_channel_docs(path, lines))
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="C18 外设驱动安全检查器")
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
        print("[peripheral_driver_checker] 无文件可检查")
        return 0

    all_issues: list[dict] = []
    for path in unique:
        all_issues.extend(check_file(path))

    if not all_issues:
        print(f"[peripheral_driver_checker] 已检查 {len(unique)} 个文件，未发现 C18 违规")
        return 0

    print(f"[peripheral_driver_checker] 已检查 {len(unique)} 个文件，发现 {len(all_issues)} 个 C18 告警:\n")
    for issue in all_issues:
        print(f"  [{issue['severity']}] {issue['id']} — {issue['file']} — {issue['issue']}")

    print(f"\nSummary: {len(all_issues)} C18 peripheral-driver warnings")
    return 1


if __name__ == "__main__":
    sys.exit(main())
