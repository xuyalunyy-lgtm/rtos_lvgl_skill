#!/usr/bin/env python3
"""Quick gate step: run LVGL golden page regression (non-blocking).

Skips gracefully if golden_pages/ is missing or empty.
Exit 0 always (warning-only); actual failures are printed for visibility.

Usage:
    python scripts/check_lvgl_regression.py
    python scripts/check_lvgl_regression.py --self-test
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GOLDEN_DIR = ROOT / "golden_pages"


def run_regression() -> int:
    """Run LVGL regression, non-blocking."""
    if not GOLDEN_DIR.is_dir():
        print("[SKIP] golden_pages/ not found")
        return 0

    pages = [p for p in GOLDEN_DIR.iterdir() if p.is_dir()]
    if not pages:
        print("[SKIP] golden_pages/ is empty")
        return 0

    proc = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "run_lvgl_regression.py"), "--all", "--json"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )

    try:
        report = json.loads(proc.stdout)
    except (json.JSONDecodeError, ValueError):
        print(f"[WARN] regression output not parseable: {proc.stdout[:200]}")
        return 0  # non-blocking

    total = report.get("total", 0)
    passed = report.get("passed", 0)
    failed = report.get("failed", 0)

    if failed > 0:
        print(f"[WARN] LVGL regression: {passed}/{total} passed, {failed} failed (non-blocking)")
        for page in report.get("pages", []):
            if page.get("verdict") == "failed":
                print(f"  - {page['page']}: {page.get('failed_stages', [])}")
    else:
        print(f"[OK] LVGL regression: {passed}/{total} passed")

    return 0  # always non-blocking


def run_self_test() -> int:
    """Self-test for the non-blocking wrapper."""
    passed = 0
    failed = 0

    def check(name: str, condition: bool, detail: str = ""):
        nonlocal passed, failed
        if condition:
            passed += 1
            print(f"  PASS: {name}")
        else:
            failed += 1
            msg = f"  FAIL: {name}"
            if detail:
                msg += f" ({detail})"
            print(msg)

    print("check_lvgl_regression.py - self-test")

    # Test 1: real golden pages pass
    if GOLDEN_DIR.is_dir():
        pages = [p for p in GOLDEN_DIR.iterdir() if p.is_dir()]
        if pages:
            proc = subprocess.run(
                [sys.executable, str(ROOT / "tools" / "run_lvgl_regression.py"), "--all", "--json"],
                cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
            )
            try:
                report = json.loads(proc.stdout)
                check("real golden pages: all pass",
                      report.get("failed", 0) == 0,
                      f"failed={report.get('failed', 0)}")
            except (json.JSONDecodeError, ValueError):
                check("real golden pages: parseable output", False, "JSON parse error")
        else:
            check("golden_pages exists but empty (skip)", True)
    else:
        check("golden_pages/ not found (skip)", True)

    # Test 2: regression tool --self-test passes
    proc = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "run_lvgl_regression.py"), "--self-test"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    check("run_lvgl_regression.py --self-test passes",
          proc.returncode == 0,
          f"exit={proc.returncode}")

    # Test 3: wrapper always returns 0
    rc = run_regression()
    check("wrapper always returns 0", rc == 0, f"exit={rc}")

    print(f"\nSelf-test: {passed} passed, {failed} failed")
    return 0 if failed == 0 else 1


def main() -> int:
    if "--self-test" in sys.argv:
        return run_self_test()
    return run_regression()


if __name__ == "__main__":
    raise SystemExit(main())
