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
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_QUALITY_POLICY = ROOT / "references" / "log_symptom_routes_quality_policy.json"
DEFAULT_QUALITY_ALLOWLIST = ROOT / "references" / "log_symptom_route_conflict_allowlist.json"
DEFAULT_QUALITY_ARTIFACT = ROOT / "artifacts" / "log_symptom_routes_quality.json"


@dataclass(frozen=True)
class GateStep:
    name: str
    cmd: list[str]


STEPS = [
    GateStep("review self-test", [sys.executable, "tools/run_review.py", "--self-test"]),
    GateStep("review examples", [sys.executable, "tools/run_review.py", "--validate-examples"]),
    GateStep("log triage self-test", [sys.executable, "tools/log_triage.py", "--self-test"]),
    GateStep("log triage batch self-test", [sys.executable, "tools/log_triage_batch.py", "--self-test"]),
    GateStep("log triage matrix", [sys.executable, "scripts/check_log_triage_matrix.py"]),
    GateStep("project gate self-test", [sys.executable, "tools/project_gate.py", "--self-test"]),
    GateStep("repro bundle self-test", [sys.executable, "tools/repro_bundle.py", "--self-test"]),
    GateStep("context router self-test", [sys.executable, "tools/context_router.py", "--self-test"]),
    GateStep("post-install smoke self-test", [sys.executable, "scripts/post_install_smoke.py", "--self-test"]),
    GateStep("skill metadata", [sys.executable, "scripts/check_skill_metadata.py"]),
    GateStep("runtime distribution", [sys.executable, "scripts/check_runtime_distribution.py"]),
    GateStep("link check", [sys.executable, "tools/check_links.py"]),
]



def _env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    return env


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


def run_step(index: int, total: int, step: GateStep, *, verbose: bool) -> bool:
    cmd_text = " ".join(step.cmd)
    print(f"[{index}/{total}] {step.name}")
    print(f"  {cmd_text}")

    if verbose:
        proc = subprocess.run(step.cmd, cwd=ROOT, env=_env())
        if proc.returncode == 0:
            print(f"  PASS {step.name}")
            return True
        print(f"  FAIL {step.name}: exit {proc.returncode}")
        return False

    proc = subprocess.run(
        step.cmd,
        cwd=ROOT,
        env=_env(),
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode == 0:
        print(f"  PASS {step.name}")
        return True

    print(f"  FAIL {step.name}: exit {proc.returncode}")
    _print_failure_output(proc)
    return False


def _build_route_quality_step(args: argparse.Namespace) -> GateStep:
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
    if args.strict:
        command.append("--strict")
    return GateStep("log symptom routes quality", command)


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
    args = parser.parse_args()

    policy_fingerprint, policy_mtime = _file_fingerprint(args.quality_policy)
    allowlist_fingerprint, allowlist_mtime = _file_fingerprint(args.quality_allowlist)
    print(f"[INFO] quality policy {args.quality_policy}: md5={policy_fingerprint} mtime={policy_mtime}")
    print(f"[INFO] conflict allowlist {args.quality_allowlist}: md5={allowlist_fingerprint} mtime={allowlist_mtime}")

    steps = STEPS.copy()
    steps.insert(5, _build_route_quality_step(args))

    failed: list[str] = []
    total = len(steps)

    for index, step in enumerate(steps, start=1):
        if not run_step(index, total, step, verbose=args.verbose):
            failed.append(step.name)

    if failed:
        print("\nQuick gate failed:")
        for name in failed:
            print(f"  - {name}")
        return 1

    print("\nQuick gate passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())