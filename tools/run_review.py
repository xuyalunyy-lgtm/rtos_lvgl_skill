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


_DISABLED_CONFIG_RE = re.compile(r"#\s*(CONFIG_[A-Za-z0-9_]+)\s+is\s+not\s+set")


def load_kconfig_values(paths: list[str]) -> dict[str, str]:
    """Merge sdkconfig/prj.conf files for checker-side Kconfig filtering."""
    values: dict[str, str] = {}
    for raw_path in paths:
        path = Path(raw_path)
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError as exc:
            raise ValueError(f"cannot read Kconfig file {path}: {exc}") from exc
        for raw_line in lines:
            line = raw_line.strip()
            disabled = _DISABLED_CONFIG_RE.fullmatch(line)
            if disabled:
                values[disabled.group(1)] = "n"
                continue
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            if key.startswith("CONFIG_"):
                values[key] = value.strip().strip('"')
    return values


def configure_kconfig_values(paths: list[str]) -> dict[str, str]:
    """Publish known Kconfig values to all checker subprocesses for this run."""
    values = load_kconfig_values(paths)
    if values:
        os.environ["SKILL_KCONFIG_VALUES"] = json.dumps(values, ensure_ascii=False, sort_keys=True)
    else:
        os.environ.pop("SKILL_KCONFIG_VALUES", None)
    return values


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


def collect_changed_c_files(base: str | None) -> list[Path]:
    """Return changed C/C++ headers and sources from Git, excluding deletions.

    With no base this compares the working tree (including staged changes) to
    HEAD.  A caller may pass a merge-base revision for CI/PR reviews.
    """
    command = ["git", "diff", "--name-only", "--diff-filter=ACMR"]
    if base:
        command.append(f"{base}...HEAD")
    else:
        command.append("HEAD")
    try:
        proc = subprocess.run(
            command, cwd=SKILL_ROOT, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"cannot determine changed files: {exc}") from exc
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip()
        raise RuntimeError(f"git diff failed ({' '.join(command)}): {detail}")
    return collect_c_files(proc.stdout.splitlines(), None, include_bad=True)


def run_cmd(label: str, argv: list[str]) -> int:
    print(f"\n{'=' * 60}\n[{label}]\n{'=' * 60}", flush=True)
    print(" ", " ".join(str(a) for a in argv), flush=True)
    try:
        proc = subprocess.run(argv, cwd=SKILL_ROOT, env=checker_env(), timeout=300)
    except subprocess.TimeoutExpired:
        print(f"[TIMEOUT] {label} exceeded 300s", flush=True)
        return 1
    return proc.returncode


