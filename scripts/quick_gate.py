#!/usr/bin/env python3
"""Run the fast local release gate for this skill.

This intentionally avoids git history and install-state checks so it can be
used during normal iteration before a commit is ready.
"""
from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class GateStep:
    name: str
    cmd: list[str]


STEPS = [
    GateStep("review self-test", [sys.executable, "tools/run_review.py", "--self-test"]),
    GateStep("review examples", [sys.executable, "tools/run_review.py", "--validate-examples"]),
    GateStep("log triage self-test", [sys.executable, "tools/log_triage.py", "--self-test"]),
    GateStep("log triage matrix", [sys.executable, "scripts/check_log_triage_matrix.py"]),
    GateStep("context router self-test", [sys.executable, "tools/context_router.py", "--self-test"]),
    GateStep("skill metadata", [sys.executable, "scripts/check_skill_metadata.py"]),
    GateStep("runtime distribution", [sys.executable, "scripts/check_runtime_distribution.py"]),
    GateStep("link check", [sys.executable, "tools/check_links.py"]),
]


def _env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    return env


def run_step(index: int, total: int, step: GateStep) -> bool:
    print(f"[{index}/{total}] {step.name}")
    print("  " + " ".join(step.cmd))
    proc = subprocess.run(step.cmd, cwd=ROOT, env=_env())
    if proc.returncode == 0:
        print(f"  PASS {step.name}")
        return True
    print(f"  FAIL {step.name}: exit {proc.returncode}")
    return False


def main() -> int:
    failed: list[str] = []
    total = len(STEPS)

    for index, step in enumerate(STEPS, start=1):
        if not run_step(index, total, step):
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
