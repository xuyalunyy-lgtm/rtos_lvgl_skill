#!/usr/bin/env python3
"""Smoke-test an installed freertos-embedded-architect skill directory."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INSTALL_DIR = Path(os.environ.get("USERPROFILE", "")) / ".codex" / "skills" / "freertos-embedded-architect"


def run(cmd: list[str], cwd: Path) -> tuple[int, str]:
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    return proc.returncode, (proc.stdout + proc.stderr)


def smoke(install_dir: Path) -> list[str]:
    issues: list[str] = []
    required = [
        "SKILL.md",
        "tools/run_review.py",
        "tools/log_triage.py",
        "tools/log_triage_batch.py",
        "tools/project_gate.py",
        "scripts/check_skill_metadata.py",
    ]
    for rel in required:
        if not (install_dir / rel).is_file():
            issues.append(f"missing {rel}")

    if issues:
        return issues

    checks = [
        [sys.executable, "scripts/check_skill_metadata.py"],
        [sys.executable, "tools/log_triage_batch.py", "--self-test"],
        [sys.executable, "tools/project_gate.py", "--self-test"],
        [
            sys.executable,
            "tools/log_triage.py",
            "--log",
            "tools/fixtures/logs/bad_zephyr_kernel_oops.log",
            "--platform",
            "zephyr",
            "--json",
        ],
    ]
    for cmd in checks:
        rc, out = run(cmd, install_dir)
        if rc != 0:
            issues.append(f"{' '.join(cmd)} failed rc={rc}: {out[-500:]}")

    return issues


def run_self_test() -> int:
    issues = smoke(ROOT)
    assert not issues, issues
    print("post_install_smoke self-test passed")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-test installed skill runtime")
    parser.add_argument("--install-dir", default=str(DEFAULT_INSTALL_DIR))
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    install_dir = Path(args.install_dir)
    issues = smoke(install_dir)
    if issues:
        print("Post-install smoke failed:")
        for issue in issues:
            print(f"  - {issue}")
        return 1
    print(f"Post-install smoke passed: {install_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