def run_checker(script: str, checker_args: list[str], environment: dict[str, str] | None = None) -> int:
    argv = [sys.executable, str(TOOLS_DIR / script), *checker_args]
    env = checker_env()
    if environment:
        env.update(environment)
    proc = subprocess.run(
        argv,
        cwd=SKILL_ROOT,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        env=env,
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

    rc = run_checker(case.script, [str(path)], dict(case.environment))
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


CHECKER_PROTOCOL_VERSION = "checker-result/v1"


def _parse_checker_jsonl(output: str) -> dict:
    """Parse the one-record checker JSON Lines protocol strictly.

    Human-oriented checker text must never be used to calculate issue counts:
    wording changes would otherwise silently turn real findings into zero.
    """
    records = [line for line in output.splitlines() if line.strip()]
    if len(records) != 1:
        raise ValueError(f"expected one JSONL record, received {len(records)}")
    try:
        payload = json.loads(records[0])
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSONL record: {exc.msg}") from exc
    if not isinstance(payload, dict) or payload.get("protocol_version") != CHECKER_PROTOCOL_VERSION:
        raise ValueError("unsupported checker result protocol")
    issues = payload.get("issues")
    violations = payload.get("violations")
    if not isinstance(issues, list) or not isinstance(violations, int) or violations != len(issues):
        raise ValueError("invalid violations/issues fields")
    if not isinstance(payload.get("files_checked"), int):
        raise ValueError("invalid files_checked field")
    return payload


def _format_checker_payload(payload: dict) -> str:
    """Render a structured checker payload for the interactive CLI."""
    checker = payload.get("checker", "checker")
    files_checked = payload.get("files_checked", 0)
    issues = payload.get("issues", [])
    domains = "/".join(payload.get("domains", [])) or "checker"
    if not issues:
        return f"[{checker}] checked {files_checked} file(s), no {domains} violations\n"
    lines = [f"[{checker}] checked {files_checked} file(s), found {len(issues)} {domains} warning(s):", ""]
    for issue in issues:
        lines.append(
            f"  [{issue.get('severity', '?')}] {issue.get('id', '?')} — "
            f"{issue.get('file', '?')} — {issue.get('issue', '?')}"
        )
    return "\n".join(lines) + "\n"


def _run_checker_protocol(argv: list[str], *, cwd: str, env: dict[str, str]) -> tuple[int, dict | None, str]:
    """Run one checker and require its checker-result/v1 JSONL record."""
    try:
        proc = subprocess.run(
            [*argv, "--jsonl"], cwd=cwd, env=env,
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=300,
        )
    except subprocess.TimeoutExpired:
        return 1, None, "checker timed out after 300s"
    combined = proc.stdout + proc.stderr
    try:
        payload = _parse_checker_jsonl(proc.stdout)
    except ValueError as exc:
        return 1, None, f"checker protocol error: {exc}; raw output: {combined[:500]}"
    return proc.returncode, payload, ""


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
        findings: list[dict] = []
        rendered: list[str] = []
        protocol_error = ""
        for f in c_files:
            argv = [sys.executable, os.path.join(tools_dir, spec.script), str(f)]
            rc, payload, error = _run_checker_protocol(argv, cwd=skill_root, env=env)
            checker_exit = max(checker_exit, rc)
            if error:
                protocol_error = error
                continue
            assert payload is not None
            findings.extend(payload["issues"])
            rendered.append(_format_checker_payload(payload))
        return {
            "checker": spec.name, "script": spec.script,
            "domains": spec.domains, "mode": spec.mode,
            "files_checked": len(c_files), "issues": len(findings), "findings": findings,
            "exit_code": checker_exit, "output": "".join(rendered) or protocol_error,
        }
    elif spec.mode == "batch":
        argv = [sys.executable, os.path.join(tools_dir, spec.script)]
        argv.extend(str(f) for f in c_files)
        rc, payload, error = _run_checker_protocol(argv, cwd=skill_root, env=env)
        if error:
            return {
                "checker": spec.name, "script": spec.script,
                "domains": spec.domains, "mode": spec.mode,
                "files_checked": len(c_files), "issues": 0,
                "findings": [], "exit_code": 1, "output": error,
            }
        assert payload is not None
        return {
            "checker": spec.name, "script": spec.script,
            "domains": spec.domains, "mode": spec.mode,
            "files_checked": len(c_files), "issues": payload["violations"],
            "findings": payload["issues"], "exit_code": rc,
            "output": _format_checker_payload(payload),
        }
    elif spec.mode == "global":
        argv = [sys.executable, os.path.join(tools_dir, spec.script)]
        rc, payload, error = _run_checker_protocol(argv, cwd=skill_root, env=env)
        if error:
            return {
                "checker": spec.name, "script": spec.script,
                "domains": spec.domains, "mode": spec.mode,
                "files_checked": 0, "issues": 0,
                "findings": [], "exit_code": 1, "output": error,
            }
        assert payload is not None
        return {
            "checker": spec.name, "script": spec.script,
            "domains": spec.domains, "mode": spec.mode,
            "files_checked": payload["files_checked"], "issues": payload["violations"],
            "findings": payload["issues"], "exit_code": rc,
            "output": _format_checker_payload(payload),
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


def selected_checker_specs(args: argparse.Namespace) -> tuple[CheckerSpec, ...]:
    """Resolve the effective checker set once for execution and --dry-run."""
    from_symptom_plan = bool(getattr(args, "from_symptom_plan", None))
    candidates = ALL_CHECKERS if from_symptom_plan else DEFAULT_CHECKERS
    selected = set(getattr(args, "symptom_checker_targets", ()))
    return tuple(
        spec for spec in candidates
        if (not from_symptom_plan or spec.name in selected)
        and not getattr(args, spec.skip_attr, False)
    )


def build_execution_plan(args: argparse.Namespace, c_files: list[Path]) -> dict:
    """Describe every subprocess that would be run without executing it."""
    steps: list[dict] = []
    if args.scan_secrets or args.git_remotes:
        argv = [sys.executable, str(TOOLS_DIR / "secret_scan_checker.py")]
        if args.git_remotes:
            argv.append("--git-remotes")
        if args.scan_secrets:
            if args.dir:
                argv.extend(["--dir", args.dir])
            argv.extend(args.files)
        steps.append({"kind": "auxiliary", "name": "secret_scan_checker", "argv": argv})
    if args.log:
        steps.append({
            "kind": "auxiliary", "name": "log_triage",
            "argv": [sys.executable, str(TOOLS_DIR / "log_triage.py"), "--log", args.log, "--platform", args.platform],
        })
    if args.repro_output:
        steps.append({
            "kind": "auxiliary", "name": "repro_bundle",
            "argv": [sys.executable, str(TOOLS_DIR / "repro_bundle.py"), "--output", args.repro_output],
        })
    if not args.skip_stack:
        steps.append({
            "kind": "auxiliary", "name": "stack_calculator",
            "argv": [sys.executable, str(TOOLS_DIR / "stack_calculator.py"), "--describe", args.describe, "--platform", args.platform],
        })
    if not c_files and not any(spec.mode == "global" for spec in selected_checker_specs(args)):
        steps.append({"kind": "skip", "name": "registered_checkers", "reason": "no C/C++ files selected"})
    else:
        for spec in selected_checker_specs(args):
            if not c_files and spec.mode != "global":
                continue
            steps.append({
                "kind": "checker", "name": spec.name, "script": spec.script,
                "mode": spec.mode, "domains": list(spec.domains),
                "files": [str(path) for path in c_files],
                "protocol": CHECKER_PROTOCOL_VERSION,
            })
    if args.evidence:
        steps.append({"kind": "output", "name": "delivery_evidence", "path": args.evidence})
    return {
        "version": SKILL_VERSION,
        "dry_run": True,
        "files_checked": len(c_files),
        "changed_only": bool(getattr(args, "changed_only", False)),
        "changed_base": getattr(args, "changed_base", None),
        "kconfig_files": list(getattr(args, "config", []) or []),
        "suites": ["symptom-plan"] if args.from_symptom_plan else ["default"],
        "steps": steps,
    }


def print_execution_plan(plan: dict, *, as_json: bool) -> None:
    if as_json:
        json.dump(plan, sys.stdout, ensure_ascii=False, indent=2)
        print()
        return
    print(f"Dry run: {plan['files_checked']} source file(s), {len(plan['steps'])} planned step(s)")
    for step in plan["steps"]:
        if step["kind"] == "checker":
            print(f"  [checker] {step['name']} ({step['mode']}, {', '.join(step['domains'])})")
        elif step["kind"] == "output":
            print(f"  [output] {step['name']} -> {step['path']}")
        elif step["kind"] == "skip":
            print(f"  [skip] {step['name']}: {step['reason']}")
        else:
            print(f"  [{step['kind']}] {step['name']}: {' '.join(str(arg) for arg in step['argv'])}")


def run_registered_checkers(args: argparse.Namespace, c_files: list[Path]) -> int | tuple[int, list[dict]]:
    """Run all registered checkers.  Returns exit_code, or (exit_code, results) in JSON mode.

    Uses ProcessPoolExecutor for independent checkers (no overlap dependencies).
    Overlap pairs are run sequentially: primary first, skip secondary if primary found issues.
    """
    json_mode = getattr(args, "json", False)
    exit_code = 0
    results: list[dict] = []

    # Filter by --skip-* flags
    active_checkers = selected_checker_specs(args)

    if not c_files:
        global_checkers = tuple(spec for spec in active_checkers if spec.mode == "global")
        for spec in active_checkers:
            if spec.mode == "global":
                continue
            if not json_mode:
                print(f"\n[skip] {spec.name}: no .c files")
            if json_mode:
                results.append({
                    "checker": spec.name, "script": spec.script,
                    "domains": spec.domains, "mode": spec.mode,
                    "files_checked": 0, "issues": 0, "exit_code": 0, "skipped": True,
                })
        if not global_checkers:
            return (exit_code, results) if json_mode else exit_code
        active_checkers = global_checkers

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


def _launch_watch(args: argparse.Namespace) -> int:
    """Delegate polling to the standalone watcher without recursive flags."""
    forwarded: list[str] = []
    raw = sys.argv[1:]
    index = 0
    while index < len(raw):
        token = raw[index]
        if token == "--watch":
            index += 1
            continue
        if token in {"--watch-interval"}:
            index += 2
            continue
        if token.startswith("--watch-interval=") or token == "--watch-once":
            index += 1
            continue
        forwarded.append(token)
        index += 1
    command = [
        sys.executable, str(TOOLS_DIR / "review_watch.py"), "--root", args.dir,
        "--interval", str(args.watch_interval),
    ]
    if args.watch_once:
        command.append("--once")
    command.extend(["--", *forwarded])
    return subprocess.run(command, cwd=SKILL_ROOT).returncode


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
    parser.add_argument("--markdown", metavar="FILE", help="将结构化审查结果写为 Markdown 报告")
    parser.add_argument("--html", metavar="FILE", help="将结构化审查结果写为独立 HTML 报告")
    parser.add_argument("--watch", action="store_true", help="监控 --dir 下 C/C++ 保存并增量重跑相关 checker")
    parser.add_argument("--watch-interval", type=float, default=0.75, help="--watch 轮询秒数（默认 0.75）")
    parser.add_argument("--watch-once", action="store_true", help="配合 --watch 只执行首轮全量审查（便于 IDE/CI 验证）")
    parser.add_argument(
        "--build-system",
        help="由 project_doctor 传入的构建系统上下文（例如 esp-idf、west、cmake）",
    )
    parser.add_argument(
        "--history-dir",
        default="artifacts/review_history",
        help="JSON review 历史目录（默认：artifacts/review_history）",
    )
    parser.add_argument(
        "--no-history",
        action="store_true",
        help="不保存 JSON review 历史（默认会保存，适合一次性临时检查）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只输出将执行的辅助工具与 checker 计划，不运行任何子进程",
    )
    parser.add_argument(
        "--changed-only",
        action="store_true",
        help="只审查相对 HEAD 的 Git diff 中 C/C++ 文件（CI 可配合 --changed-base）",
    )
    parser.add_argument(
        "--changed-base",
        metavar="REV",
        help="--changed-only 的 Git 合并基线；使用 REV...HEAD 计算变更",
    )
    parser.add_argument(
        "--config",
        action="append",
        default=[],
        metavar="FILE",
        help="加载 sdkconfig/prj.conf；已知禁用的 CONFIG 分支不会参与 checker 扫描（可重复）",
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
    emit_json = args.json

    if args.watch:
        if not args.dir or args.files or args.changed_only or args.dry_run:
            parser.error("--watch requires --dir and cannot be combined with files, --changed-only, or --dry-run")
        if args.watch_interval <= 0:
            parser.error("--watch-interval must be positive")
        return _launch_watch(args)
    if (args.markdown or args.html) and (args.self_test or args.validate_examples or args.list_checkers or args.dry_run):
        parser.error("--markdown/--html require an executed review, not a meta command or --dry-run")
    # Report rendering consumes the same structured data as --json.  Preserve
    # normal text stdout when only a file report was requested.
    if args.markdown or args.html:
        args.json = True

    try:
        args.kconfig_values = configure_kconfig_values(args.config)
    except ValueError as exc:
        parser.error(str(exc))
    if args.build_system:
        os.environ["SKILL_BUILD_SYSTEM"] = args.build_system
    else:
        os.environ.pop("SKILL_BUILD_SYSTEM", None)
    # All SDK-aware checkers load their API names at process start.  Propagate
    # the requested target before any checker subprocess is created.
    os.environ["SDK_PLATFORM"] = args.platform

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

    if args.dry_run and (args.self_test or args.validate_examples or args.list_checkers):
        parser.error("--dry-run cannot be combined with --self-test, --validate-examples, or --list-checkers")

    if args.list_checkers:
        return list_checkers(as_json=args.json)

    if args.self_test:
        return run_self_test()

    if args.validate_examples:
        return run_validate_examples()

    if args.changed_only and (args.files or args.dir):
        parser.error("--changed-only cannot be combined with positional files or --dir")
    if args.changed_base and not args.changed_only:
        parser.error("--changed-base requires --changed-only")

    if args.changed_only:
        try:
            c_files = collect_changed_c_files(args.changed_base)
        except RuntimeError as exc:
            parser.error(str(exc))
    else:
        c_files = collect_c_files(args.files, args.dir, include_bad=args.include_bad)
    skipped_bad = 0
    if args.dir and not args.include_bad:
        root = Path(args.dir)
        if root.is_dir():
            skipped_bad = sum(1 for f in root.rglob("*.c") if is_bad_example(f.resolve()))

    if args.dry_run:
        print_execution_plan(build_execution_plan(args, c_files), as_json=args.json)
        return 0

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
            rc, out = _run_and_capture("secret_scan_checker", [*secret_argv, "--jsonl"], quiet=True)
            protocol_error = ""
            try:
                payload = _parse_checker_jsonl(out)
            except ValueError as exc:
                payload = None
                rc = 1
                protocol_error = str(exc)
            extra_results.append({
                "checker": "secret_scan_checker", "script": "secret_scan_checker.py",
                "domains": ["C9"], "mode": "batch",
                "files_checked": payload["files_checked"] if payload else 0,
                "issues": payload["violations"] if payload else 0,
                "findings": payload["issues"] if payload else [],
                "exit_code": rc,
                **({"protocol_error": protocol_error} if payload is None else {}),
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
            "review_context": {
                "platform": args.platform,
                "build_system": args.build_system,
                "kconfig_files": list(args.config),
                "kconfig_values_loaded": len(args.kconfig_values),
            },
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
        if not args.no_history:
            try:
                from review_history import append as append_review_history
                append_review_history(report, args.history_dir)
            except OSError as exc:
                print(f"[warn] review history was not saved: {exc}", file=sys.stderr)
        output_paths: list[Path] = []
        if args.markdown or args.html:
            from review_report import write_report
            try:
                if args.markdown:
                    output_paths.append(write_report(report, args.markdown, "markdown"))
                if args.html:
                    output_paths.append(write_report(report, args.html, "html"))
            except OSError as exc:
                print(f"[error] report output failed: {exc}", file=sys.stderr)
                return 1
        if emit_json:
            json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
            print()
        elif output_paths:
            outcome = "通过" if exit_code == 0 else "存在告警/失败"
            print(f"Summary: {outcome}; files={len(c_files)} issues={report['total_issues']}")
            for output_path in output_paths:
                print(f"[report] {output_path}")
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
                for iss in r.get("findings", []):
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
