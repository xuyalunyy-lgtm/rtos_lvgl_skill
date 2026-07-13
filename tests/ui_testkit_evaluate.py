"""Post-process native TestKit output and enforce the deterministic 90% gate."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mcp.lvgl_compare import compare, score_evidence  # noqa: E402
from mcp.lvgl_ir.object_tree_reader import read_object_tree  # noqa: E402


def passes_quality_gate(scored: dict) -> bool:
    metrics = scored.get("metrics", {})
    return bool(
        scored.get("hard_gates_pass")
        and int(scored.get("total_score", 0)) >= 9000
        and float(metrics.get("global_ssim", 0.0)) >= 0.90
        and float(metrics.get("critical_region_ssim", 0.0)) >= 0.90
        and float(metrics.get("pixel_similarity", 0.0)) >= 0.90
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True, type=Path)
    parser.add_argument("--native-dir", required=True, type=Path)
    parser.add_argument("--generated-dir", required=True, type=Path)
    args = parser.parse_args()
    case = json.loads(args.case.read_text(encoding="utf-8"))
    native = args.native_dir.resolve()
    generated = args.generated_dir.resolve()
    native_report = json.loads((native / "native_execution_report.json").read_text(encoding="utf-8"))
    build_report = json.loads((generated.parent / "build_input_report.json").read_text(encoding="utf-8"))
    tree = read_object_tree(native / "object_tree.bin")
    (native / "object_tree.json").write_text(json.dumps(tree, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    render_png = native / "render.png"
    Image.open(native / "render.ppm").save(render_png)

    spec = {
        "nodes": [
            {"id": item["id"], "type": "region", "source_bbox": item["bbox"]}
            for item in case.get("quality_regions", [])
        ]
    }
    comparison = compare(str(render_png), str((ROOT / case["design"]).resolve()), spec, None, profile="golden_strict")
    hard_gates = {
        "native_render": bool(native_report.get("screenshot_written")),
        "compile": True,
        "nodes_nonempty": int(tree.get("node_count", 0)) > 1,
        "not_blank": bool(native_report.get("not_blank")),
        "assets": bool(build_report.get("resource_closure", {}).get("ok")),
        "fonts": all((generated / name).is_file() for name in build_report.get("fonts", [])),
        "memory": int(native_report.get("framebuffer_bytes", 0)) <= int(case["memory"]["max_framebuffer_bytes"]),
        "flows": not bool(case.get("flows_required", False)),
        "no_capability_gap": True,
        "no_design_cheat": not bool(build_report.get("asset_resolution_errors")),
    }
    critical_ids = {item["id"] for item in case.get("quality_regions", []) if item.get("critical", False)}
    scored = score_evidence(comparison, critical_region_ids=critical_ids, hard_gates=hard_gates)
    metrics = scored["metrics"]
    passed_90 = passes_quality_gate(scored)
    evidence = {
        "schema_version": "1.0",
        "case": case["id"],
        "status": "verified" if passed_90 else "manual_required",
        "passed_90": passed_90,
        "score": scored,
        "comparison": comparison,
        "native_execution": native_report,
        "object_tree_path": str(native / "object_tree.json"),
        "render_path": str(render_png),
    }
    (native / "visual_evidence.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": evidence["status"], "total_score": scored["total_score"], "metrics": metrics}, indent=2))
    return 0 if passed_90 else 2


if __name__ == "__main__":
    raise SystemExit(main())
