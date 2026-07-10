#!/usr/bin/env python3
"""Quick gate step: run LVGL golden page regression (non-blocking).

Skips gracefully if golden_pages/ is missing or empty.
Returns non-zero when regression is failed/incomplete; quick_gate marks this step
non-blocking and prints WARN instead of failing the release gate.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GOLDEN_DIR = ROOT / "golden_pages"


def main() -> int:
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
        return 1

    total = report.get("total", 0)
    passed = report.get("passed", 0)
    passed_with_warnings = report.get("passed_with_warnings", 0)
    failed = report.get("failed", 0)
    incomplete = report.get("incomplete", 0)

    if failed > 0 or incomplete > 0 or proc.returncode != 0:
        print(
            f"[WARN] LVGL regression: {passed}/{total} passed, "
            f"{failed} failed, {incomplete} incomplete (non-blocking)"
        )
        for page in report.get("pages", []):
            if page.get("verdict") in {"failed", "incomplete"}:
                file_stage = page.get("stages", {}).get("file_check", {})
                detail = page.get("failed_stages") or file_stage.get("missing", [])
                print(f"  - {page['page']}: {detail}")
        return 1
    elif passed_with_warnings > 0:
        print(f"[WARN] LVGL regression: {passed}/{total} passed, {passed_with_warnings} with warnings")
    else:
        print(f"[OK] LVGL regression: {passed}/{total} regression_passed")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
