#!/usr/bin/env python3
"""Verify authoritative LVGL golden baselines with the bundled simulator.

This is the release gate for the native rendering path.  It deliberately does
not call ``tools/run_lvgl_regression.py``: that tool compares an analysis and
preview pipeline to source design images, which is useful during refinement but
is not a reproducible simulator regression test.

For every page this script encodes the accepted UI Spec, runs the packaged
LVGL v9 runner, then checks the resulting pixels and native object tree against
the accepted native baseline.  A missing/tampered runner or a non-authoritative
baseline is a failure.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
GOLDEN_DIR = ROOT / "golden_pages"
sys.path.insert(0, str(ROOT / "mcp"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _page_dirs() -> list[Path]:
    if not GOLDEN_DIR.is_dir():
        return []
    return sorted(path for path in GOLDEN_DIR.iterdir() if path.is_dir())


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("expected a JSON object")
    return value


def _validate_baseline(expected: Path) -> tuple[dict[str, Any] | None, str | None]:
    manifest_path = expected / "manifest.json"
    spec_path = expected / "ui_spec.json"
    for required in (manifest_path, spec_path, expected / "render.png", expected / "object_tree.bin"):
        if not required.is_file() or required.stat().st_size == 0:
            return None, f"missing required baseline file: {required.name}"
    try:
        manifest = _load_json(manifest_path)
        spec = _load_json(spec_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return None, f"invalid baseline JSON: {exc}"
    if manifest.get("renderer") != "lvgl_simulator" or manifest.get("authoritative") is not True:
        return None, "baseline is not marked as authoritative LVGL simulator output"
    if spec.get("lvgl_version") != "v9":
        return None, f"unsupported baseline lvgl_version: {spec.get('lvgl_version')!r}"
    display = spec.get("display")
    if not isinstance(display, dict) or not all(isinstance(display.get(k), int) and display[k] > 0 for k in ("width", "height")):
        return None, "invalid display dimensions in UI Spec"
    return spec, None


def _compare_pixels(actual: Path, expected: Path) -> tuple[bool, dict[str, Any] | str]:
    try:
        from lvgl_compare import compare
        report = compare(str(actual), str(expected), {"nodes": []})
    except Exception as exc:  # Pillow/numpy or a corrupt image are gate failures.
        return False, f"pixel comparison failed: {exc}"
    changed = report.get("changed_pixel_ratio")
    if changed != 0:
        return False, {
            "changed_pixel_ratio": changed,
            "global_ssim": report.get("global_ssim"),
        }
    return True, {"changed_pixel_ratio": changed, "global_ssim": report.get("global_ssim")}


def run_regression() -> dict[str, Any]:
    """Render all accepted pages and return a machine-readable gate report."""
    from lvgl_ir.scene_encoder import encode_spec
    from lvgl_sim_resolver import resolve_runner, run_runner_self_test, run_simulator

    pages = _page_dirs()
    report: dict[str, Any] = {"ok": False, "total": len(pages), "passed": 0, "failed": 0, "pages": []}
    if not pages:
        report["error"] = "golden_pages/ is missing or empty"
        return report

    runner = resolve_runner("v9")
    report["runner"] = {key: runner.get(key) for key in ("platform", "version", "sha256", "status", "error") if runner.get(key) is not None}
    if not runner.get("ok"):
        report["error"] = runner.get("error", "bundled LVGL runner unavailable")
        report["failed"] = len(pages)
        return report
    self_test = run_runner_self_test(runner["path"])
    if not self_test.get("ok"):
        report["error"] = self_test.get("error", "bundled LVGL runner self-test failed")
        report["runner_self_test"] = self_test
        report["failed"] = len(pages)
        return report

    with tempfile.TemporaryDirectory(prefix="lvgl-native-regression-") as temp_dir:
        work_root = Path(temp_dir)
        for page_dir in pages:
            expected = page_dir / "expected"
            result: dict[str, Any] = {"page": page_dir.name, "verdict": "failed", "failed_stages": []}
            spec, baseline_error = _validate_baseline(expected)
            if baseline_error:
                result["failed_stages"].append("baseline")
                result["error"] = baseline_error
                report["pages"].append(result)
                continue
            assert spec is not None
            display = spec["display"]
            scene_path = work_root / page_dir.name / "scene.bin"
            scene_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                scene_path.write_bytes(encode_spec(spec))
            except Exception as exc:
                result["failed_stages"].append("scene_encode")
                result["error"] = str(exc)
                report["pages"].append(result)
                continue
            native = run_simulator(
                runner["path"], str(scene_path), str(scene_path.parent / "render"),
                display["width"], display["height"],
            )
            if not native.get("ok") or not native.get("render_png"):
                result["failed_stages"].append("native_render")
                result["error"] = native.get("error", native.get("stderr", "runner did not render PNG"))
                report["pages"].append(result)
                continue
            pixels_ok, pixels = _compare_pixels(Path(native["render_png"]), expected / "render.png")
            if not pixels_ok:
                result["failed_stages"].append("pixels")
                result["pixel_diff"] = pixels
            actual_tree = Path(native["tree"])
            if _sha256(actual_tree) != _sha256(expected / "object_tree.bin"):
                result["failed_stages"].append("object_tree")
                result["object_tree"] = {"actual_sha256": _sha256(actual_tree), "expected_sha256": _sha256(expected / "object_tree.bin")}
            if not result["failed_stages"]:
                result["verdict"] = "passed"
                result["pixel_diff"] = pixels
                report["passed"] += 1
            report["pages"].append(result)

    report["failed"] = report["total"] - report["passed"]
    report["ok"] = report["failed"] == 0
    return report


def _print_report(report: dict[str, Any]) -> None:
    if report.get("ok"):
        runner = report.get("runner", {})
        print(f"[OK] Native LVGL regression: {report['passed']}/{report['total']} passed ({runner.get('platform')}, {runner.get('sha256', '')[:12]})")
        return
    print(f"[FAIL] Native LVGL regression: {report.get('passed', 0)}/{report.get('total', 0)} passed")
    if report.get("error"):
        print(f"  {report['error']}")
    for page in report.get("pages", []):
        if page.get("verdict") != "passed":
            print(f"  - {page.get('page')}: {page.get('failed_stages', [])} {page.get('error', '')}".rstrip())


def run_self_test() -> int:
    """Exercise the real native regression contract."""
    report = run_regression()
    _print_report(report)
    return 0 if report.get("ok") else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit the full report as JSON")
    parser.add_argument("--self-test", action="store_true", help="run the native golden regression")
    args = parser.parse_args()
    report = run_regression()
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        _print_report(report)
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
