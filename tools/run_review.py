#!/usr/bin/env python3
"""
一键静态审查：串联 Skill 内 checker 脚本。

用法:
    python tools/run_review.py --dir ./src --platform jl
    python tools/run_review.py file1.c file2.c --platform esp32
    python tools/run_review.py --dir ./src --platform stm32 --describe "WSS TLS LVGL"
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent


def collect_c_files(targets: list[str], dir_path: str | None) -> list[Path]:
    files: list[Path] = []
    for t in targets:
        p = Path(t)
        if p.is_file() and p.suffix.lower() in (".c", ".h", ".cpp"):
            files.append(p.resolve())
        elif p.is_dir():
            files.extend(sorted(p.rglob("*.c")))
            files.extend(sorted(p.rglob("*.cpp")))
    if dir_path:
        root = Path(dir_path)
        if root.is_dir():
            files.extend(sorted(root.rglob("*.c")))
            files.extend(sorted(root.rglob("*.cpp")))
    # dedupe preserve order
    seen: set[Path] = set()
    out: list[Path] = []
    for f in files:
        if f not in seen:
            seen.add(f)
            out.append(f)
    return out


def run_cmd(label: str, argv: list[str]) -> int:
    print(f"\n{'=' * 60}\n[{label}]\n{'=' * 60}")
    print(" ", " ".join(str(a) for a in argv))
    proc = subprocess.run(argv, cwd=TOOLS_DIR.parent)
    return proc.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="FreeRTOS Skill 一键静态审查")
    parser.add_argument("files", nargs="*", help="待审查 .c 文件")
    parser.add_argument("--dir", "-d", help="递归审查目录下所有 .c")
    parser.add_argument(
        "--platform", "-p", default="freertos",
        choices=["freertos", "esp32", "stm32", "jl", "bk"],
        help="stack_calculator 平台",
    )
    parser.add_argument(
        "--describe",
        default="WSS TLS cJSON LVGL Presenter",
        help="stack_calculator 任务描述",
    )
    parser.add_argument("--skip-stack", action="store_true")
    parser.add_argument("--skip-cjson", action="store_true")
    parser.add_argument("--skip-isr", action="store_true")
    parser.add_argument("--skip-lvgl", action="store_true")
    args = parser.parse_args()

    c_files = collect_c_files(args.files, args.dir)
    review_root = args.dir or (str(c_files[0].parent) if c_files else ".")

    exit_code = 0

    if not args.skip_stack:
        rc = run_cmd(
            "stack_calculator",
            [
                sys.executable,
                str(TOOLS_DIR / "stack_calculator.py"),
                "--describe",
                args.describe,
                "--platform",
                args.platform,
            ],
        )
        exit_code = max(exit_code, rc)

    if not args.skip_cjson and c_files:
        for f in c_files:
            rc = run_cmd("cjson_leak_checker", [sys.executable, str(TOOLS_DIR / "cjson_leak_checker.py"), str(f)])
            exit_code = max(exit_code, rc)
    elif not args.skip_cjson:
        print("\n[skip] cjson_leak_checker: 无 .c 文件")

    if not args.skip_isr:
        rc = run_cmd(
            "isr_safety_checker",
            [sys.executable, str(TOOLS_DIR / "isr_safety_checker.py"), "--dir", review_root],
        )
        exit_code = max(exit_code, rc)

    if not args.skip_lvgl:
        rc = run_cmd(
            "lvgl_thread_checker",
            [sys.executable, str(TOOLS_DIR / "lvgl_thread_checker.py"), review_root],
        )
        exit_code = max(exit_code, rc)

    print(f"\n{'=' * 60}")
    if exit_code == 0:
        print("Summary: 全部 checker 通过（启发式，仍需人工 review）")
    else:
        print(f"Summary: 存在告警/失败 (exit={exit_code})，请人工核对")
    print(f"{'=' * 60}\n")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
