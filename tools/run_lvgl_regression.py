#!/usr/bin/env python3
"""Golden page regression pipeline.

Runs: file check -> IR validation -> cutout audit -> visual diff -> unified report.

Usage:
    python tools/run_lvgl_regression.py --all                # full pipeline on all pages
    python tools/run_lvgl_regression.py --page golden_pages/loading_page
    python tools/run_lvgl_regression.py --list               # list pages and status
    python tools/run_lvgl_regression.py --all --json         # JSON output
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GOLDEN_DIR = ROOT / "golden_pages"
TOOLS_DIR = ROOT / "tools"


PASS_VERDICTS = {"regression_passed", "regression_passed_with_warnings"}


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _split_issues(issues: list[dict]) -> tuple[list[dict], list[dict]]:
    errors = [i for i in issues if i.get("level") == "error"]
    warnings = [i for i in issues if i.get("level") == "warning"]
    return errors, warnings


def list_pages() -> list[dict]:
    """List all golden pages with unified regression status."""
    if not GOLDEN_DIR.is_dir():
        return []

    pages = []
    for page_dir in sorted(GOLDEN_DIR.iterdir()):
        if not page_dir.is_dir():
            continue
        pipeline = regression_pipeline(page_dir)
        has_design = (page_dir / "design.png").is_file()
        cutout_count = len(list((page_dir / "cutouts").glob("*"))) if (page_dir / "cutouts").is_dir() else 0
        expected_dir = page_dir / "expected"
        expected_files = [f.name for f in expected_dir.iterdir()] if expected_dir.is_dir() else []

        pages.append({
            "name": page_dir.name,
            "path": _rel(page_dir),
            "has_design": has_design,
            "cutout_count": cutout_count,
            "expected_files": len(expected_files),
            "status": pipeline["verdict"],
            "failed_stages": pipeline.get("failed_stages", []),
        })
    return pages


def run_check(script: str, args: list[str], *, json_mode: bool = False) -> tuple[int, dict, str]:
    """Run a checker script and return (exit_code, parsed_json_or_empty, diagnostic)."""
    argv = [sys.executable, str(TOOLS_DIR / script), *args]
    if json_mode:
        argv.append("--json")
    proc = subprocess.run(
        argv, cwd=ROOT, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    result = {}
    if json_mode and proc.stdout.strip():
        try:
            result = json.loads(proc.stdout)
        except json.JSONDecodeError:
            return proc.returncode, {}, proc.stdout[:500]
    return proc.returncode, result, proc.stderr.strip()


def regression_pipeline(page_dir: Path) -> dict:
    """Run full regression pipeline on a single golden page."""
    page_name = page_dir.name
    expected_dir = page_dir / "expected"
    design_path = page_dir / "design.png"
    render_path = expected_dir / "render.png"

    result = {
        "page": page_name,
        "path": _rel(page_dir),
        "stages": {},
        "verdict": "unknown",
    }

    # Stage 1: File completeness
    required = ["analysis_report.json", "cutout_audit.json", "render.png", "manifest.json"]
    missing = []
    if not page_dir.is_dir():
        missing.append(".")
    if not expected_dir.is_dir():
        missing.append("expected/")
    missing.extend(f"expected/{f}" for f in required if not (expected_dir / f).is_file())
    has_design = design_path.is_file()
    if not has_design:
        missing.append("design.png")
    stage1 = {
        "name": "file_check",
        "pass": has_design and len(missing) == 0,
        "has_design": has_design,
        "missing": missing,
        "warnings": [],
        "errors": [],
    }
    result["stages"]["file_check"] = stage1
    if not stage1["pass"]:
        result["verdict"] = "incomplete"
        return result

    # Stage 2: IR validation (analysis_report.json)
    _rc2, ir_result, ir_diag = run_check("validate_cutout_audit.py", [_rel(page_dir)], json_mode=True)
    page_result = ir_result.get("pages", {}).get(page_name)
    if page_result is None:
        validation_error = [{
            "level": "error",
            "rule": "validation_output_missing",
            "message": ir_diag or "validate_cutout_audit.py did not return page results",
        }]
        report_issues = validation_error
        audit_issues = validation_error
    else:
        report_issues = page_result.get("report_issues", [])
        audit_issues = page_result.get("audit_issues", [])

    report_errors, report_warnings = _split_issues(report_issues)
    audit_errors, audit_warnings = _split_issues(audit_issues)
    stage2 = {
        "name": "ir_validation",
        "pass": len(report_errors) == 0,
        "errors": report_errors,
        "warnings": report_warnings,
    }
    result["stages"]["ir_validation"] = stage2

    # Stage 3: Cutout audit validation
    stage3 = {
        "name": "cutout_audit",
        "pass": len(audit_errors) == 0,
        "errors": audit_errors,
        "warnings": audit_warnings,
    }
    result["stages"]["cutout_audit"] = stage3

    # Stage 4: Visual diff (design vs expected render)
    with tempfile.TemporaryDirectory(prefix="lvgl_regression_") as tmp_dir:
        rc4, diff_result, diff_diag = run_check(
            "visual_diff.py",
            [_rel(design_path), _rel(render_path), "--output", tmp_dir],
            json_mode=True,
        )
    diff_verdict = diff_result.get("verdict", "unknown")
    diff_errors = []
    diff_warnings = []
    if rc4 != 0 and diff_verdict != "warn":
        diff_errors.append({
            "level": "error",
            "rule": "visual_diff_failed",
            "message": diff_result.get("error") or diff_diag or f"visual diff exited {rc4}",
        })
    elif diff_verdict == "warn":
        diff_warnings.append({
            "level": "warning",
            "rule": "visual_diff_warn",
            "message": f"changed_ratio={diff_result.get('changed_ratio', -1)}",
        })

    stage4 = {
        "name": "visual_diff",
        "pass": diff_verdict in {"pass", "warn"} and len(diff_errors) == 0,
        "verdict": diff_verdict,
        "changed_ratio": diff_result.get("changed_ratio", -1),
        "max_delta": diff_result.get("max_channel_delta", -1),
        "bbox_mismatch_count": diff_result.get("bbox_mismatch_count", -1),
        "missing_regions": diff_result.get("missing_regions", -1),
        "errors": diff_errors,
        "warnings": diff_warnings,
    }
    result["stages"]["visual_diff"] = stage4

    # Overall verdict
    all_pass = all(s.get("pass", False) for s in result["stages"].values())
    any_warn = any(s.get("warnings") for s in result["stages"].values())
    if all_pass and not any_warn:
        result["verdict"] = "regression_passed"
    elif all_pass:
        result["verdict"] = "regression_passed_with_warnings"
    else:
        failed_stages = [s["name"] for s in result["stages"].values() if not s.get("pass")]
        result["verdict"] = "failed"
        result["failed_stages"] = failed_stages

    return result


def _make_page(tmp_dir: Path, name: str, *, design: bool = True, render: bool = True,
               report: bool = True, audit: bool = True, manifest: bool = True,
               bad_report: bool = False, bad_audit: bool = False,
               render_size: tuple[int, int] | None = None) -> Path:
    """Create a minimal golden page fixture in tmp_dir."""
    from PIL import Image
    import numpy as np

    page_dir = tmp_dir / name
    expected = page_dir / "expected"
    expected.mkdir(parents=True, exist_ok=True)
    (page_dir / "cutouts").mkdir(exist_ok=True)

    W, H = 480, 800
    if design:
        img = np.zeros((H, W, 3), dtype=np.uint8)
        img[:, :] = [26, 26, 46]
        Image.fromarray(img).save(page_dir / "design.png")

    if render:
        rw, rh = render_size or (W, H)
        img = np.zeros((rh, rw, 3), dtype=np.uint8)
        img[:, :] = [26, 26, 46]
        Image.fromarray(img).save(expected / "render.png")

    if report:
        if bad_report:
            report_data = {"screen": {"width": 480}}
        else:
            report_data = {
                "screen": {"width": W, "height": H},
                "assets": [],
                "components": [{"id": "root", "type": "container", "bbox": [0, 0, W, H],
                                "source": "layout_root", "confidence": 1.0}],
                "layout_policy": {"mode": "pixel_exact"},
                "warnings": [],
            }
        (expected / "analysis_report.json").write_text(
            json.dumps(report_data, indent=2), encoding="utf-8")

    if audit:
        if bad_audit:
            audit_data = {"page_name": name, "audit_version": "1.0",
                          "cutouts": [{"filename": "x.png", "status": "bad_status"}], "summary": {}}
        else:
            audit_data = {"page_name": name, "audit_version": "1.0", "cutouts": [],
                          "summary": {"total": 0, "used_cutout": 0, "used_component_calibration": 0,
                                      "duplicate_or_low_confidence": 0, "unmatched_or_state_variant": 0}}
        (expected / "cutout_audit.json").write_text(
            json.dumps(audit_data, indent=2), encoding="utf-8")

    if manifest:
        (expected / "manifest.json").write_text(
            json.dumps({"page_name": name, "assets": []}), encoding="utf-8")

    return page_dir


def run_self_test() -> int:
    """Run failure-mode self-tests using temp directories."""
    from PIL import Image
    import numpy as np

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

    print("run_lvgl_regression.py - failure-mode self-test")

    # 1: incomplete - missing render.png
    with tempfile.TemporaryDirectory() as tmp:
        r = regression_pipeline(_make_page(Path(tmp), "no_render", render=False))
        check("incomplete: missing render.png", r["verdict"] == "incomplete", f"got {r['verdict']}")

    # 2: incomplete - missing analysis_report.json
    with tempfile.TemporaryDirectory() as tmp:
        r = regression_pipeline(_make_page(Path(tmp), "no_report", report=False))
        check("incomplete: missing analysis_report.json", r["verdict"] == "incomplete", f"got {r['verdict']}")

    # 3: incomplete - missing design.png
    with tempfile.TemporaryDirectory() as tmp:
        r = regression_pipeline(_make_page(Path(tmp), "no_design", design=False))
        check("incomplete: missing design.png", r["verdict"] == "incomplete", f"got {r['verdict']}")

    # 4: failed.ir_validation - bad IR
    with tempfile.TemporaryDirectory() as tmp:
        r = regression_pipeline(_make_page(Path(tmp), "bad_ir", bad_report=True))
        check("failed: bad IR (missing keys)",
              r["verdict"] == "failed" and "ir_validation" in r.get("failed_stages", []),
              f"got {r['verdict']}")

    # 5: failed.cutout_audit - bad audit status
    with tempfile.TemporaryDirectory() as tmp:
        r = regression_pipeline(_make_page(Path(tmp), "bad_audit", bad_audit=True))
        check("failed: bad cutout audit (invalid status)",
              r["verdict"] == "failed" and "cutout_audit" in r.get("failed_stages", []),
              f"got {r['verdict']}")

    # 6: failed.visual_diff - size mismatch
    with tempfile.TemporaryDirectory() as tmp:
        r = regression_pipeline(_make_page(Path(tmp), "size_mismatch", render_size=(240, 400)))
        check("failed: visual diff size mismatch",
              r["verdict"] == "failed" and "visual_diff" in r.get("failed_stages", []),
              f"got {r['verdict']}")

    # 7: regression_passed - identical images
    with tempfile.TemporaryDirectory() as tmp:
        r = regression_pipeline(_make_page(Path(tmp), "identical"))
        check("regression_passed: identical images", r["verdict"] == "regression_passed", f"got {r['verdict']}")

    # 8: regression_passed_with_warnings - slight diff
    with tempfile.TemporaryDirectory() as tmp:
        page_dir = Path(tmp) / "slight_diff"
        expected = page_dir / "expected"
        expected.mkdir(parents=True)
        (page_dir / "cutouts").mkdir()

        design = np.zeros((800, 480, 3), dtype=np.uint8)
        design[:, :] = [26, 26, 46]
        Image.fromarray(design).save(page_dir / "design.png")

        # Render with diff in warn range (50x80 block = 4000 pixels, ~1% of 384000)
        render = design.copy()
        render[100:150, 100:180, :] = [200, 200, 200]
        Image.fromarray(render).save(expected / "render.png")

        report_data = {"screen": {"width": 480, "height": 800}, "assets": [],
                       "components": [{"id": "root", "type": "container", "bbox": [0, 0, 480, 800],
                                       "source": "layout_root", "confidence": 1.0}],
                       "layout_policy": {}, "warnings": []}
        (expected / "analysis_report.json").write_text(json.dumps(report_data), encoding="utf-8")
        audit_data = {"page_name": "slight_diff", "audit_version": "1.0", "cutouts": [],
                      "summary": {"total": 0, "used_cutout": 0, "used_component_calibration": 0,
                                  "duplicate_or_low_confidence": 0, "unmatched_or_state_variant": 0}}
        (expected / "cutout_audit.json").write_text(json.dumps(audit_data), encoding="utf-8")
        (expected / "manifest.json").write_text(json.dumps({"page_name": "slight_diff", "assets": []}), encoding="utf-8")

        r = regression_pipeline(page_dir)
        v4 = r["stages"].get("visual_diff", {})
        check("warn: slight diff triggers warning",
              r["verdict"] == "regression_passed_with_warnings",
              f"got {r['verdict']} diff_verdict={v4.get('verdict')}")

    # 9: non-existent page directory
    r = regression_pipeline(Path("/nonexistent/path"))
    check("incomplete: non-existent page", r["verdict"] == "incomplete", f"got {r['verdict']}")

    print(f"\nSelf-test: {passed} passed, {failed} failed")
    return 0 if failed == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Golden page regression pipeline")
    parser.add_argument("--page", help="Page directory to run regression on")
    parser.add_argument("--all", action="store_true", help="Run on all golden pages")
    parser.add_argument("--list", action="store_true", help="List pages and status")
    parser.add_argument("--self-test", action="store_true", help="Run failure-mode self-tests")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    if args.list:
        pages = list_pages()
        if args.json:
            json.dump(pages, sys.stdout, ensure_ascii=False, indent=2)
            print()
        else:
            print(f"{'Page':<25} {'Design':<10} {'Cutouts':<10} {'Expected':<10} {'Status'}")
            print("-" * 70)
            for p in pages:
                print(f"{p['name']:<25} {'yes' if p['has_design'] else 'no':<10} "
                      f"{p['cutout_count']:<10} {p['expected_files']:<10} {p['status']}")
        return 0

    if not args.page and not args.all:
        parser.error("--page, --all, or --list is required")

    # Collect pages
    if args.all:
        if not GOLDEN_DIR.is_dir():
            print("[ERROR] golden_pages/ not found")
            return 1
        page_dirs = sorted(p for p in GOLDEN_DIR.iterdir() if p.is_dir())
    else:
        p = Path(args.page)
        if not p.is_absolute():
            p = ROOT / p
        page_dirs = [p]

    # Run pipeline
    results = []
    for page_dir in page_dirs:
        r = regression_pipeline(page_dir)
        results.append(r)

    # Output
    if args.json:
        summary = {
            "total": len(results),
            "passed": sum(1 for r in results if r["verdict"] in PASS_VERDICTS),
            "passed_with_warnings": sum(1 for r in results if r["verdict"] == "regression_passed_with_warnings"),
            "failed": sum(1 for r in results if r["verdict"] == "failed"),
            "incomplete": sum(1 for r in results if r["verdict"] == "incomplete"),
            "pages": results,
        }
        json.dump(summary, sys.stdout, ensure_ascii=False, indent=2)
        print()
    else:
        for r in results:
            v = r["verdict"]
            icon = {"regression_passed": "PASS", "regression_passed_with_warnings": "WARN",
                    "failed": "FAIL", "incomplete": "SKIP"}.get(v, "???")
            print(f"[{icon}] {r['page']}: {v}")
            for stage in r["stages"].values():
                s_icon = "ok" if stage.get("pass") else "XX"
                extra = ""
                if stage["name"] == "visual_diff" and "changed_ratio" in stage:
                    extra = f" ratio={stage['changed_ratio']:.6f} bbox_miss={stage['bbox_mismatch_count']}"
                print(f"  [{s_icon}] {stage['name']}{extra}")

        passed = sum(1 for r in results if r["verdict"] in PASS_VERDICTS)
        total = len(results)
        print(f"\nSummary: {passed}/{total} passed")

    exit_code = 0 if all(r["verdict"] in PASS_VERDICTS for r in results) else 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
