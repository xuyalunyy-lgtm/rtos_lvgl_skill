#!/usr/bin/env python3
"""Validate cutout_audit.json completeness and analysis_report.json IR fields.

Usage:
    python tools/validate_cutout_audit.py golden_pages/loading_page
    python tools/validate_cutout_audit.py golden_pages/loading_page --strict
    python tools/validate_cutout_audit.py --all           # validate all golden pages
    python tools/validate_cutout_audit.py --all --json    # JSON output

Rules (cutout_audit):
  - Every input cutout image must have an entry in cutout_audit.json
  - Every entry must have: status, bbox, confidence, source
  - Status must be one of: used_cutout, used_component_calibration,
    duplicate_or_low_confidence, unmatched_or_state_variant
  - High-confidence cutout (>= 0.8) dropped to unmatched → warning (strict: fail)

Rules (analysis_report IR):
  - Must have top-level keys: screen, assets, components, layout_policy, warnings
  - screen must have: width, height
  - Every component must have: id, type, bbox, source, confidence
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

VALID_STATUSES = {
    "used_cutout",
    "used_component_calibration",
    "duplicate_or_low_confidence",
    "unmatched_or_state_variant",
}

IR_REQUIRED_KEYS = {"screen", "assets", "components", "layout_policy", "warnings"}
SCREEN_REQUIRED_KEYS = {"width", "height"}
COMPONENT_REQUIRED_KEYS = {"id", "type", "bbox", "source", "confidence"}
HIGH_CONFIDENCE_THRESHOLD = 0.8


def validate_cutout_audit(audit_path: Path, cutouts_dir: Path, *, strict: bool) -> list[dict]:
    """Validate cutout_audit.json against actual cutout files."""
    issues = []

    if not audit_path.is_file():
        if cutouts_dir.is_dir() and any(cutouts_dir.iterdir()):
            issues.append({
                "level": "error",
                "rule": "audit_missing",
                "message": f"cutout_audit.json missing but cutouts/ has files",
            })
        return issues

    try:
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        issues.append({"level": "error", "rule": "audit_parse_error", "message": str(e)})
        return issues

    entries = audit.get("cutouts", [])
    entry_map = {e.get("filename", ""): e for e in entries}

    # Check: every cutout file must have an audit entry
    if cutouts_dir.is_dir():
        for f in sorted(cutouts_dir.iterdir()):
            if f.is_file() and f.suffix.lower() in (".png", ".jpg", ".jpeg", ".bmp"):
                if f.name not in entry_map:
                    issues.append({
                        "level": "error",
                        "rule": "cutout_not_in_audit",
                        "message": f"cutout file '{f.name}' has no entry in cutout_audit.json",
                        "file": f.name,
                    })

    # Check: every audit entry must have required fields
    for entry in entries:
        filename = entry.get("filename", "<unknown>")
        status = entry.get("status", "")

        if not status:
            issues.append({
                "level": "error",
                "rule": "missing_status",
                "message": f"'{filename}': missing 'status' field",
                "file": filename,
            })
        elif status not in VALID_STATUSES:
            issues.append({
                "level": "error",
                "rule": "invalid_status",
                "message": f"'{filename}': invalid status '{status}', must be one of {sorted(VALID_STATUSES)}",
                "file": filename,
            })

        for field in ("bbox", "confidence", "source"):
            if field not in entry:
                issues.append({
                    "level": "error",
                    "rule": f"missing_{field}",
                    "message": f"'{filename}': missing required field '{field}'",
                    "file": filename,
                })

        # Check: high-confidence cutout dropped
        conf = entry.get("confidence", 0)
        if isinstance(conf, (int, float)) and conf >= HIGH_CONFIDENCE_THRESHOLD:
            if status in ("unmatched_or_state_variant", "duplicate_or_low_confidence"):
                level = "error" if strict else "warning"
                issues.append({
                    "level": level,
                    "rule": "high_confidence_dropped",
                    "message": f"'{filename}': confidence={conf} but status='{status}'",
                    "file": filename,
                })

    return issues


def validate_analysis_report(report_path: Path) -> list[dict]:
    """Validate analysis_report.json IR fields."""
    issues = []

    if not report_path.is_file():
        issues.append({"level": "error", "rule": "report_missing", "message": "analysis_report.json missing"})
        return issues

    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        issues.append({"level": "error", "rule": "report_parse_error", "message": str(e)})
        return issues

    # Top-level keys
    for key in IR_REQUIRED_KEYS:
        if key not in report:
            issues.append({"level": "error", "rule": "missing_ir_key", "message": f"missing top-level key: '{key}'"})

    # Screen
    screen = report.get("screen", {})
    for key in SCREEN_REQUIRED_KEYS:
        if key not in screen:
            issues.append({"level": "error", "rule": "missing_screen_key", "message": f"screen missing '{key}'"})
        elif not isinstance(screen[key], (int, float)):
            issues.append({"level": "error", "rule": "invalid_screen_value", "message": f"screen.{key} must be numeric"})

    # Components
    components = report.get("components", [])
    if not isinstance(components, list):
        issues.append({"level": "error", "rule": "invalid_components", "message": "components must be a list"})
    else:
        for i, comp in enumerate(components):
            for key in COMPONENT_REQUIRED_KEYS:
                if key not in comp:
                    comp_id = comp.get("id", f"[{i}]")
                    issues.append({
                        "level": "error",
                        "rule": f"missing_component_{key}",
                        "message": f"component '{comp_id}': missing '{key}'",
                    })
            # bbox must be list of 4 numbers
            bbox = comp.get("bbox")
            if bbox is not None:
                if not isinstance(bbox, list) or len(bbox) != 4:
                    comp_id = comp.get("id", f"[{i}]")
                    issues.append({
                        "level": "error",
                        "rule": "invalid_bbox",
                        "message": f"component '{comp_id}': bbox must be [x, y, w, h]",
                    })
            # confidence must be 0-1
            conf = comp.get("confidence")
            if conf is not None and isinstance(conf, (int, float)):
                if not (0 <= conf <= 1):
                    comp_id = comp.get("id", f"[{i}]")
                    issues.append({
                        "level": "warning",
                        "rule": "confidence_out_of_range",
                        "message": f"component '{comp_id}': confidence={conf} not in [0, 1]",
                    })

    return issues


def validate_page(page_dir: Path, *, strict: bool) -> tuple[list[dict], list[dict]]:
    """Validate a single golden page."""
    audit_path = page_dir / "expected" / "cutout_audit.json"
    report_path = page_dir / "expected" / "analysis_report.json"
    cutouts_dir = page_dir / "cutouts"

    audit_issues = validate_cutout_audit(audit_path, cutouts_dir, strict=strict)
    report_issues = validate_analysis_report(report_path)

    return audit_issues, report_issues


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate cutout audit and analysis report")
    parser.add_argument("page", nargs="?", help="Page directory to validate")
    parser.add_argument("--all", action="store_true", help="Validate all golden pages")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as errors")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    if not args.page and not args.all:
        parser.error("specify a page directory or --all")

    golden_dir = ROOT / "golden_pages"
    pages = []
    if args.all:
        pages = sorted(p for p in golden_dir.iterdir() if p.is_dir())
    else:
        p = Path(args.page)
        if not p.is_absolute():
            p = ROOT / p
        pages = [p]

    all_results = {}
    total_errors = 0
    total_warnings = 0

    for page_dir in pages:
        page_name = page_dir.name
        audit_issues, report_issues = validate_page(page_dir, strict=args.strict)
        all_issues = audit_issues + report_issues

        errors = [i for i in all_issues if i["level"] == "error"]
        warnings = [i for i in all_issues if i["level"] == "warning"]
        total_errors += len(errors)
        total_warnings += len(warnings)

        all_results[page_name] = {
            "audit_issues": audit_issues,
            "report_issues": report_issues,
            "errors": len(errors),
            "warnings": len(warnings),
            "pass": len(errors) == 0,
        }

        if not args.json:
            status = "PASS" if not errors else "FAIL"
            print(f"[{status}] {page_name}: {len(errors)} errors, {len(warnings)} warnings")
            for issue in all_issues:
                marker = "ERR" if issue["level"] == "error" else "WRN"
                print(f"  [{marker}] {issue['rule']}: {issue['message']}")

    if args.json:
        output = {
            "total_pages": len(pages),
            "total_errors": total_errors,
            "total_warnings": total_warnings,
            "all_pass": total_errors == 0,
            "pages": all_results,
        }
        json.dump(output, sys.stdout, ensure_ascii=False, indent=2)
        print()
    else:
        print(f"\nSummary: {len(pages)} pages, {total_errors} errors, {total_warnings} warnings")

    return 0 if total_errors == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
