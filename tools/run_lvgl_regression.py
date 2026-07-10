#!/usr/bin/env python3
"""Golden page regression: compare current LVGL render against baseline.

Usage:
    python tools/run_lvgl_regression.py --page golden_pages/loading_page
    python tools/run_lvgl_regression.py --all
    python tools/run_lvgl_regression.py --page golden_pages/loading_page --check
    python tools/run_lvgl_regression.py --page golden_pages/loading_page --compare artifacts/render.png
    python tools/run_lvgl_regression.py --list
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GOLDEN_DIR = ROOT / "golden_pages"


def list_pages() -> int:
    if not GOLDEN_DIR.is_dir():
        print("[ERROR] golden_pages/ directory not found")
        return 1

    pages = sorted(p for p in GOLDEN_DIR.iterdir() if p.is_dir())
    if not pages:
        print("[INFO] No golden pages found")
        return 0

    print(f"{'Page':<25} {'Design':<10} {'Cutouts':<10} {'Expected':<10} {'Status'}")
    print("-" * 70)
    for page in pages:
        has_design = (page / "design.png").is_file()
        cutout_count = len(list((page / "cutouts").glob("*"))) if (page / "cutouts").is_dir() else 0
        expected_dir = page / "expected"
        expected_count = len(list(expected_dir.glob("*"))) if expected_dir.is_dir() else 0

        status = "ready" if has_design and expected_count > 0 else "pending"
        print(f"{page.name:<25} {'yes' if has_design else 'no':<10} {cutout_count:<10} {expected_count:<10} {status}")

    return 0


def check_page(page_dir: Path) -> int:
    """Check a golden page has all required files."""
    errors = []

    if not page_dir.is_dir():
        print(f"[ERROR] Page directory not found: {page_dir}")
        return 1

    # Required inputs
    if not (page_dir / "design.png").is_file():
        errors.append("missing: design.png")

    # Required expected outputs
    expected_dir = page_dir / "expected"
    required_expected = [
        "analysis_report.json",
        "cutout_audit.json",
        "render.png",
        "manifest.json",
    ]
    for f in required_expected:
        if not (expected_dir / f).is_file():
            errors.append(f"missing: expected/{f}")

    if errors:
        print(f"[WARN] {page_dir.name}: {len(errors)} issues")
        for e in errors:
            print(f"  - {e}")
        return 1

    print(f"[OK] {page_dir.name}: all files present")
    return 0


def compare_renders(baseline_path: Path, current_path: Path, threshold: float = 0.01) -> dict:
    """Compare two render PNGs. Returns diff report."""
    try:
        from PIL import Image
        import numpy as np
    except ImportError:
        return {"error": "Pillow/numpy not installed", "match": False}

    if not baseline_path.is_file():
        return {"error": f"baseline not found: {baseline_path}", "match": False}
    if not current_path.is_file():
        return {"error": f"current not found: {current_path}", "match": False}

    baseline = np.array(Image.open(baseline_path).convert("RGB"))
    current = np.array(Image.open(current_path).convert("RGB"))

    if baseline.shape != current.shape:
        return {
            "match": False,
            "error": f"size mismatch: baseline={baseline.shape} current={current.shape}",
        }

    diff = np.abs(baseline.astype(int) - current.astype(int))
    changed_pixels = np.any(diff > 8, axis=2).sum()
    total_pixels = baseline.shape[0] * baseline.shape[1]
    changed_ratio = changed_pixels / total_pixels

    return {
        "match": changed_ratio <= threshold,
        "changed_ratio": round(changed_ratio, 6),
        "changed_pixels": int(changed_pixels),
        "total_pixels": int(total_pixels),
        "max_channel_delta": int(diff.max()),
        "threshold": threshold,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Golden page regression")
    parser.add_argument("--page", help="Page directory to check/compare")
    parser.add_argument("--all", action="store_true", help="Check all golden pages")
    parser.add_argument("--list", action="store_true", help="List all golden pages")
    parser.add_argument("--check", action="store_true", help="Check page has all required files")
    parser.add_argument("--compare", help="Compare with this render PNG")
    parser.add_argument("--threshold", type=float, default=0.01, help="Changed ratio threshold")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    if args.list:
        return list_pages()

    if args.all:
        if not GOLDEN_DIR.is_dir():
            print("[ERROR] golden_pages/ directory not found")
            return 1
        exit_code = 0
        for p in sorted(GOLDEN_DIR.iterdir()):
            if p.is_dir() and check_page(p) != 0:
                exit_code = 1
        return exit_code

    if not args.page:
        parser.error("--page, --all, or --list is required")

    page_dir = Path(args.page)
    if not page_dir.is_absolute():
        page_dir = ROOT / page_dir

    if args.check:
        return check_page(page_dir)

    if args.compare:
        baseline = page_dir / "expected" / "render.png"
        current = Path(args.compare)
        if not current.is_absolute():
            current = ROOT / current
        result = compare_renders(baseline, current, args.threshold)
        if args.json:
            json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
            print()
        else:
            if result.get("match"):
                print(f"[PASS] renders match (changed_ratio={result['changed_ratio']})")
            else:
                print(f"[FAIL] renders differ: {result}")
        return 0 if result.get("match") else 1

    # Default: check one page.
    if page_dir.is_dir() and (page_dir / "expected").is_dir():
        return check_page(page_dir)

    parser.error("--check, --compare, or --all is required")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
