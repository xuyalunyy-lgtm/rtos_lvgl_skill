#!/usr/bin/env python3
"""Generate placeholder expected/ files for golden pages.

Creates minimal valid structure for regression testing.
Run after generate_golden_designs.py.

Usage:
    python scripts/generate_golden_expected.py
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GOLDEN_DIR = ROOT / "golden_pages"

# Pages that already have expected/ files (keep existing)
EXISTING_PAGES = {"loading_page", "home_card_page", "media_page"}

# Minimal analysis report template
ANALYSIS_REPORT_TEMPLATE = {
    "schema_version": "1.0",
    "page_name": "",
    "screen": {"width": 480, "height": 800, "lvgl_version": "v9", "color_depth": 16},
    "detected_regions": [],
    "detected_text": [],
    "color_palette": [],
    "layout_candidates": [],
    "confidence": 0.0,
    "uncertain_regions": [],
    "questions": [],
}

# Minimal object tree template
OBJECT_TREE_TEMPLATE = {
    "schema_version": "1.0",
    "root": {
        "type": "screen",
        "children": [],
    },
}

# Minimal manifest template
MANIFEST_TEMPLATE = {
    "schema_version": "1.0",
    "page_name": "",
    "generated_files": [],
    "assets": [],
    "fonts": [],
    "total_flash_bytes": 0,
    "total_ram_bytes": 0,
}

# Minimal visual diff template
VISUAL_DIFF_TEMPLATE = {
    "schema_version": "1.0",
    "global_ssim": 0.0,
    "changed_pixel_ratio": 0.0,
    "region_diffs": [],
    "text_diffs": [],
    "control_tree_diffs": [],
    "status": "pending",
}


def main():
    count = 0
    for page_dir in sorted(GOLDEN_DIR.iterdir()):
        if not page_dir.is_dir():
            continue
        page_name = page_dir.name
        if page_name in EXISTING_PAGES:
            continue

        expected_dir = page_dir / "expected"
        expected_dir.mkdir(parents=True, exist_ok=True)

        # analysis_report.json
        report = ANALYSIS_REPORT_TEMPLATE.copy()
        report["page_name"] = page_name
        (expected_dir / "analysis_report.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        # object_tree.json
        (expected_dir / "object_tree.json").write_text(
            json.dumps(OBJECT_TREE_TEMPLATE, indent=2), encoding="utf-8"
        )

        # manifest.json
        manifest = MANIFEST_TEMPLATE.copy()
        manifest["page_name"] = page_name
        (expected_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )

        # visual_diff.json
        (expected_dir / "visual_diff.json").write_text(
            json.dumps(VISUAL_DIFF_TEMPLATE, indent=2), encoding="utf-8"
        )

        # cutout_audit.json (empty array)
        (expected_dir / "cutout_audit.json").write_text("[]", encoding="utf-8")

        # diff_overlay.png (empty placeholder - will be replaced by actual render)
        # Don't create binary placeholder - leave for actual generation

        print(f"[OK] {page_name}/expected/ (6 JSON files)")
        count += 1

    print(f"\nGenerated expected/ structure for {count} new golden pages")


if __name__ == "__main__":
    main()
