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
import os
import subprocess
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
FIXTURES_DIR = TOOLS_DIR / "fixtures"
SKILL_ROOT = TOOLS_DIR.parent


def checker_env() -> dict[str, str]:
    """Windows GBK 控制台下避免 checker emoji 输出触发 UnicodeEncodeError。"""
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    return env


from checker_io import safe_print as _safe_print  # noqa: E402


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
    proc = subprocess.run(
        argv,
        cwd=SKILL_ROOT,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        env=checker_env(),
    )
    if proc.stdout:
        _safe_print(proc.stdout)
    if proc.stderr:
        _safe_print(proc.stderr, file=sys.stderr)
    return proc.returncode


def run_self_test() -> int:
    cases = [
        ("cjson_leak_checker.py", [str(FIXTURES_DIR / "good_cjson.c")], 0),
        ("cjson_leak_checker.py", [str(FIXTURES_DIR / "bad_cjson.c")], 1),
        ("isr_safety_checker.py", [str(FIXTURES_DIR / "good_isr.c")], 0),
        ("isr_safety_checker.py", [str(FIXTURES_DIR / "bad_isr.c")], 1),
        ("lvgl_thread_checker.py", [str(FIXTURES_DIR / "ui_view_good.c")], 0),
        ("lvgl_thread_checker.py", [str(FIXTURES_DIR / "network_wss_bad.c")], 1),
        ("queue_ownership_checker.py", [str(FIXTURES_DIR / "good_queue_heap.c")], 0),
        ("queue_ownership_checker.py", [str(FIXTURES_DIR / "bad_queue_stack.c")], 1),
        ("secret_scan_checker.py", [str(FIXTURES_DIR / "good_config_secrets")], 0),
        ("secret_scan_checker.py", [str(FIXTURES_DIR / "bad_config_secrets")], 1),
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


def run_validate_examples() -> int:
    """铁律范例约束：good_* 须通过，bad_* 须触发对应 checker 失败。"""
    examples = SKILL_ROOT / "examples"
    cases: list[tuple[str, Path, int, str]] = [
        # C1 — LVGL
        ("lvgl_thread_checker.py", examples / "good_mvp_pattern.c", 0, "C1 good"),
        ("lvgl_thread_checker.py", examples / "good_presenter_consumer.c", 0, "C1 good"),
        ("lvgl_thread_checker.py", examples / "bad_lvgl_cross_thread.c", 1, "C1.1 bad"),
        # C2 — Queue
        ("queue_ownership_checker.py", examples / "good_wss_json_parse.c", 0, "C2 good"),
        ("queue_ownership_checker.py", examples / "good_presenter_consumer.c", 0, "C2 good"),
        ("queue_ownership_checker.py", examples / "good_wss_reconnect.c", 0, "C2 good"),
        ("queue_ownership_checker.py", examples / "good_boot_sequence.c", 0, "C2/C8 good"),
        ("queue_ownership_checker.py", examples / "bad_queue_stack_pointer.c", 1, "C2.2 bad"),
        # C3 — cJSON
        ("cjson_leak_checker.py", examples / "good_wss_json_parse.c", 0, "C3 good"),
        ("cjson_leak_checker.py", examples / "bad_cjson_leak.c", 1, "C3.1 bad"),
        # C4 — ISR
        ("isr_safety_checker.py", examples / "bad_isr_blocking.c", 1, "C4.1 bad"),
        # C8 — 启动 (queue checker 对 good_boot_sequence 应通过)
        ("queue_ownership_checker.py", examples / "good_voice_prompt_uplink.c", 0, "C10 good"),
    ]

    print("=" * 60)
    print("run_review.py — examples/ 铁律约束验证")
    print("=" * 60)

    failed = 0
    for script, path, expected, label in cases:
        if not path.is_file():
            print(f"[FAIL] 缺少范例: {path}")
            failed += 1
            continue
        rc = run_checker(script, [str(path)])
        ok = rc == expected
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {label}: {script} {path.name} → exit {rc} (期望 {expected})")
        if not ok:
            failed += 1

    print(f"\n{'=' * 60}")
    if failed == 0:
        print("Validate-examples: 全部通过")
    else:
        print(f"Validate-examples: {failed} 项失败")
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
    parser.add_argument("--skip-queue", action="store_true")
    parser.add_argument("--skip-voice", action="store_true")
    parser.add_argument("--skip-logging", action="store_true")
    parser.add_argument("--skip-return-check", action="store_true")
    parser.add_argument(
        "--validate-examples",
        action="store_true",
        help="验证 examples/ good/bad 与 checker 铁律约束一致",
    )
    parser.add_argument(
        "--scan-secrets",
        action="store_true",
        help="扫描目录内 config/凭证 (C9)，可与 --dir 联用",
    )
    parser.add_argument(
        "--git-remotes",
        action="store_true",
        help="扫描 git remote 内嵌凭证 (C9.2)",
    )
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    if args.validate_examples:
        return run_validate_examples()

    exit_code = 0

    if args.scan_secrets or args.git_remotes:
        secret_argv = [sys.executable, str(TOOLS_DIR / "secret_scan_checker.py")]
        if args.git_remotes:
            secret_argv.append("--git-remotes")
        if args.scan_secrets:
            if args.dir:
                secret_argv.extend(["--dir", args.dir])
            secret_argv.extend(args.files)
        rc = run_cmd("secret_scan_checker", secret_argv)
        exit_code = max(exit_code, rc)
        if args.git_remotes and not args.scan_secrets and not args.dir and not args.files:
            print(f"\n{'=' * 60}")
            if exit_code == 0:
                print("Summary: secret_scan 通过")
            else:
                print(f"Summary: secret_scan 失败 (exit={exit_code})")
            print(f"{'=' * 60}\n")
            return exit_code

    c_files = collect_c_files(args.files, args.dir, include_bad=args.include_bad)
    review_root = args.dir or (str(c_files[0].parent) if c_files else ".")

    skipped_bad = 0
    if args.dir and not args.include_bad:
        root = Path(args.dir)
        if root.is_dir():
            skipped_bad = sum(1 for f in root.rglob("*.c") if is_bad_example(f.resolve()))

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

    if not args.skip_queue and c_files:
        for f in c_files:
            rc = run_cmd(
                "queue_ownership_checker",
                [
                    sys.executable,
                    str(TOOLS_DIR / "queue_ownership_checker.py"),
                    str(f),
                ],
            )
            exit_code = max(exit_code, rc)
    elif not args.skip_queue:
        print("\n[skip] queue_ownership_checker: 无 .c 文件")

    if not args.skip_voice and c_files:
        voice_argv: list[str] = []
        if args.dir:
            voice_argv.extend(["--dir", args.dir])
        else:
            voice_argv.extend(str(f) for f in c_files)
        rc = run_cmd(
            "voice_sequence_checker",
            [sys.executable, str(TOOLS_DIR / "voice_sequence_checker.py"), *voice_argv],
        )
        exit_code = max(exit_code, rc)
    elif not args.skip_voice:
        print("\n[skip] voice_sequence_checker: 无 .c 文件")

    if not args.skip_logging and c_files:
        logging_argv: list[str] = []
        if args.dir:
            logging_argv.extend(["--dir", args.dir])
        else:
            logging_argv.extend(str(f) for f in c_files)
        rc = run_cmd(
            "logging_checker",
            [sys.executable, str(TOOLS_DIR / "logging_checker.py"), *logging_argv],
        )
        exit_code = max(exit_code, rc)
    elif not args.skip_logging:
        print("\n[skip] logging_checker: 无 .c 文件")

    if not args.skip_return_check and c_files:
        rc_argv: list[str] = []
        if args.dir:
            rc_argv.extend(["--dir", args.dir])
        else:
            rc_argv.extend(str(f) for f in c_files)
        rc = run_cmd(
            "return_check_checker",
            [sys.executable, str(TOOLS_DIR / "return_check_checker.py"), *rc_argv],
        )
        exit_code = max(exit_code, rc)
    elif not args.skip_return_check:
        print("\n[skip] return_check_checker: 无 .c 文件")

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
