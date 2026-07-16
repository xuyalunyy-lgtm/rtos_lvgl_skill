#!/usr/bin/env python3
"""Official Skill validator wrapper.

Finds and runs the official Codex/Claude skill validator, falling back
to the repository's custom validator if the official one is unavailable.

Lookup order:
1. Environment variable OFFICIAL_SKILL_VALIDATOR
2. $CODEX_HOME/skills/.system/skill-creator/scripts/quick_validate.py
3. ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py
4. third_party/openai-skill-validator/quick_validate.py (vendored)
5. Fallback: custom check_skill_metadata.py

Usage:
    python scripts/run_official_skill_validator.py .
    python scripts/run_official_skill_validator.py --strict
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _find_validator() -> tuple[str | None, str]:
    """Find the official validator script. Returns (path, source)."""
    # 1. Environment variable
    env_path = os.environ.get("OFFICIAL_SKILL_VALIDATOR", "").strip()
    if env_path and Path(env_path).is_file():
        return env_path, "environment_variable"

    # 2. CODEX_HOME
    codex_home = os.environ.get("CODEX_HOME", "").strip()
    if codex_home:
        candidate = Path(codex_home) / "skills" / ".system" / "skill-creator" / "scripts" / "quick_validate.py"
        if candidate.is_file():
            return str(candidate), "codex_home"

    # 3. Default Codex home when CODEX_HOME is unset
    candidate = Path.home() / ".codex" / "skills" / ".system" / "skill-creator" / "scripts" / "quick_validate.py"
    if candidate.is_file():
        return str(candidate), "default_codex_home"

    # 4. Vendored copy
    vendored = ROOT / "third_party" / "openai-skill-validator" / "quick_validate.py"
    if vendored.is_file():
        return str(vendored), "vendored"

    # 5. Fallback to custom
    custom = ROOT / "scripts" / "check_skill_metadata.py"
    if custom.is_file():
        return str(custom), "custom_fallback"

    return None, "not_found"


def _run_validator(script_path: str, target_dir: str, source: str) -> dict:
    """Run the validator script."""
    if source == "custom_fallback":
        # Custom validator doesn't accept positional args
        cmd = [sys.executable, "-X", "utf8", script_path]
    else:
        cmd = [sys.executable, "-X", "utf8", script_path, target_dir]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            cwd=ROOT,
        )
        return {
            "ok": proc.returncode == 0,
            "exit_code": proc.returncode,
            "source": source,
            "script": script_path,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }
    except Exception as e:
        return {
            "ok": False,
            "exit_code": -1,
            "source": source,
            "script": script_path,
            "error": str(e),
        }


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", nargs="?", default=".", help="Skill directory to validate")
    parser.add_argument("--strict", action="store_true", help="Strict mode")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    target = str(Path(args.target).resolve())
    script, source = _find_validator()

    if script is None:
        result = {
            "ok": False,
            "source": "not_found",
            "error": "No validator found. Set OFFICIAL_SKILL_VALIDATOR or vendor quick_validate.py",
        }
    else:
        result = _run_validator(script, target, source)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"Validator: {result.get('source', 'unknown')}")
        print(f"Script: {result.get('script', 'N/A')}")
        print(f"Status: {'PASS' if result.get('ok') else 'FAIL'}")
        if result.get("stdout"):
            print(result["stdout"])
        if result.get("stderr"):
            print(result["stderr"], file=sys.stderr)
        if result.get("error"):
            print(f"Error: {result['error']}")

    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
