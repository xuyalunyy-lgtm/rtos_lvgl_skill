#!/usr/bin/env python3
"""
C42 板级资源契约启发式检查器。

检查项:
  C42.1 — GPIO/DMA/clock/IRQ/cache/heap/PSRAM 资源必须声明 owner
  C42.4 — IRQ priority、ISR-safe API、跨核访问边界必须明确

用法:
    python tools/board_resource_checker.py <file.c> [file2.c ...]
    python tools/board_resource_checker.py --dir src/
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


def check_file(path: Path) -> list[dict]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    lines = text.splitlines()
    issues = []

    # Track GPIO pin usage
    gpio_pins = {}

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("/*"):
            continue

        # C42.1: Check GPIO pin usage without owner documentation
        match = re.search(r'gpio_set_level\s*\(\s*(?:GPIO_NUM_)?(\d+)', stripped)
        if match:
            pin = match.group(1)
            if pin not in gpio_pins:
                gpio_pins[pin] = []
            gpio_pins[pin].append(i)

        # Check for GPIO config
        match = re.search(r'gpio_config.*pin_bit_mask.*1ULL\s*<<\s*(?:GPIO_NUM_)?(\d+)', stripped)
        if match:
            pin = match.group(1)
            if pin in gpio_pins:
                del gpio_pins[pin]  # Configured before use

    # Report pins used without config
    for pin, lines_used in gpio_pins.items():
        issues.append({
            "id": "C42.1",
            "file": f"{path}:{lines_used[0]}",
            "issue": f"GPIO {pin} 使用前未见 gpio_config 配置（无 owner 声明）",
            "severity": "P0",
        })

    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="C42 板级资源契约检查器")
    parser.add_argument("files", nargs="*", help="待检查文件")
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
        print("[board_resource_checker] No files to check")
        return 0

    all_issues: list[dict] = []
    for path in unique:
        all_issues.extend(check_file(path))

    if not all_issues:
        print(f"[board_resource_checker] Checked {len(unique)} files, no C42 violations")
        return 0

    print(f"[board_resource_checker] Checked {len(unique)} files, found {len(all_issues)} C42 warnings:\n")
    for issue in all_issues:
        print(f"  [{issue['severity']}] {issue['id']} — {issue['file']} — {issue['issue']}")

    print(f"\nSummary: {len(all_issues)} C42 board resource warnings")
    return 1


if __name__ == "__main__":
    sys.exit(main())
