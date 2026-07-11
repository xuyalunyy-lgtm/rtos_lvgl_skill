#!/usr/bin/env python3
"""Generate real golden expected files using preview renderer.

Runs the full pipeline for each golden page:
  design.png → preflight → analysis → UI Spec → codegen → preview render → compare

Usage:
    python scripts/generate_golden_expected_real.py
    python scripts/generate_golden_expected_real.py --page loading_page
    python scripts/generate_golden_expected_real.py --accept
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "mcp"))


def generate_page_expected(page_name: str, accept: bool = False) -> dict:
    """Generate expected files for a single golden page."""
    from lvgl_preflight import preflight
    from lvgl_analysis import analyze
    from lvgl_codegen import write_page_files
    from lvgl_compile_gate import validate_compile
    from lvgl_compare import compare
    from lvgl_preview import render_tree_to_png, spec_to_tree, write_object_tree

    page_dir = ROOT / "golden_pages" / page_name
    design_path = page_dir / "design.png"
    meta_path = page_dir / "design_meta.json"

    if not design_path.is_file():
        return {"ok": False, "error": f"Design not found: {design_path}"}
    if not meta_path.is_file():
        return {"ok": False, "error": f"Meta not found: {meta_path}"}

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    width = meta.get("screen", {}).get("width", 480)
    height = meta.get("screen", {}).get("height", 800)
    lvgl_version = meta.get("screen", {}).get("lvgl_version", "v9")

    # Working directory
    work_dir = ROOT / "artifacts" / "golden_candidates" / page_name
    work_dir.mkdir(parents=True, exist_ok=True)

    result = {
        "page": page_name,
        "ok": False,
        "stages": {},
    }

    # ── Step 1: Preflight ──
    pf = preflight(str(design_path), width, height, lvgl_version)
    result["stages"]["preflight"] = {"ok": pf["ok"], "errors": pf["errors"]}
    if not pf["ok"]:
        return result

    # ── Step 2: Analysis ──
    analysis = analyze(str(design_path), width, height, lvgl_version)
    if not analysis.get("ok"):
        result["stages"]["analysis"] = {"ok": False, "errors": analysis.get("errors", [])}
        return result
    result["stages"]["analysis"] = {
        "ok": True,
        "confidence": analysis["report"].get("confidence", 0),
        "regions": len(analysis["report"].get("detected_regions", [])),
    }

    # ── Step 3: Generate UI Spec ──
    spec = _analysis_to_spec(analysis["report"], width, height, lvgl_version, page_name)
    spec_path = work_dir / "ui_spec.json"
    spec_path.write_text(json.dumps(spec, indent=2, ensure_ascii=False), encoding="utf-8")
    result["stages"]["spec"] = {"ok": True, "path": str(spec_path)}

    # ── Step 4: Code Generation ──
    codegen = write_page_files(spec, str(work_dir), lvgl_version)
    if not codegen["ok"]:
        result["stages"]["codegen"] = {"ok": False, "errors": codegen["errors"]}
        return result
    result["stages"]["codegen"] = {
        "ok": True,
        "c_path": codegen.get("c_path"),
        "h_path": codegen.get("h_path"),
    }

    # ── Step 5: Compile Gate ──
    compile_result = validate_compile(codegen["c_code"], codegen["h_code"], lvgl_version)
    result["stages"]["compile"] = {
        "ok": compile_result["ok"],
        "errors": compile_result["errors"],
        "warnings": compile_result["warnings"],
    }

    # ── Step 6: Preview Render ──
    tree = spec_to_tree(spec, display_width=width, display_height=height)
    png_path = render_tree_to_png(tree, work_dir, "render.png", display_width=width, display_height=height)
    tree_path = write_object_tree(tree, work_dir, "object_tree.json")
    result["stages"]["render"] = {
        "ok": True,
        "render_path": str(png_path),
        "tree_path": str(tree_path),
    }

    # ── Step 7: Visual Compare (informational only) ──
    if png_path.is_file():
        compare_result = compare(str(png_path), str(design_path), spec)
        result["stages"]["compare"] = {
            "ok": True,  # Compare is informational, not blocking
            "ssim": float(compare_result.get("global_ssim", 0)),
            "changed_ratio": float(compare_result.get("changed_pixel_ratio", 1)),
            "note": "Preview render vs design - low SSIM expected for synthetic designs",
        }
        # Save visual diff
        diff_path = work_dir / "visual_diff.json"
        diff_path.write_text(json.dumps(compare_result, indent=2, default=str), encoding="utf-8")
    else:
        result["stages"]["compare"] = {"ok": False, "error": "No render.png"}

    # ── Step 8: Manifest ──
    manifest = {
        "schema_version": "1.0",
        "page_name": page_name,
        "generated_files": [
            codegen.get("c_path", ""),
            codegen.get("h_path", ""),
        ],
        "assets": [],
        "fonts": [],
        "total_flash_bytes": 0,
        "total_ram_bytes": 0,
    }
    manifest_path = work_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # ── Determine success ──
    all_ok = all(s.get("ok", False) for s in result["stages"].values())
    result["ok"] = all_ok
    result["work_dir"] = str(work_dir)

    # ── Accept: copy to golden_pages ──
    if accept and all_ok:
        expected_dir = page_dir / "expected"
        expected_dir.mkdir(parents=True, exist_ok=True)

        # Copy files
        for src_name, dst_name in [
            ("ui_spec.json", "ui_spec.json"),
            ("render.png", "render.png"),
            ("object_tree.json", "object_tree.json"),
            ("manifest.json", "manifest.json"),
        ]:
            src = work_dir / src_name
            if src.is_file():
                shutil.copy2(src, expected_dir / dst_name)

        # Copy generated C/H
        for suffix in [".c", ".h"]:
            for f in work_dir.glob(f"*{suffix}"):
                shutil.copy2(f, expected_dir / f.name)

        # Copy analysis report
        analysis_report = analysis["report"]
        (expected_dir / "analysis_report.json").write_text(
            json.dumps(analysis_report, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        result["accepted"] = True
        result["expected_dir"] = str(expected_dir)

    return result


def _analysis_to_spec(report: dict, width: int, height: int, lvgl_version: str, page_name: str) -> dict:
    """Convert analysis report to UI Spec v2."""
    nodes = [{"id": "root", "type": "screen"}]

    for i, region in enumerate(report.get("detected_regions", [])):
        region_type = region.get("type", "container")
        type_map = {
            "container": "container", "label": "label", "button": "button",
            "image": "image", "bar": "bar", "card": "container",
            "list_item": "container", "header": "container", "footer": "container",
            "icon": "image", "background": "container", "unknown": "container",
        }
        widget_type = type_map.get(region_type, "container")

        node = {
            "id": region.get("id", f"region_{i}"),
            "type": widget_type,
            "parent_id": "root",
            "source_bbox": region.get("bbox", []),
            "confidence": region.get("confidence", 0.5),
        }
        if region.get("text_content"):
            node["text"] = region["text_content"]
        nodes.append(node)

    theme = {}
    for color in report.get("color_palette", []):
        role = color.get("role", "")
        hex_color = color.get("hex", "")
        if role and hex_color:
            if role == "background":
                theme["background_color"] = hex_color
            elif role == "primary":
                theme["primary_color"] = hex_color
            elif role == "text":
                theme["text_color"] = hex_color

    return {
        "schema_version": "2.0",
        "page_name": page_name,
        "display": {"width": width, "height": height, "color_depth": 16},
        "lvgl_version": lvgl_version,
        "theme": theme,
        "fonts": [],
        "assets": [],
        "nodes": nodes,
        "events": [],
        "data_bindings": [],
        "lifecycle": {"create_function": f"ui_page_{page_name}_create"},
        "metadata": {"generator_version": "golden_generator_v1"},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--page", help="Generate for specific page only")
    parser.add_argument("--accept", action="store_true", help="Accept candidates and copy to golden_pages")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    golden_dir = ROOT / "golden_pages"
    pages = sorted([d.name for d in golden_dir.iterdir() if d.is_dir()])
    if args.page:
        pages = [args.page]

    results = []
    for page_name in pages:
        print(f"\n{'='*60}")
        print(f"Page: {page_name}")
        print(f"{'='*60}")

        result = generate_page_expected(page_name, accept=args.accept)
        results.append(result)

        if result["ok"]:
            stages = result["stages"]
            print(f"  Preflight: PASS")
            print(f"  Analysis:  PASS (confidence={stages['analysis'].get('confidence', 0):.2f}, regions={stages['analysis'].get('regions', 0)})")
            print(f"  Codegen:   PASS")
            print(f"  Compile:   {'PASS' if stages['compile']['ok'] else 'FAIL'}")
            print(f"  Render:    PASS")
            print(f"  Compare:   SSIM={stages['compare'].get('ssim', 0):.3f}, changed={stages['compare'].get('changed_ratio', 1):.1%}")
            if result.get("accepted"):
                print(f"  Accepted:  {result.get('expected_dir', 'N/A')}")
        else:
            for stage, info in result.get("stages", {}).items():
                if not info.get("ok"):
                    print(f"  FAIL at {stage}: {info.get('errors', info.get('error', 'unknown'))}")

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))

    passed = sum(1 for r in results if r["ok"])
    print(f"\n{'='*60}")
    print(f"Summary: {passed}/{len(results)} pages passed")
    if args.accept:
        print(f"Accepted: {passed} pages written to golden_pages/*/expected/")
    else:
        print(f"Candidates in artifacts/golden_candidates/. Use --accept to copy to golden_pages.")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
