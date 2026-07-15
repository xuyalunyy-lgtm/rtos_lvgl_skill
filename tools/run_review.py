#!/usr/bin/env python3
"""
One-click static review: chain checker scripts within the Skill.

Usage:
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
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

TOOLS_DIR = Path(__file__).resolve().parent
SKILL_ROOT = TOOLS_DIR.parent


def _read_skill_version() -> str:
    """Read version from SKILL.md frontmatter."""
    import re
    try:
        text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        m = re.search(r"version:\s*(\d+\.\d+\.\d+)", text)
        return m.group(1) if m else "0.0.0"
    except OSError:
        return "0.0.0"


SKILL_VERSION = _read_skill_version()


def checker_env() -> dict[str, str]:
    """Avoid UnicodeEncodeError from checker emoji output under Windows GBK console."""
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    return env


from checker_io import safe_print as _safe_print  # noqa: E402
from checker_registry import (  # noqa: E402
    ALL_CHECKERS,
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
        print(f"[FAIL] Missing test file: {path}")
        return False

    rc = run_checker(case.script, [str(path)])
    ok = rc == case.expected
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {case.label}: {case.script} {path.name} -> exit {rc} (expected {case.expected})")
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
        print(f"{title.split(' -- ')[-1]}: all passed")
    else:
        print(f"{title.split(' -- ')[-1]}: {failed} failed")
    print(f"{'=' * 60}\n")
    return 1 if failed else 0


def run_self_test() -> int:
    return run_case_group("run_review.py — checker fixtures 自测", SELF_TEST_CASES, TOOLS_DIR)


def run_validate_examples() -> int:
    """Iron rule example constraints: good_* must pass, bad_* must trigger corresponding checker failure."""
    return run_case_group("run_review.py -- examples/ iron rule constraint validation", VALIDATE_EXAMPLE_CASES, SKILL_ROOT)


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
        print("Default checker pipeline:")
        for spec in DEFAULT_CHECKERS:
            domains = ",".join(spec.domains)
            overlaps = f" (overlaps: {', '.join(spec.overlaps)})" if spec.overlaps else ""
            print(f"  --skip-{spec.skip_arg:<14} {spec.name:<28} {spec.mode:<8} {domains}{overlaps}")
        print("\nSpecial: --skip-stack skips stack_calculator; --scan-secrets / --git-remotes enable C9 scan individually")
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


_ISSUE_COUNT_RE = re.compile(r'(?:found|发现)\s*(\d+)\s*(?:issues?|个)')
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


def _run_one_checker(spec: CheckerSpec, c_files: list[Path], tools_dir: str, skill_root: str) -> dict:
    """Run a single checker in a subprocess. Designed for ProcessPoolExecutor.

    Returns a dict with checker results (exit_code, issues, stdout, stderr).
    This function is top-level (not a closure) so it can be pickled for multiprocessing.
    """
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PYTHONUTF8", "1")

    if spec.mode == "per-file":
        checker_exit = 0
        total_issues = 0
        combined_output = ""
        for f in c_files:
            argv = [sys.executable, os.path.join(tools_dir, spec.script), str(f)]
            try:
                proc = subprocess.run(
                    argv, cwd=skill_root, env=env,
                    capture_output=True, text=True, encoding="utf-8", errors="replace",
                    timeout=300,
                )
            except subprocess.TimeoutExpired:
                checker_exit = max(checker_exit, 1)
                continue
            checker_exit = max(checker_exit, proc.returncode)
            combined_output += proc.stdout + proc.stderr
            total_issues += _parse_issue_count(proc.stdout + proc.stderr)
        return {
            "checker": spec.name, "script": spec.script,
            "domains": spec.domains, "mode": spec.mode,
            "files_checked": len(c_files), "issues": total_issues,
            "exit_code": checker_exit, "output": combined_output,
        }
    elif spec.mode == "batch":
        argv = [sys.executable, os.path.join(tools_dir, spec.script)]
        argv.extend(str(f) for f in c_files)
        try:
            proc = subprocess.run(
                argv, cwd=skill_root, env=env,
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=300,
            )
        except subprocess.TimeoutExpired:
            return {
                "checker": spec.name, "script": spec.script,
                "domains": spec.domains, "mode": spec.mode,
                "files_checked": len(c_files), "issues": 0,
                "exit_code": 1, "output": "",
            }
        combined = proc.stdout + proc.stderr
        return {
            "checker": spec.name, "script": spec.script,
            "domains": spec.domains, "mode": spec.mode,
            "files_checked": len(c_files), "issues": _parse_issue_count(combined),
            "exit_code": proc.returncode, "output": combined,
        }
    else:
        return {
            "checker": spec.name, "script": spec.script,
            "domains": spec.domains, "mode": spec.mode,
            "files_checked": 0, "issues": 0,
            "exit_code": 1, "output": f"Unknown checker mode: {spec.mode}",
        }


def _classify_checkers(checkers: tuple[CheckerSpec, ...]) -> tuple[list[CheckerSpec], list[tuple[CheckerSpec, CheckerSpec]]]:
    """Classify checkers into independent (no overlap) and overlap pairs.

    Returns:
        (independent_checkers, overlap_pairs)
        overlap_pairs: list of (primary, secondary) where secondary is skipped if primary finds issues.
    """
    overlap_map: dict[str, CheckerSpec] = {}
    for spec in checkers:
        if spec.overlaps:
            overlap_map[spec.name] = spec

    seen_overlap: set[str] = set()
    overlap_pairs: list[tuple[CheckerSpec, CheckerSpec]] = []
    overlap_names: set[str] = set()

    for spec in checkers:
        if spec.name in seen_overlap:
            continue
        if spec.overlaps:
            for target_name in spec.overlaps:
                if target_name in overlap_map:
                    overlap_pairs.append((spec, overlap_map[target_name]))
                    overlap_names.add(spec.name)
                    overlap_names.add(target_name)
                    seen_overlap.add(spec.name)
                    seen_overlap.add(target_name)

    independent = [s for s in checkers if s.name not in overlap_names]
    return independent, overlap_pairs


def run_registered_checkers(args: argparse.Namespace, c_files: list[Path]) -> int | tuple[int, list[dict]]:
    """Run all registered checkers.  Returns exit_code, or (exit_code, results) in JSON mode.

    Uses ProcessPoolExecutor for independent checkers (no overlap dependencies).
    Overlap pairs are run sequentially: primary first, skip secondary if primary found issues.
    """
    json_mode = getattr(args, "json", False)
    exit_code = 0
    results: list[dict] = []

    # Filter by --skip-* flags
    from_symptom_plan = bool(getattr(args, "from_symptom_plan", None))
    candidates = ALL_CHECKERS if from_symptom_plan else DEFAULT_CHECKERS
    selected = set(getattr(args, "symptom_checker_targets", ()))
    active_checkers = tuple(
        spec for spec in candidates
        if (not from_symptom_plan or spec.name in selected)
        and not getattr(args, spec.skip_attr, False)
    )

    if not c_files:
        for spec in active_checkers:
            if not json_mode:
                print(f"\n[skip] {spec.name}: no .c files")
            if json_mode:
                results.append({
                    "checker": spec.name, "script": spec.script,
                    "domains": spec.domains, "mode": spec.mode,
                    "files_checked": 0, "issues": 0, "exit_code": 0, "skipped": True,
                })
        return (exit_code, results) if json_mode else exit_code

    independent, overlap_pairs = _classify_checkers(active_checkers)

    # ── Phase 1: Run independent checkers in parallel ──
    checker_map: dict[str, dict] = {}
    max_workers = min(len(independent), os.cpu_count() or 4)

    if independent and max_workers > 1:
        with ProcessPoolExecutor(max_workers=max_workers) as pool:
            futures = {
                pool.submit(_run_one_checker, spec, c_files, str(TOOLS_DIR), str(SKILL_ROOT)): spec
                for spec in independent
            }
            for future in as_completed(futures):
                spec = futures[future]
                try:
                    result = future.result()
                except Exception as exc:
                    result = {
                        "checker": spec.name, "script": spec.script,
                        "domains": spec.domains, "mode": spec.mode,
                        "files_checked": len(c_files), "issues": 0,
                        "exit_code": 1, "output": str(exc),
                    }
                checker_map[spec.name] = result
                exit_code = max(exit_code, result["exit_code"])
                if not json_mode and result.get("output"):
                    print(f"\n{'=' * 60}\n[{spec.name}]\n{'=' * 60}", flush=True)
                    _safe_print(result["output"])
    else:
        # Fallback: run sequentially if few checkers or single core
        for spec in independent:
            result = _run_one_checker(spec, c_files, str(TOOLS_DIR), str(SKILL_ROOT))
            checker_map[spec.name] = result
            exit_code = max(exit_code, result["exit_code"])
            if not json_mode and result.get("output"):
                print(f"\n{'=' * 60}\n[{spec.name}]\n{'=' * 60}", flush=True)
                _safe_print(result["output"])

    # ── Phase 2: Run overlap pairs sequentially ──
    skip_overlap: set[str] = set()

    for primary, secondary in overlap_pairs:
        # Check if primary was already run (could be independent)
        if primary.name not in checker_map:
            if primary.name in skip_overlap:
                checker_map[primary.name] = {
                    "checker": primary.name, "script": primary.script,
                    "domains": primary.domains, "mode": primary.mode,
                    "files_checked": 0, "issues": 0, "exit_code": 0,
                    "skipped": True, "skipped_due_to_overlap": True,
                }
            else:
                result = _run_one_checker(primary, c_files, str(TOOLS_DIR), str(SKILL_ROOT))
                checker_map[primary.name] = result
                exit_code = max(exit_code, result["exit_code"])
                if not json_mode and result.get("output"):
                    print(f"\n{'=' * 60}\n[{primary.name}]\n{'=' * 60}", flush=True)
                    _safe_print(result["output"])

        primary_result = checker_map.get(primary.name, {})
        primary_issues = primary_result.get("issues", 0)

        # Skip secondary if primary found issues
        if primary_issues > 0:
            skip_overlap.add(secondary.name)
            checker_map[secondary.name] = {
                "checker": secondary.name, "script": secondary.script,
                "domains": secondary.domains, "mode": secondary.mode,
                "files_checked": 0, "issues": 0, "exit_code": 0,
                "skipped": True, "skipped_due_to_overlap": True,
            }
        elif secondary.name not in checker_map:
            result = _run_one_checker(secondary, c_files, str(TOOLS_DIR), str(SKILL_ROOT))
            checker_map[secondary.name] = result
            exit_code = max(exit_code, result["exit_code"])
            if not json_mode and result.get("output"):
                print(f"\n{'=' * 60}\n[{secondary.name}]\n{'=' * 60}", flush=True)
                _safe_print(result["output"])

    # ── Collect results in original order ──
    for spec in active_checkers:
        if spec.name in checker_map:
            result = checker_map[spec.name]
            # Remove internal output field from JSON results
            result_clean = {k: v for k, v in result.items() if k != "output"}
            results.append(result_clean)
        else:
            # Checker was not in independent or overlap groups (shouldn't happen)
            results.append({
                "checker": spec.name, "script": spec.script,
                "domains": spec.domains, "mode": spec.mode,
                "files_checked": 0, "issues": 0, "exit_code": 0, "skipped": True,
            })

    if json_mode:
        return exit_code, results
    return exit_code


def main() -> int:
    parser = argparse.ArgumentParser(description="FreeRTOS Skill one-click static review")
    parser.add_argument("files", nargs="*", help="Files to review (.c)")
    parser.add_argument("--dir", "-d", help="Recursively review all .c files in directory")
    parser.add_argument(
        "--platform", "-p", default="freertos",
        choices=["freertos", "esp32", "stm32", "jl", "bk", "zephyr"],
        help="Target platform",
    )
    parser.add_argument(
        "--describe",
        default="WSS TLS cJSON LVGL Presenter",
        help="stack_calculator task description",
    )
    parser.add_argument(
        "--include-bad",
        action="store_true",
        help="Include bad_*.c counter-examples (excluded by default)",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Run tools/fixtures/ self-test and exit",
    )
    parser.add_argument(
        "--list-checkers",
        action="store_true",
        help="List default checker pipeline and exit",
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
    parser.add_argument(
        "--evidence",
        metavar="FILE",
        help="输出交付证据包 (delivery_evidence.json) 到指定文件",
    )
    parser.add_argument(
        "--log",
        metavar="FILE",
        help="加载串口/系统日志并运行现场诊断 (log_triage)",
    )
    parser.add_argument(
        "--from-symptom-plan",
        metavar="FILE",
        help="Load a context_router diagnostic plan JSON and run only its checker_targets",
    )
    parser.add_argument(
        "--repro-output",
        metavar="FILE",
        help="生成可复现调试包到指定文件",
    )
    parser.add_argument(
        "--strict-field",
        action="store_true",
        help="现场诊断 P0 风险阻断 exit code（默认不阻断）",
    )
    parser.add_argument(
        "--suggest-fixes",
        action="store_true",
        help="输出可审查修复方案 (FixPlan)，不修改文件",
    )
    parser.add_argument(
        "--fix-detail",
        choices=["summary", "full"],
        default="summary",
        help="FixPlan 输出详细程度：summary（默认）只输出摘要，full 输出完整 template/diff",
    )
    args = parser.parse_args()

    args.symptom_checker_targets = ()
    if args.from_symptom_plan:
        try:
            raw_plan = json.loads(Path(args.from_symptom_plan).read_text(encoding="utf-8"))
            # log_triage --json wraps the router result in diagnostic_plan;
            # context_router writes the plan directly.  Accept both forms.
            plan = raw_plan.get("diagnostic_plan", raw_plan) if isinstance(raw_plan, dict) else raw_plan
            if not isinstance(plan, dict):
                raise ValueError("plan must be a JSON object")
            targets = plan.get("checker_targets", [])
            if not isinstance(targets, list) or not all(isinstance(item, str) for item in targets):
                raise ValueError("checker_targets must be a string list")
            known = {spec.name for spec in ALL_CHECKERS}
            unknown = sorted(set(targets) - known)
            if unknown:
                raise ValueError(f"unknown checker target(s): {', '.join(unknown)}")
            args.symptom_checker_targets = tuple(targets)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            parser.error(f"invalid --from-symptom-plan: {exc}")

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

    # ── 现场诊断：log_triage ──
    field_diagnostics = None
    if args.log:
        log_path = Path(args.log)
        if not log_path.is_file():
            print(f"Error: log file not found: {log_path}", file=sys.stderr)
            return 1
        log_argv = [sys.executable, str(TOOLS_DIR / "log_triage.py"), str(log_path)]
        if args.platform:
            log_argv.extend(["--platform", args.platform])
        if args.json:
            log_argv.append("--json")
        if args.json:
            rc, out = _run_and_capture("log_triage", log_argv, quiet=True)
            try:
                field_diagnostics = json.loads(out)
            except (json.JSONDecodeError, ValueError):
                field_diagnostics = {"raw_output": out, "parse_error": True}
        else:
            rc = run_cmd("log_triage", log_argv)
        # 默认不阻断；--strict-field 才阻断 P0
        if args.strict_field:
            exit_code = max(exit_code, rc)
        elif not args.json:
            print("[info] 现场诊断 P0 不阻断（加 --strict-field 可阻断）")

    # ── 复现包：repro_bundle ──
    if args.repro_output:
        repro_argv = [sys.executable, str(TOOLS_DIR / "repro_bundle.py"),
                      "--output", args.repro_output]
        if args.dir:
            repro_argv.extend(["--dir", args.dir])
        if args.platform:
            repro_argv.extend(["--platform", args.platform])
        if args.json:
            rc, _ = _run_and_capture("repro_bundle", repro_argv, quiet=True)
        else:
            rc = run_cmd("repro_bundle", repro_argv)
        exit_code = max(exit_code, rc)

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
            "version": SKILL_VERSION,
            "exit_code": exit_code,
            "files_checked": len(c_files),
            "suites": ["symptom-plan"] if args.from_symptom_plan else ["default"],
            "checkers": all_results,
            "total_issues": sum(r.get("issues", 0) for r in all_results),
            "total_checkers_run": sum(1 for r in all_results if not r.get("skipped")),
        }
        if field_diagnostics:
            report["field_diagnostics"] = field_diagnostics

        # ── 修复建议 (FixPlan) ──
        if args.suggest_fixes:
            fix_plans = []
            non_applicable = []
            # 只对有 issue 的 checker 生成 FixPlan
            for r in all_results:
                if r.get("skipped") or r.get("issues", 0) == 0:
                    continue
                checker_name = r.get("checker", "")
                # 找到对应的 spec
                spec = checker_map.get(checker_name)
                if not spec:
                    non_applicable.append({
                        "checker": checker_name,
                        "non_applicable_reason": "checker 不在注册表中",
                    })
                    continue
                # 对每个文件尝试生成 FixPlan
                for c_file in c_files[:10]:
                    af_argv = [sys.executable, str(TOOLS_DIR / "auto_fix_engine.py"),
                               str(c_file), "--checker", spec.name, "--plan", "--json"]
                    rc, out = _run_and_capture("auto_fix_engine", af_argv, quiet=True)
                    if rc == 0 and out.strip():
                        try:
                            plans = json.loads(out)
                            plan_list = plans if isinstance(plans, list) else [plans]
                            for plan in plan_list:
                                if plan.get("actions"):
                                    # 添加 source_diagnostic
                                    plan["source_diagnostic"] = {
                                        "checker": checker_name,
                                        "constraints": list(spec.domains),
                                        "file": str(c_file),
                                    }
                                    plan["fix_plan_schema_version"] = "1.0"
                                    fix_plans.append(plan)
                        except (json.JSONDecodeError, ValueError):
                            pass
            # summary 模式：限制输出数量，移除长字段
            if args.fix_detail == "summary":
                fix_plans = fix_plans[:20]  # JSON 默认最多 20 条
                for plan in fix_plans:
                    for action in plan.get("actions", []):
                        action.pop("template", None)
                        action.pop("diff", None)
            report["fix_plans"] = fix_plans
            report["total_fix_plans"] = len(fix_plans)
            report["total_non_applicable"] = len(non_applicable)
            if non_applicable:
                report["non_applicable"] = non_applicable
        json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
        print()
    else:
        print(f"\n{'=' * 60}")
        if exit_code == 0:
            print("Summary: 全部 checker 通过（启发式，仍需人工 review）")
        else:
            print(f"Summary: 存在告警/失败 (exit={exit_code})，请人工核对")
        print(f"{'=' * 60}\n")

        # ── 修复建议文本输出 ──
        if args.suggest_fixes:
            print("Fix Plan (可审查修复方案)")
            print("=" * 60)
            fix_count = 0
            max_fixes = 5 if args.fix_detail == "summary" else 999
            # 只对有 issue 的 checker 生成修复建议
            for r in all_results:
                if r.get("skipped") or r.get("issues", 0) == 0:
                    continue
                if fix_count >= max_fixes:
                    break
                checker_name = r.get("checker", "")
                spec = checker_map.get(checker_name)
                if not spec:
                    continue
                for c_file in c_files[:10]:
                    if fix_count >= max_fixes:
                        break
                    af_argv = [sys.executable, str(TOOLS_DIR / "auto_fix_engine.py"),
                               str(c_file), "--checker", spec.name, "--plan", "--diff"]
                    rc, out = _run_and_capture("auto_fix_engine", af_argv, quiet=True)
                    if rc == 0 and out.strip():
                        print(f"\n[{checker_name}] {c_file.name}")
                        if args.fix_detail == "summary":
                            # 只输出第一行摘要
                            for line in out.split("\n"):
                                if line.strip():
                                    print(f"  {line.strip()}")
                                    break
                        else:
                            print(out)
                        fix_count += 1
            if fix_count == 0:
                print("  无修复建议（所有 checker 通过或无匹配修复模板）")
            if fix_count >= max_fixes:
                print(f"\n共 {fix_count}+ 个修复建议（显示前 {max_fixes} 条，用 --fix-detail full 查看全部）")
            else:
                print(f"\n共 {fix_count} 个修复建议（不修改文件，仅供审查）")

    # ── 交付证据包输出 ──
    if args.evidence:
        try:
            from evidence_schema import (
                DeliveryEvidence,
                issue_entry,
                make_evidence,
                save_evidence,
            )
        except ImportError:
            print("[warn] evidence_schema 模块不可用（已归档），跳过证据包输出", file=sys.stderr)
            return 0

        # 收集所有 checker 的 issues（从 JSON 模式结果中提取）
        ev_issues: list[dict] = []
        if args.json:
            for r in all_results:
                checker_name = r.get("checker", "")
                # issues 字段可能是 int（摘要）或 list（详细）
                if isinstance(r.get("issues"), list):
                    for iss in r["issues"]:
                        ev_issues.append(issue_entry(
                            cid=iss.get("id", ""),
                            severity=iss.get("severity", "P2"),
                            file=iss.get("file", ""),
                            line=iss.get("line", 0),
                            constraint=iss.get("id", "").split(".")[0] if "." in iss.get("id", "") else "",
                            message=iss.get("issue", ""),
                            checker=checker_name,
                        ))

        # 生成复现命令
        repro_cmd = f"python tools/run_review.py --dir {args.dir}" if args.dir else f"python tools/run_review.py {' '.join(args.files)}"
        if args.platform != "freertos":
            repro_cmd += f" --platform {args.platform}"

        ev = make_evidence(
            source_tool="run_review",
            platform=args.platform,
            suite="default",
            issues=ev_issues,
            reproduce_commands=[{"command": repro_cmd, "description": "复现审查"}],
            metadata={
                "tool_version": SKILL_VERSION,
                "files_checked": len(c_files),
                "exit_code": exit_code,
                "total_checkers_run": sum(1 for r in (all_results if args.json else []) if not r.get("skipped")),
            },
        )
        save_evidence(ev, args.evidence)
        if not args.json:
            print(f"[evidence] 已保存交付证据包: {args.evidence}")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
