#!/usr/bin/env python3
"""
Installed version sync check — compare repository and installed package versions.

Usage:
    python scripts/check_installed_skill_sync.py
    python scripts/check_installed_skill_sync.py --strict
    python scripts/check_installed_skill_sync.py --self-test
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INSTALL_DIR = Path(os.environ.get("USERPROFILE", "")) / ".codex" / "skills" / "freertos-embedded-architect"


def get_version(root: Path) -> str | None:
    """Extract ``[project].version`` from pyproject.toml."""
    path = root / "pyproject.toml"
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    project = re.search(r"^\[project\]\s*$([\s\S]*?)(?=^\[|\Z)", text, re.MULTILINE)
    if not project:
        return None
    match = re.search(r'^version\s*=\s*["\']([^"\']+)["\']', project.group(1), re.MULTILINE)
    return match.group(1) if match else None


def check_sync(install_dir: Path, strict: bool = False) -> dict:
    """Check installed version against repo version sync status."""
    repo_version = get_version(ROOT)
    install_version = get_version(install_dir)

    result = {
        "repo_version": repo_version,
        "install_dir": str(install_dir),
        "install_exists": install_dir.exists(),
        "install_version": install_version,
        "passed": True,
        "issues": [],
    }

    if not install_dir.exists():
        msg = f"Install directory does not exist: {install_dir}"
        if strict:
            result["passed"] = False
            result["issues"].append(msg)
        else:
            result["issues"].append(f"[warning] {msg}")
        return result

    if not install_version:
        result["passed"] = False
        result["issues"].append("Installed pyproject.toml missing [project].version")
        return result

    if repo_version and install_version != repo_version:
        msg = f"Version mismatch: repo={repo_version}, installed={install_version}"
        if strict:
            result["passed"] = False
            result["issues"].append(msg)
        else:
            result["issues"].append(f"[warning] {msg}")

    return result


def run_self_test() -> int:
    passed = 0
    failed = 0

    import tempfile

    # 1. Non-existent install directory (non-strict)
    r = check_sync(Path("/nonexistent/path"), strict=False)
    assert r["passed"] is True
    assert any("does not exist" in i for i in r["issues"])
    print("[PASS] missing install dir (non-strict) → warning")
    passed += 1

    # 2. Non-existent install directory (strict)
    r = check_sync(Path("/nonexistent/path"), strict=True)
    assert r["passed"] is False
    print("[PASS] missing install dir (strict) → fail")
    passed += 1

    # 3. Version match
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        (tmp / "pyproject.toml").write_text(
            '[project]\nname = "fixture"\nversion = "1.0.0"\n', encoding="utf-8"
        )
        r = check_sync(tmp, strict=True)
        assert r["passed"] is False
        assert any("mismatch" in i for i in r["issues"])
        print("[PASS] version mismatch → fail")
        passed += 1

    print(f"\nSelf-test: {passed} passed, {failed} failed")
    return 1 if failed > 0 else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Installed version sync check")
    parser.add_argument("--install-dir", default=str(DEFAULT_INSTALL_DIR), help="Install directory")
    parser.add_argument("--strict", action="store_true", help="Strict mode (fail if not installed)")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    r = check_sync(Path(args.install_dir), strict=args.strict)

    if args.json:
        import json
        print(json.dumps(r, indent=2, ensure_ascii=False))
    else:
        print(f"Repo:     {r['repo_version']}")
        print(f"Installed: {r['install_version'] or '(not installed)'}")
        print(f"Passed:   {r['passed']}")
        for i in r["issues"]:
            print(f"  - {i}")

    return 0 if r["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
