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
import json
import os
import re
import subprocess
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
SKILL_ROOT = TOOLS_DIR.parent


def checker_env() -> dict[str, str]:
    """Windows GBK 控制台下避免 checker emoji 输出触发 UnicodeEncodeError。"""
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    return env


from checker_io import safe_print as _safe_print  # noqa: E402
from checker_registry import (  # noqa: E402
    DEFAULT_CHECKERS,
    SELF_TEST_CASES,
    VALIDATE_EXAMPLE_CASES,
    CheckerCase,
    CheckerSpec,
)


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
            files.extend(sorted(p.rglob("*.h")))
            files.extend(sorted(p.rglob("*.cpp")))
    if dir_path:
        root = Path(dir_path)
        if root.is_dir():
            files.extend(sorted(root.rglob("*.c")))
            files.extend(sorted(root.rglob("*.h")))
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
    print(f"\n{'=' * 60}\n[{label}]\n{'=' * 60}", flush=True)
    print(" ", " ".join(str(a) for a in argv), flush=True)
    try:
        proc = subprocess.run(argv, cwd=SKILL_ROOT, env=checker_env(), timeout=300)
    except subprocess.TimeoutExpired:
        print(f"[TIMEOUT] {label} exceeded 300s", flush=True)
        return 1
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


def run_checker_case(case: CheckerCase, base_dir: Path) -> bool:
    path = base_dir / case.path
    if not path.is_file():
        print(f"[FAIL] 缺少测试文件: {path}")
        return False

    rc = run_checker(case.script, [str(path)])
    ok = rc == case.expected
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {case.label}: {case.script} {path.name} → exit {rc} (期望 {case.expected})")
    return ok


def run_case_group(title: str, cases: tuple[CheckerCase, ...], base_dir: Path) -> int:
    print("=" * 60)
    print(title)
    print("=" * 60)

    failed = 0
    for case in cases:
        if not run_checker_case(case, base_dir):
            failed += 1

    print(f"\n{'=' * 60}")
    if failed == 0:
        print(f"{title.split(' — ')[-1]}: 全部通过")
    else:
        print(f"{title.split(' — ')[-1]}: {failed} 项失败")
    print(f"{'=' * 60}\n")
    return 1 if failed else 0


def run_self_test() -> int:
    return run_case_group("run_review.py — checker fixtures 自测", SELF_TEST_CASES, TOOLS_DIR)


def run_validate_examples() -> int:
    """铁律范例约束：good_* 须通过，bad_* 须触发对应 checker 失败。"""
    return run_case_group("run_review.py — examples/ 铁律约束验证", VALIDATE_EXAMPLE_CASES, SKILL_ROOT)


def list_checkers(as_json: bool = False) -> int:
    if as_json:
        import json
        data = []
        for spec in DEFAULT_CHECKERS:
            data.append({
                "name": spec.name,
                "script": spec.script,
                "skip_arg": spec.skip_arg,
                "mode": spec.mode,
                "domains": list(spec.domains),
                "suites": list(spec.suites),
            })
        json.dump(data, sys.stdout, ensure_ascii=False, indent=2)
        print()
    else:
        print("默认 checker 管线:")
        for spec in DEFAULT_CHECKERS:
            domains = ",".join(spec.domains)
            print(f"  --skip-{spec.skip_arg:<14} {spec.name:<28} {spec.mode:<8} {domains}")
        print("\n特殊项: --skip-stack 跳过 stack_calculator；--scan-secrets / --git-remotes 单独启用 C9 扫描")
    return 0


def checker_argv(spec: CheckerSpec, c_files: list[Path]) -> list[str]:
    argv = [sys.executable, str(TOOLS_DIR / spec.script)]
    argv.extend(str(f) for f in c_files)
    return argv


def _run_and_capture(label: str, argv: list[str], quiet: bool = False) -> tuple[int, str]:
    """Run a subprocess, optionally print output, return (exit_code, stdout+stderr)."""
    if not quiet:
        print(f"\n{'=' * 60}\n[{label}]\n{'=' * 60}", flush=True)
        print(" ", " ".join(str(a) for a in argv), flush=True)
    try:
        proc = subprocess.run(
            argv, cwd=SKILL_ROOT, env=checker_env(),
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=300,
        )
    except subprocess.TimeoutExpired:
        if not quiet:
            print(f"[TIMEOUT] {label} exceeded 300s", flush=True)
        return 1, ""
    combined = proc.stdout + proc.stderr
    if combined and not quiet:
        print(combined, end="", flush=True)
    return proc.returncode, combined


_ISSUE_COUNT_RE = re.compile(r'发现\s*(\d+)\s*个')
_WARN_COUNT_RE = re.compile(r'(\d+)\s+warnings?', re.IGNORECASE)


def _parse_issue_count(output: str) -> int:
    """Extract violation count from checker stdout."""
    m = _ISSUE_COUNT_RE.search(output)
    if m:
        return int(m.group(1))
    m = _WARN_COUNT_RE.search(output)
    if m:
        return int(m.group(1))
    return 0


