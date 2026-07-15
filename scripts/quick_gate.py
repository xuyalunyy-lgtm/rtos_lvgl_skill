#!/usr/bin/env python3
"""Run the fast local release gate for this skill.

This intentionally avoids git history and install-state checks so it can be
used during normal iteration before a commit is ready.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from dataclasses import dataclass, replace
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_QUALITY_POLICY = ROOT / "references" / "log_symptom_routes_quality_policy.json"
DEFAULT_QUALITY_ALLOWLIST = ROOT / "references" / "log_symptom_route_conflict_allowlist.json"
DEFAULT_QUALITY_ARTIFACT = ROOT / "artifacts" / "log_symptom_routes_quality.json"


@dataclass(frozen=True)
class GateStep:
    name: str
    cmd: list[str]
    blocking: bool = True
    timeout_seconds: float = 300.0


STEPS = [
    GateStep("review self-test", [sys.executable, "tools/run_review.py", "--self-test"]),
    GateStep("review examples", [sys.executable, "tools/run_review.py", "--validate-examples"]),
    GateStep("log triage self-test", [sys.executable, "tools/log_triage.py", "--self-test"]),
    GateStep("log triage batch self-test", [sys.executable, "tools/log_triage_batch.py", "--self-test"]),
    GateStep("log triage matrix", [sys.executable, "scripts/check_log_triage_matrix.py"]),
    GateStep("project gate self-test", [sys.executable, "tools/project_gate.py", "--self-test"]),
    GateStep("repro bundle self-test", [sys.executable, "tools/repro_bundle.py", "--self-test"]),
    GateStep("context router self-test", [sys.executable, "tools/context_router.py", "--self-test"]),
    GateStep("routing table sync", [sys.executable, "scripts/sync_skill_routing.py", "--check"]),
    GateStep("post-install smoke self-test", [sys.executable, "scripts/post_install_smoke.py", "--self-test"]),
    GateStep("skill metadata", [sys.executable, "scripts/check_skill_metadata.py"]),
    GateStep("official skill validator", [sys.executable, "scripts/run_official_skill_validator.py", "."]),
    GateStep("text encoding", [sys.executable, "scripts/check_text_encoding.py"]),
    GateStep("runtime distribution", [sys.executable, "scripts/check_runtime_distribution.py"]),
    GateStep("link check", [sys.executable, "tools/check_links.py"]),
    GateStep("release contract", [sys.executable, "scripts/check_release_contract.py"]),
    GateStep("project doctor", [sys.executable, "tools/project_doctor.py", "--self-test"]),
    GateStep("unit tests", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"]),
    GateStep("mqtt MCP", [sys.executable, "mcp/mqtt_server.py", "--self-test"]),
    GateStep("ota MCP", [sys.executable, "mcp/ota_server.py", "--self-test"]),
    GateStep("serial MCP", [sys.executable, "mcp/serial_server.py", "--self-test"]),
]



def _env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    return env


def _parse_bool_env(value: str) -> bool | None:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on", "y"}:
        return True
    if normalized in {"0", "false", "no", "off", "n"}:
        return False
    return None


def _is_ci_environment() -> bool:
    return os.getenv("CI", "").strip().lower() in {"1", "true", "yes", "on"}


def _resolve_quality_strict(args: argparse.Namespace) -> bool:
    env_override = os.getenv("SKILL_QUICK_GATE_STRICT")
    if env_override is not None and env_override.strip():
        parsed = _parse_bool_env(env_override)
        if parsed is not None:
            return parsed
    return args.strict or _is_ci_environment()


def _print_failure_output(proc: subprocess.CompletedProcess[str]) -> None:
    if proc.stdout:
        print("  stdout:")
        for line in proc.stdout.splitlines():
            print(f"    {line}")
    if proc.stderr:
        print("  stderr:")
        for line in proc.stderr.splitlines():
            print(f"    {line}")


def _append_if_set(command: list[str], flag: str, value: object) -> None:
    if value is not None:
        command.extend([flag, str(value)])


def _file_fingerprint(path: Path) -> tuple[str, str]:
    if not path.exists():
        return "missing", "missing"
    try:
        digest = hashlib.md5(path.read_bytes()).hexdigest()
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
        return digest, mtime
    except OSError:
        return "unreadable", "unreadable"


@dataclass
class StepResult:
    """Result of a single gate step."""
    index: int
    name: str
    blocking: bool
    passed: bool
    returncode: int
    output: str  # captured stdout + stderr
    timed_out: bool = False
    timeout_seconds: float | None = None
    duration_seconds: float = 0.0


def run_step_capture(index: int, step: GateStep) -> StepResult:
    """Run a single gate step and capture output. Designed for parallel execution."""
    started = time.monotonic()
    try:
        proc = subprocess.run(
            step.cmd,
            cwd=ROOT,
            env=_env(),
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=step.timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
        return StepResult(
            index=index, name=step.name, blocking=step.blocking,
            passed=False, returncode=1,
            output=f"Timed out after {step.timeout_seconds:g}s\n{stdout}{stderr}",
            timed_out=True, timeout_seconds=step.timeout_seconds,
            duration_seconds=time.monotonic() - started,
        )
    except Exception as exc:
        return StepResult(
            index=index, name=step.name, blocking=step.blocking,
            passed=False, returncode=1, output=str(exc),
            duration_seconds=time.monotonic() - started,
        )

    combined = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode == 0:
        return StepResult(
            index=index, name=step.name, blocking=step.blocking,
            passed=True, returncode=0, output=combined,
            duration_seconds=time.monotonic() - started,
        )

    if not step.blocking:
        return StepResult(
            index=index, name=step.name, blocking=step.blocking,
            passed=True, returncode=proc.returncode, output=combined,
            duration_seconds=time.monotonic() - started,
        )

    return StepResult(
        index=index, name=step.name, blocking=step.blocking,
        passed=False, returncode=proc.returncode, output=combined,
        duration_seconds=time.monotonic() - started,
    )


def print_step_result(result: StepResult, total: int) -> None:
    """Print a step result in the original format."""
    label = f"[{result.index}/{total}] {result.name}"
    if not result.blocking:
        label += " (non-blocking)"

    if result.timed_out:
        print(f"{label}\n  TIMEOUT {result.name}: exceeded {result.timeout_seconds:g}s ({result.duration_seconds:.2f}s)")
        if result.output.strip():
            for line in result.output.strip().splitlines():
                print(f"    {line}")
    elif result.passed and result.returncode == 0:
        print(f"{label}\n  PASS {result.name} ({result.duration_seconds:.2f}s)")
    elif result.passed and not result.blocking:
        print(f"{label}\n  WARN {result.name}: exit {result.returncode} ({result.duration_seconds:.2f}s, non-blocking)")
        if result.output.strip():
            for line in result.output.strip().splitlines():
                print(f"    {line}")
    else:
        print(f"{label}\n  FAIL {result.name}: exit {result.returncode} ({result.duration_seconds:.2f}s)")
        if result.output.strip():
            print("  stdout:")
            for line in result.output.strip().splitlines():
                print(f"    {line}")


def _build_route_quality_step(args: argparse.Namespace, *, strict: bool) -> GateStep:
    command = [
        sys.executable,
        "scripts/check_log_symptom_quality_gate.py",
        "--quality-policy",
        str(args.quality_policy),
        "--conflict-allowlist",
        str(args.quality_allowlist),
        "--artifact",
        str(args.quality_artifact),
    ]
    _append_if_set(command, "--max-missing-field-alerts", args.quality_max_missing_field_alerts)
    _append_if_set(command, "--min-average-coverage", args.quality_min_average_coverage)
    _append_if_set(command, "--max-route-conflicts", args.quality_max_route_conflicts)
    _append_if_set(command, "--max-duplicate-patterns", args.quality_max_duplicate_patterns)
    _append_if_set(command, "--max-weak-strong-overlaps", args.quality_max_weak_strong_overlaps)
    _append_if_set(command, "--max-broad-patterns", args.quality_max_broad_patterns)
    _append_if_set(command, "--max-multi-match-fixtures", args.quality_max_multi_match_fixtures)
    if strict:
        command.append("--strict")
    return GateStep("log symptom routes quality", command)


def _build_coverage_step(*, strict: bool) -> GateStep:
    command = [sys.executable, "scripts/check_rule_coverage.py"]
    if strict:
        command.append("--strict")
    return GateStep("constraint coverage", command)


def _build_checker_registry_step(*, strict: bool) -> GateStep:
    command = [sys.executable, "scripts/check_checker_registry.py"]
    if strict:
        command.append("--strict")
    return GateStep("checker registry", command)


def _step_slug(name: str) -> str:
    return "-".join(part for part in "".join(ch.lower() if ch.isalnum() else " " for ch in name).split())


def _select_steps(steps: list[GateStep], filters: list[str]) -> list[GateStep]:
    """Select steps by case-insensitive display name or stable dashed slug."""
    if not filters:
        return steps
    selected: list[GateStep] = []
    for step in steps:
        haystack = f"{step.name.casefold()} {_step_slug(step.name)}"
        if any(token.casefold() in haystack for token in filters):
            selected.append(step)
    return selected


def print_timing_summary(results: list[StepResult], wall_seconds: float) -> None:
    """Print deterministic per-step timing after sequential or parallel execution."""
    print("\nTiming summary:")
    print(f"  {'Step':<32} {'Result':<9} Duration")
    for result in results:
        status = "TIMEOUT" if result.timed_out else "PASS" if result.passed else "FAIL"
        print(f"  {result.name:<32} {status:<9} {result.duration_seconds:.2f}s")
    accumulated = sum(result.duration_seconds for result in results)
    print(f"  {'Total wall time':<42} {wall_seconds:.2f}s")
    print(f"  {'Accumulated step time':<42} {accumulated:.2f}s")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the fast local skill release gate")
    parser.add_argument("--verbose", action="store_true", help="stream full child-process output")
    parser.add_argument("--quality-policy", type=Path, default=DEFAULT_QUALITY_POLICY)
    parser.add_argument("--quality-allowlist", type=Path, default=DEFAULT_QUALITY_ALLOWLIST)
    parser.add_argument("--quality-artifact", type=Path, default=DEFAULT_QUALITY_ARTIFACT)
    parser.add_argument("--quality-max-missing-field-alerts", type=int)
    parser.add_argument("--quality-min-average-coverage", type=float)
    parser.add_argument("--quality-max-route-conflicts", type=int)
    parser.add_argument("--quality-max-duplicate-patterns", type=int)
    parser.add_argument("--quality-max-weak-strong-overlaps", type=int)
    parser.add_argument("--quality-max-broad-patterns", type=int)
    parser.add_argument("--quality-max-multi-match-fixtures", type=int)
    parser.add_argument("--strict", action="store_true", help="fail on quality gate warnings (CI-style strict mode)")
    parser.add_argument("--sequential", action="store_true", help="run steps sequentially (default: parallel)")
    parser.add_argument(
        "--timeout", type=float, default=300.0, metavar="SECONDS",
        help="per-step timeout in seconds (default: 300)",
    )
    parser.add_argument(
        "--only", "--filter", dest="filters", action="append", default=[], metavar="STEP",
        help="run only matching step name/slug; repeatable (for example: --only serial-mcp)",
    )
    args = parser.parse_args()

    if args.timeout <= 0:
        parser.error("--timeout must be greater than zero")

    policy_fingerprint, policy_mtime = _file_fingerprint(args.quality_policy)
    allowlist_fingerprint, allowlist_mtime = _file_fingerprint(args.quality_allowlist)
    print(f"[INFO] quality policy {args.quality_policy}: md5={policy_fingerprint} mtime={policy_mtime}")
    print(f"[INFO] conflict allowlist {args.quality_allowlist}: md5={allowlist_fingerprint} mtime={allowlist_mtime}")

    quality_strict = _resolve_quality_strict(args)
    print(
        f"[INFO] quick gate quality strict mode: {quality_strict} "
        f"(CI={_is_ci_environment()}, override={os.getenv('SKILL_QUICK_GATE_STRICT')!r})"
    )

    steps = STEPS.copy()
    steps.insert(5, _build_route_quality_step(args, strict=quality_strict))
    steps.insert(14, _build_coverage_step(strict=quality_strict))
    steps.insert(15, _build_checker_registry_step(strict=quality_strict))
    steps.insert(16, GateStep("architecture sync", [sys.executable, "scripts/check_architecture_sync.py"]))
    steps = _select_steps(steps, args.filters)
    if args.filters and not steps:
        available = ", ".join(_step_slug(step.name) for step in STEPS)
        parser.error(f"no gate steps match {args.filters!r}; available: {available}")
    steps = [replace(step, timeout_seconds=args.timeout) for step in steps]
    total = len(steps)

    failed: list[str] = []
    completed: list[StepResult] = []
    gate_started = time.monotonic()

    if args.sequential:
        # Sequential mode: original behavior
        for index, step in enumerate(steps, start=1):
            result = run_step_capture(index, step)
            completed.append(result)
            print_step_result(result, total)
            if not result.passed:
                failed.append(result.name)
    else:
        # Parallel mode: run all steps concurrently, print results in order
        print(f"[INFO] Running {total} gate steps in parallel (max_workers=4)")
        results_by_index: dict[int, StepResult] = {}

        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = {
                pool.submit(run_step_capture, index, step): index
                for index, step in enumerate(steps, start=1)
            }
            for future in as_completed(futures):
                result = future.result()
                results_by_index[result.index] = result

        # Print results in original order
        for index in sorted(results_by_index.keys()):
            result = results_by_index[index]
            completed.append(result)
            print_step_result(result, total)
            if not result.passed:
                failed.append(result.name)

    print_timing_summary(completed, time.monotonic() - gate_started)

    if failed:
        print("\nQuick gate failed:")
        for name in failed:
            print(f"  - {name}")
        return 1

    print("\nQuick gate passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
