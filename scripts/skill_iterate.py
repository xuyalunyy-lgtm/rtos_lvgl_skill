#!/usr/bin/env python3
"""Run the truthful local release contract for the current skill contents."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECKS = (
    ("review self-test", ["tools/run_review.py", "--self-test"]),
    ("review examples", ["tools/run_review.py", "--validate-examples"]),
    ("runtime distribution", ["scripts/check_runtime_distribution.py"]),
    ("release contract", ["scripts/check_release_contract.py"]),
    ("skill metadata", ["scripts/check_skill_metadata.py"]),
    ("routing table", ["scripts/sync_skill_routing.py", "--check"]),
    ("project doctor", ["tools/project_doctor.py", "--self-test"]),
    ("unit tests", ["-m", "unittest", "discover", "-s", "tests", "-v"]),
    ("mqtt MCP", ["mcp/mqtt_server.py", "--self-test"]),
    ("ota MCP", ["mcp/ota_server.py", "--self-test"]),
    ("serial MCP", ["mcp/serial_server.py", "--self-test"]),
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Run the local release contract (default)")
    parser.add_argument("--skip-self-test", action="store_true", help="Skip only the run_review fixture self-test")
    args = parser.parse_args()
    failures: list[str] = []
    checks = CHECKS[1:] if args.skip_self_test else CHECKS
    for index, (name, command) in enumerate(checks, start=1):
        print(f"[{index}/{len(checks)}] {name}")
        result = subprocess.run([sys.executable, *command], cwd=ROOT)
        if result.returncode:
            failures.append(name)
    if failures:
        print("Skill iteration gate failed: " + ", ".join(failures))
        return 1
    print("Skill iteration gate passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