def run_registered_checkers(args: argparse.Namespace, c_files: list[Path]) -> int | tuple[int, list[dict]]:
    """Run all registered checkers.  Returns exit_code, or (exit_code, results) in JSON mode."""
    json_mode = getattr(args, "json", False)
    exit_code = 0
    results: list[dict] = []

    for spec in DEFAULT_CHECKERS:
        if getattr(args, spec.skip_attr):
            continue
        if not c_files:
            if not json_mode:
                print(f"\n[skip] {spec.name}: 无 .c 文件")
            if json_mode:
                results.append({
                    "checker": spec.name, "script": spec.script,
                    "domains": spec.domains, "mode": spec.mode,
                    "files_checked": 0, "issues": 0, "exit_code": 0, "skipped": True,
                })
            continue

        if spec.mode == "per-file":
            checker_exit = 0
            total_issues = 0
            for f in c_files:
                rc, out = _run_and_capture(spec.name, [sys.executable, str(TOOLS_DIR / spec.script), str(f)], quiet=json_mode)
                checker_exit = max(checker_exit, rc)
                total_issues += _parse_issue_count(out)
            exit_code = max(exit_code, checker_exit)
            if json_mode:
                results.append({
                    "checker": spec.name, "script": spec.script,
                    "domains": spec.domains, "mode": spec.mode,
                    "files_checked": len(c_files), "issues": total_issues,
                    "exit_code": checker_exit,
                })
        elif spec.mode == "batch":
            rc, out = _run_and_capture(spec.name, checker_argv(spec, c_files), quiet=json_mode)
            exit_code = max(exit_code, rc)
            if json_mode:
                results.append({
                    "checker": spec.name, "script": spec.script,
                    "domains": spec.domains, "mode": spec.mode,
                    "files_checked": len(c_files), "issues": _parse_issue_count(out),
                    "exit_code": rc,
                })
        else:
            if not json_mode:
                print(f"[warn] 未知 checker mode: {spec.name} mode={spec.mode}")
            exit_code = max(exit_code, 1)

    if json_mode:
        return exit_code, results
    return exit_code


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
    parser.add_argument(
        "--list-checkers",
        action="store_true",
        help="列出默认 checker 管线并退出",
    )
    parser.add_argument("--skip-stack", action="store_true")
    for spec in DEFAULT_CHECKERS:
        parser.add_argument(
            f"--skip-{spec.skip_arg}",
            action="store_true",
            help=f"跳过 {spec.name} ({','.join(spec.domains)})",
        )
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
    parser.add_argument(
        "--json",
        action="store_true",
        help="输出 JSON 格式摘要（CI 集成 / 机器可读）",
    )
    args = parser.parse_args()

    if args.list_checkers:
        return list_checkers(as_json=args.json)

    if args.self_test:
        return run_self_test()

    if args.validate_examples:
        return run_validate_examples()

    exit_code = 0
    extra_results: list[dict] = []  # for --json: checkers run outside registered loop

    if args.scan_secrets or args.git_remotes:
        secret_argv = [sys.executable, str(TOOLS_DIR / "secret_scan_checker.py")]
        if args.git_remotes:
            secret_argv.append("--git-remotes")
        if args.scan_secrets:
            if args.dir:
                secret_argv.extend(["--dir", args.dir])
            secret_argv.extend(args.files)
        if args.json:
            rc, out = _run_and_capture("secret_scan_checker", secret_argv, quiet=True)
            extra_results.append({
                "checker": "secret_scan_checker", "script": "secret_scan_checker.py",
                "domains": ["C9"], "mode": "batch",
                "files_checked": 0, "issues": _parse_issue_count(out), "exit_code": rc,
            })
        else:
            rc = run_cmd("secret_scan_checker", secret_argv)
        exit_code = max(exit_code, rc)
        if args.git_remotes and not args.scan_secrets and not args.dir and not args.files:
            if not args.json:
                print(f"\n{'=' * 60}")
                if exit_code == 0:
                    print("Summary: secret_scan 通过")
                else:
                    print(f"Summary: secret_scan 失败 (exit={exit_code})")
                print(f"{'=' * 60}\n")
            return exit_code

    c_files = collect_c_files(args.files, args.dir, include_bad=args.include_bad)
    skipped_bad = 0
    if args.dir and not args.include_bad:
        root = Path(args.dir)
        if root.is_dir():
            skipped_bad = sum(1 for f in root.rglob("*.c") if is_bad_example(f.resolve()))

    if skipped_bad and not args.json:
        print(f"[info] 已排除 {skipped_bad} 个 bad_*.c 反例（加 --include-bad 可纳入）")

    if not args.skip_stack:
        stack_argv = [
            sys.executable,
            str(TOOLS_DIR / "stack_calculator.py"),
            "--describe",
            args.describe,
            "--platform",
            args.platform,
        ]
        if args.json:
            rc, _ = _run_and_capture("stack_calculator", stack_argv, quiet=True)
        else:
            rc = run_cmd("stack_calculator", stack_argv)
        exit_code = max(exit_code, rc)

    checker_result = run_registered_checkers(args, c_files)
    if args.json:
        checker_exit, checker_results = checker_result
    else:
        checker_exit = checker_result
    exit_code = max(exit_code, checker_exit)

    if not c_files and args.dir:
        print("\n[warn] 排除 bad_*.c 后无可审查文件")

    if args.json:
        # 从 checker_registry 获取 suite 信息
        from checker_registry import ALL_CHECKERS as _ALL
        checker_map = {c.name: c for c in _ALL}
        all_results = checker_results + extra_results
        for r in all_results:
            spec = checker_map.get(r["checker"])
            if spec:
                r["suites"] = list(spec.suites)

        report = {
            "version": "8.0.4",
            "exit_code": exit_code,
            "files_checked": len(c_files),
            "suites": ["default"],
            "checkers": all_results,
            "total_issues": sum(r.get("issues", 0) for r in all_results),
            "total_checkers_run": sum(1 for r in all_results if not r.get("skipped")),
        }
        json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
        print()
    else:
        print(f"\n{'=' * 60}")
        if exit_code == 0:
            print("Summary: 全部 checker 通过（启发式，仍需人工 review）")
        else:
            print(f"Summary: 存在告警/失败 (exit={exit_code})，请人工核对")
        print(f"{'=' * 60}\n")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
