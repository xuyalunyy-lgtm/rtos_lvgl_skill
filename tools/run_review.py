#!/usr/bin/env python3
"""
一键静态审查：串联 Skill 内 checker 脚本。

用法:
    python tools/run_review.py --dir ./src --platform jl
    python tools/run_review.py --dir ./examples --platform freertos
    python tools/run_review.py --self-test
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
FIXTURES_DIR = TOOLS_DIR / "fixtures"
SKILL_ROOT = TOOLS_DIR.parent


def is_bad_example(path: Path) -> bool:
    return path.name.startswith("bad_")


def collect_c_files(
    targets: list[str],
    dir_path: str | None,
    *,
    include_bad: bool,
) -> list[Path]:
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
    seen: set[Path] = set()
    out: list[Path] = []
    for f in files:
        f = f.resolve()
        if f in seen:
            continue
        seen.add(f)
        if not include_bad and is_bad_example(f):
            continue
        out.append(f)
    return out


def run_cmd(label: str, argv: list[str]) -> int:
    print(f"\n{'=' * 60}\n[{label}]\n{'=' * 60}")
    print(" ", " ".join(str(a) for a in argv))
    proc = subprocess.run(argv, cwd=SKILL_ROOT)
    return proc.returncode


def run_checker(script: str, checker_args: list[str]) -> int:
    argv = [sys.executable, str(TOOLS_DIR / script), *checker_args]
    proc = subprocess.run(argv, cwd=SKILL_ROOT, capture_output=True, text=True)
    if proc.stdout:
        print(proc.stdout, end="")
    if proc.stderr:
        print(proc.stderr, end="", file=sys.stderr)
    return proc.returncode


def run_self_test() -> int:
    cases = [
        ("cjson_leak_checker.py", [str(FIXTURES_DIR / "good_cjson.c")], 0),
        ("cjson_leak_checker.py", [str(FIXTURES_DIR / "bad_cjson.c")], 1),
        ("isr_safety_checker.py", [str(FIXTURES_DIR / "good_isr.c")], 0),
        ("isr_safety_checker.py", [str(FIXTURES_DIR / "bad_isr.c")], 1),
        ("lvgl_thread_checker.py", [str(FIXTURES_DIR / "ui_view_good.c")], 0),
        ("lvgl_thread_checker.py", [str(FIXTURES_DIR / "network_wss_bad.c")], 1),
    ]

    print("=" * 60)
    print("run_review.py — checker fixtures 自测")
    print("=" * 60)

    failed = 0
    for script, cargs, expected in cases:
        rc = run_checker(script, cargs)
        ok = rc == expected
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {script} {' '.join(cargs)} → exit {rc} (期望 {expected})")
        if not ok:
            failed += 1

    print(f"\n{'=' * 60}")
    if failed == 0:
        print("Self-test: 全部通过")
    else:
        print(f"Self-test: {failed} 项失败")
    print(f"{'=' * 60}\n")
    return 1 if failed else 0


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
    parser.add_argument(
        "--include-bad",
        action="store_true",
        help="包含 bad_*.c 反例（默认排除）",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="运行 tools/fixtures/ 自测并退出",
    )
    parser.add_argument("--skip-stack", action="store_true")
    parser.add_argument("--skip-cjson", action="store_true")
    parser.add_argument("--skip-isr", action="store_true")
    parser.add_argument("--skip-lvgl", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    c_files = collect_c_files(args.files, args.dir, include_bad=args.include_bad)
    review_root = args.dir or (str(c_files[0].parent) if c_files else ".")

    skipped_bad = 0
    if args.dir and not args.include_bad:
        root = Path(args.dir)
        if root.is_dir():
            skipped_bad = sum(1 for f in root.rglob("*.c") if is_bad_example(f.resolve()))

    exit_code = 0

    if skipped_bad:
        print(f"[info] 已排除 {skipped_bad} 个 bad_*.c 反例（加 --include-bad 可纳入）")

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
            rc = run_cmd(
                "cjson_leak_checker",
                [sys.executable, str(TOOLS_DIR / "cjson_leak_checker.py"), str(f)],
            )
            exit_code = max(exit_code, rc)
    elif not args.skip_cjson:
        print("\n[skip] cjson_leak_checker: 无 .c 文件")

    if not args.skip_isr and c_files:
        for f in c_files:
            rc = run_cmd(
                "isr_safety_checker",
                [sys.executable, str(TOOLS_DIR / "isr_safety_checker.py"), str(f)],
            )
            exit_code = max(exit_code, rc)
    elif not args.skip_isr:
        print("\n[skip] isr_safety_checker: 无 .c 文件")

    if not args.skip_lvgl and c_files:
        for f in c_files:
            rc = run_cmd(
                "lvgl_thread_checker",
                [sys.executable, str(TOOLS_DIR / "lvgl_thread_checker.py"), str(f)],
            )
            exit_code = max(exit_code, rc)
    elif not args.skip_lvgl:
        print("\n[skip] lvgl_thread_checker: 无 .c 文件")

    if not c_files and args.dir:
        print("\n[warn] 排除 bad_*.c 后无可审查文件")

    print(f"\n{'=' * 60}")
    if exit_code == 0:
        print("Summary: 全部 checker 通过（启发式，仍需人工 review）")
    else:
        print(f"Summary: 存在告警/失败 (exit={exit_code})，请人工核对")
    print(f"{'=' * 60}\n")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
