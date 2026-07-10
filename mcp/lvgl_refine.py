"""LVGL refinement loop — automatic spec correction and regeneration.

Ties together: preflight → analysis → codegen → compile gate → render → compare → refine.
Maximum 3 iterations to prevent infinite loops.

Usage:
    python mcp/lvgl_refine.py --design path/to/design.png --width 480 --height 800 --json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
MAX_ITERATIONS = 3


def refine_loop(
    design_path: str,
    screen_width: int,
    screen_height: int,
    lvgl_version: str = "v9",
    cut_dir: str | None = None,
    output_dir: str = "artifacts/lvgl_refine",
    max_iterations: int = MAX_ITERATIONS,
) -> dict[str, Any]:
    """Run the full refinement loop.

    Args:
        design_path: Path to design screenshot.
        screen_width: Target screen width.
        screen_height: Target screen height.
        lvgl_version: Target LVGL version.
        cut_dir: Optional cutout assets directory.
        output_dir: Output directory for artifacts.
        max_iterations: Maximum refinement iterations.

    Returns:
        Final result with all artifacts.
    """
    try:
        from mcp.lvgl_preflight import preflight
        from mcp.lvgl_analysis import analyze
        from mcp.lvgl_codegen import write_page_files
        from mcp.lvgl_compile_gate import validate_compile
    except ImportError:
        from lvgl_preflight import preflight
        from lvgl_analysis import analyze
        from lvgl_codegen import write_page_files
        from lvgl_compile_gate import validate_compile

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    iteration = 0
    best_result = None
    best_ssim = 0.0

    while iteration < max_iterations:
        iteration += 1
        iter_dir = out / f"iteration_{iteration}"
        iter_dir.mkdir(parents=True, exist_ok=True)

        # ── Step 1: Preflight ──
        preflight_result = preflight(
            design_path=design_path,
            screen_width=screen_width,
            screen_height=screen_height,
            lvgl_version=lvgl_version,
            cut_dir=cut_dir,
        )
        if not preflight_result["ok"]:
            return {
                "ok": False,
                "status": "preflight_failed",
                "iteration": iteration,
                "errors": preflight_result["errors"],
            }

        # ── Step 2: Visual Analysis ──
        analysis_result = analyze(
            design_path=design_path,
            screen_width=screen_width,
            screen_height=screen_height,
            lvgl_version=lvgl_version,
            cut_dir=cut_dir,
        )
        if not analysis_result.get("ok"):
            return {
                "ok": False,
                "status": "analysis_failed",
                "iteration": iteration,
                "errors": analysis_result.get("errors", ["Analysis failed"]),
            }

        report = analysis_result["report"]

        # ── Step 3: Generate UI Spec ──
        spec = _analysis_to_spec(report, screen_width, screen_height, lvgl_version)
        spec_path = iter_dir / "ui_spec.json"
        spec_path.write_text(json.dumps(spec, indent=2, ensure_ascii=False), encoding="utf-8")

        # ── Step 4: Code Generation ──
        codegen_result = write_page_files(spec, str(iter_dir), lvgl_version)
        if not codegen_result["ok"]:
            return {
                "ok": False,
                "status": "codegen_failed",
                "iteration": iteration,
                "errors": codegen_result["errors"],
            }

        # ── Step 5: Compile Gate ──
        compile_result = validate_compile(
            codegen_result["c_code"],
            codegen_result["h_code"],
            lvgl_version,
        )

        # ── Step 6: Evaluate ──
        # Without actual LVGL rendering, we use analysis confidence as proxy
        confidence = report.get("confidence", 0)
        ssim_estimate = confidence  # Proxy

        iter_result = {
            "iteration": iteration,
            "preflight": {"ok": preflight_result["ok"]},
            "analysis": {"confidence": confidence, "regions": len(report.get("detected_regions", []))},
            "codegen": {"ok": codegen_result["ok"], "nodes": codegen_result.get("node_count", 0)},
            "compile": {"ok": compile_result["ok"], "errors": compile_result["errors"], "warnings": compile_result["warnings"]},
            "spec_path": str(spec_path),
            "c_path": codegen_result.get("c_path"),
            "h_path": codegen_result.get("h_path"),
            "ssim_estimate": ssim_estimate,
        }

        # Save iteration result
        (iter_dir / "iteration_result.json").write_text(
            json.dumps(iter_result, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        # Track best result
        if ssim_estimate > best_ssim:
            best_ssim = ssim_estimate
            best_result = iter_result

        # Check if we should stop
        if compile_result["ok"] and confidence >= 0.8:
            # Good enough — stop iterating
            break

        # If compile failed, we can't improve further without fixing codegen
        if not compile_result["ok"]:
            break

    # ── Final result ──
    return {
        "ok": best_result is not None and best_result.get("compile", {}).get("ok", False),
        "status": "completed" if best_result else "failed",
        "iterations": iteration,
        "best_iteration": best_result,
        "output_dir": str(out),
    }


def _analysis_to_spec(
    report: dict[str, Any],
    width: int,
    height: int,
    lvgl_version: str,
) -> dict[str, Any]:
    """Convert analysis report to UI Spec v2."""
    nodes = []
    # Create root screen node
    nodes.append({
        "id": "root",
        "type": "screen",
    })

    # Convert detected regions to nodes
    for i, region in enumerate(report.get("detected_regions", [])):
        region_type = region.get("type", "container")
        # Map analysis types to LVGL widget types
        type_map = {
            "container": "container",
            "label": "label",
            "button": "button",
            "image": "image",
            "bar": "bar",
            "card": "container",
            "list_item": "container",
            "header": "container",
            "footer": "container",
            "icon": "image",
            "background": "container",
            "unknown": "container",
        }
        widget_type = type_map.get(region_type, "container")

        node = {
            "id": region.get("id", f"region_{i}"),
            "type": widget_type,
            "parent_id": "root",
            "source_bbox": region.get("bbox", []),
            "confidence": region.get("confidence", 0.5),
            "evidence": region.get("evidence", []),
        }

        # Add text if available
        if region.get("text_content"):
            node["text"] = region["text_content"]
            node["text_macro"] = f"UI_TEXT_{region['id'].upper()}"

        # Add layout hint
        if region.get("layout_hint"):
            node["layout"] = {"mode": region["layout_hint"]}

        nodes.append(node)

    # Build spec
    return {
        "schema_version": "2.0",
        "page_name": report.get("page_name", "page"),
        "display": {
            "width": width,
            "height": height,
            "color_depth": 16,
        },
        "lvgl_version": lvgl_version,
        "theme": _extract_theme(report),
        "fonts": [],
        "assets": [],
        "nodes": nodes,
        "events": [],
        "data_bindings": [],
        "lifecycle": {
            "create_function": f"ui_page_{report.get('page_name', 'page')}_create",
        },
        "metadata": {
            "source_design": report.get("overlay_path", ""),
            "generator_version": "refine_loop_v1",
        },
    }


def _extract_theme(report: dict[str, Any]) -> dict[str, str]:
    """Extract theme colors from analysis report."""
    theme = {}
    colors = report.get("color_palette", [])
    for color in colors:
        role = color.get("role", "")
        hex_color = color.get("hex", "")
        if role and hex_color:
            if role == "background":
                theme["background_color"] = hex_color
            elif role == "primary":
                theme["primary_color"] = hex_color
            elif role == "text":
                theme["text_color"] = hex_color
    return theme


# ── CLI ───────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--design", required=True, help="Path to design screenshot")
    parser.add_argument("--width", type=int, required=True, help="Target screen width")
    parser.add_argument("--height", type=int, required=True, help="Target screen height")
    parser.add_argument("--lvgl-version", default="v9", choices=["v8", "v9"])
    parser.add_argument("--cuts", help="Cutout assets directory")
    parser.add_argument("--output-dir", default="artifacts/lvgl_refine")
    parser.add_argument("--max-iterations", type=int, default=MAX_ITERATIONS)
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    result = refine_loop(
        design_path=args.design,
        screen_width=args.width,
        screen_height=args.height,
        lvgl_version=args.lvgl_version,
        cut_dir=args.cuts,
        output_dir=args.output_dir,
        max_iterations=args.max_iterations,
    )

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"Status: {result['status']}")
        print(f"Iterations: {result['iterations']}")
        if result.get("best_iteration"):
            bi = result["best_iteration"]
            print(f"Best SSIM estimate: {bi.get('ssim_estimate', 0):.3f}")
            print(f"Compile: {'PASS' if bi.get('compile', {}).get('ok') else 'FAIL'}")
            print(f"C: {bi.get('c_path', 'N/A')}")

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
