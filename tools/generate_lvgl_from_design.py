#!/usr/bin/env python3
"""Generate LVGL page from predefined scene assets with gated pipeline."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = ROOT / "tools"
MCP_DIR = ROOT / "mcp"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))
if str(MCP_DIR) not in sys.path:
    sys.path.insert(0, str(MCP_DIR))

from mcp.interactive_scene_auto import (
    _mood_order_from_args,
    _preflight_interactive_scene,
    generate_interactive_scene_page,
)
from mcp.regression import run_lvgl_ui_regression

DESIGN_REFERENCE_PREVIEW = "design_reference_preview.html"
DESIGN_REFERENCE_PREVIEW_ALIAS = "preview.html"
LAYERED_PREVIEW = "layered_preview.png"
LAYERED_PREVIEW_COMPAT = "preview_composited.png"
LVGL_RENDER_PNG = "lvgl_render.png"
OBJECT_TREE_JSON = "object_tree.json"
QUALITY_GATES_JSON = "quality_gates.json"
VISUAL_DIFF_REPORT_JSON = "visual_diff_report.json"
VISUAL_DIFF_OVERLAY_PNG = "visual_diff_overlay.png"
BLOCKED_REPORT_JSON = "blocked_report.json"
GENERATION_REPORT_JSON = "generation_report.json"
RUN_REPORT_JSON = "run_lvgl_ui_regression.json"
SHELL_SCRIPT = "run_lvgl_render.sh"
BATCH_SCRIPT = "run_lvgl_render.bat"
RENDER_DIR = "lvgl_render"
RENDER_CACHE_DIR = "lvgl_render_cache"

SCENE_PRESETS = {
    "interactive_favorite": {
        "page_name": "interactive_scene_favorite",
        "design": "ui/\u4e92\u52a8\u573a\u666f\uff08\u6709\u6536\u85cf\uff09.png",
        "background": "ui/home_bg.jpg",
        "pet": "ui/initial_page_pet.png",
        "mood_paths": {
            "calmness": "ui/mood_calmness.png",
            "good": "ui/mood_good.png",
            "down": "ui/mood_down.png",
            "stressed": "ui/mood_stressed.png",
        },
        "default_mood_order": ("calmness", "good", "down", "stressed"),
        "top_text": "I am completely\nforgiven-past,\npresent, and",
        "title_text": "How's your mood",
        "hint_text": "today?",
    }
}


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def _image_size(path: Path) -> tuple[int, int]:
    from PIL import Image
    with Image.open(path) as image:
        return image.size


def _ensure_design_reference_preview(output_dir: Path) -> str | None:
    target = output_dir / DESIGN_REFERENCE_PREVIEW
    source = output_dir / DESIGN_REFERENCE_PREVIEW_ALIAS
    if target.exists():
        return str(target)
    if source.exists():
        shutil.copy2(source, target)
        return str(target)
    return None


def _ensure_layered_preview(output_dir: Path) -> str | None:
    target = output_dir / LAYERED_PREVIEW
    source = output_dir / LAYERED_PREVIEW_COMPAT
    if target.exists():
        return str(target)
    if source.exists():
        shutil.copy2(source, target)
        return str(target)
    return None


def _remove_if_exists(paths: list[Path]) -> None:
    for path in paths:
        if path.is_file():
            path.unlink()


def _copy_render_outputs(output_dir: Path, render_result: dict[str, Any]) -> tuple[Path | None, Path | None]:
    rendered = render_result.get("render", {}) if isinstance(render_result, dict) else {}
    png_path = rendered.get("png_path")
    tree_path = rendered.get("object_tree_path")
    copied_png = None
    copied_tree = None

    if isinstance(png_path, str):
        src = Path(png_path)
        if src.is_file():
            copied_png = output_dir / LVGL_RENDER_PNG
            shutil.copy2(src, copied_png)
    if isinstance(tree_path, str):
        src = Path(tree_path)
        if src.is_file():
            copied_tree = output_dir / OBJECT_TREE_JSON
            shutil.copy2(src, copied_tree)
    return copied_png, copied_tree


def _run_visual_diff(design_path: Path, render_png: Path, out_dir: Path, threshold: int = 8) -> dict[str, Any]:
    try:
        from PIL import Image
        import numpy as np
        from visual_diff import compute_diff, generate_overlay
    except Exception as exc:
        return {
            "status": "unavailable",
            "error": f"visual diff dependencies missing: {exc}",
        }

    with Image.open(design_path) as design_img, Image.open(render_png) as render_img:
        design = design_img.convert("RGB")
        rendered = render_img.convert("RGB")
        design_arr = np.array(design)
        rendered_arr = np.array(rendered)
        report = compute_diff(design_arr, rendered_arr, threshold)

    report["status"] = report.get("verdict", "fail")
    report["channel_threshold"] = threshold
    report["design_path"] = str(design_path)
    report["render_path"] = str(render_png)

    if "error" not in report:
        changed = np.any(np.abs(design_arr.astype(int) - rendered_arr.astype(int)) > threshold, axis=2)
        overlay = generate_overlay(design_arr, changed)
        overlay_path = out_dir / VISUAL_DIFF_OVERLAY_PNG
        overlay_path.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(overlay).save(overlay_path)
        report["overlay_path"] = str(overlay_path)

    out_json = out_dir / VISUAL_DIFF_REPORT_JSON
    _write_json(out_json, report)
    report["visual_diff_report_path"] = str(out_json)
    return report


def _write_blocked_report(output_dir: Path, preflight: dict[str, Any], spec: dict[str, Any], scene: str) -> str | None:
    if str(preflight.get("quality", {}).get("background_consistency", "pass")).lower() != "blocked":
        return None
    report = {
        "scene": scene,
        "page_name": spec["page_name"],
        "decision": "background_gate_blocked_layered_reconstruction",
        "actions": [
            f"generated {DESIGN_REFERENCE_PREVIEW}",
            "kept hotspot zones only (not full pixel layer reconstruction)",
            "generated LVGL scaffolding assets",
        ],
        "preflight": preflight,
    }
    out = output_dir / BLOCKED_REPORT_JSON
    _write_json(out, report)
    return str(out)


def _coerce_render_status(status: Any) -> str:
    status_text = str(status or "").strip().lower()
    if not status_text or status_text in {"none", "unknown"}:
        return "warn"
    if status_text in {"passed", "pass"}:
        return "pass"
    if status_text in {"failed", "failed_to_render", "build_failed", "configure_failed", "screenshot_missing", "setup_failed"}:
        return "failed"
    return status_text


def _build_quality_gates(
    preflight: dict[str, Any],
    generation: dict[str, Any],
    render_report: dict[str, Any] | None,
    diff_report: dict[str, Any] | None,
    render_requested: bool,
    render_attempted: bool,
) -> dict[str, str]:
    preflight_quality = preflight.get("quality", {})

    background = str(preflight_quality.get("background_consistency", "warn")).lower()
    if background not in {"pass", "warn", "blocked", "fail"}:
        background = "warn"

    cutout = str(preflight_quality.get("cutout_completeness", "warn")).lower()
    if cutout not in {"pass", "warn", "fail"}:
        cutout = "warn"

    bbox_confidence = "pass"
    if preflight.get("warnings") or not generation.get("summary", {}).get("analysis_method"):
        bbox_confidence = "warn"

    lvgl_validation = "pass" if bool(generation.get("validation", {}).get("ok", True)) else "fail"
    if not render_requested:
        render_state = "missing"
    elif not render_attempted:
        render_state = "missing"
    else:
        if not isinstance(render_report, dict):
            render_state = "missing"
            lvgl_validation = "warn"
        elif not render_report.get("available", False):
            render_state = "missing"
            lvgl_validation = "warn"
        else:
            render_state = _coerce_render_status(render_report.get("status"))
            if render_state == "pass":
                lvgl_validation = "pass"
            elif render_state == "failed":
                lvgl_validation = "fail"
            else:
                render_state = "warn"
                lvgl_validation = "warn"

    if diff_report:
        diff_status = str(diff_report.get("status", "")).lower()
        if diff_status == "fail":
            lvgl_validation = "fail"
            if render_state != "missing":
                render_state = "warn" if render_state == "warn" else render_state
        elif diff_status == "warn" and lvgl_validation == "pass":
            lvgl_validation = "warn"

    if render_state == "unknown":
        render_state = "warn"

    return {
        "background_consistency": background,
        "cutout_completeness": cutout,
        "bbox_confidence": bbox_confidence,
        "lvgl_validation": lvgl_validation,
        "render_available": render_state,
    }


def _run_render(scene_dir: Path, page_name: str, width: int, height: int, mode: str) -> dict[str, Any]:
    render_out = scene_dir / RENDER_DIR
    render_cache = scene_dir / RENDER_CACHE_DIR

    result = run_lvgl_ui_regression({
        "render_mode": mode,
        "output_dir": str(render_out),
        "cache_dir": str(render_cache),
        "width": width,
        "height": height,
        "ui_under_test_dir": str(scene_dir),
        "ui_entry_function": f"ui_{page_name}_create",
        "ui_header": f"ui_{page_name}.h",
    })

    render = result.get("render", {}) if isinstance(result, dict) else {}
    return {
        "available": bool(result.get("available", False)),
        "ok": bool(result.get("ok", False)),
        "stage": result.get("stage"),
        "status": result.get("status", result.get("render", {}).get("status")),
        "artifacts": result.get("artifacts", []),
        "result": result,
        "render": render,
        "run_report_path": str(render_out / RUN_REPORT_JSON),
        "sandbox_project_dir": str(result.get("sandbox_dir", render_out)),
        "build_dir": str(result.get("build_dir", render_out / "build")),
        "render_out": str(render_out),
    }


def _write_render_scripts(sandbox_dir: Path, width: int, height: int) -> tuple[str, str]:
    shell = sandbox_dir / SHELL_SCRIPT
    batch = sandbox_dir / BATCH_SCRIPT
    sandbox_dir.mkdir(parents=True, exist_ok=True)
    shell_content = (
        "#!/usr/bin/env sh\n"
        "set -eu\n"
        "cd \"$(dirname \"$0\")\"\n"
        f"cmake -S . -B build -DREGRESSION_WIDTH={width} -DREGRESSION_HEIGHT={height}\n"
        "cmake --build build --config Debug\n"
        "exe=$(find build -type f \\( -name 'lvgl_regression_sandbox' -o -name 'lvgl_regression_sandbox.exe' -o -name 'lvgl_regression_sandbox.*' \\) | head -n 1)\n"
        "if [ -n \"$exe\" ]; then\n"
        "  \"$exe\"\n"
        "else\n"
        "  echo \"executable not found, ensure cmake configure/build succeeded\"\n"
        "  exit 1\n"
        "fi\n"
    )
    shell.write_text(shell_content, encoding="utf-8", newline="\n")

    batch_content = (
        "@echo off\r\n"
        "setlocal\r\n"
        "cd /d \"%~dp0\"\r\n"
        f"cmake -S . -B build -DREGRESSION_WIDTH={width} -DREGRESSION_HEIGHT={height}\r\n"
        "cmake --build build --config Debug\r\n"
        "for /R build %%F in (lvgl_regression_sandbox*.exe) do (\r\n"
        "  \"%%F\"\r\n"
        "  goto :run_ok\r\n"
        ")\r\n"
        "echo executable not found, ensure cmake configure/build succeeded\r\n"
        "exit /b 1\r\n"
        ":run_ok\r\n"
        "endlocal\r\n"
    )
    batch.write_text(batch_content, encoding="utf-8", newline="\r\n")

    return str(shell), str(batch)


def _update_manifest(
    scene_dir: Path,
    manifest_path: Path,
    *,
    design_reference: str | None,
    layered_preview: str | None,
    render_png: Path | None,
    object_tree: Path | None,
    diff_report: dict[str, Any] | None,
    quality_gates: dict[str, str],
    blocked_report: str | None,
    render_scripts: tuple[str, str],
) -> None:
    manifest = _load_json(manifest_path)
    if not isinstance(manifest, dict):
        return

    manifest["quality_gates"] = quality_gates
    manifest.setdefault("artifacts", [])
    manifest["summary"] = manifest.get("summary", {})
    if isinstance(manifest["summary"], dict):
        manifest["summary"]["quality_gates"] = quality_gates

    artifact_refs = manifest["summary"].setdefault("artifact_refs", {})
    artifact_refs["design_reference_preview"] = str(design_reference or "")
    artifact_refs["layered_preview"] = str(layered_preview or "")
    artifact_refs["lvgl_render_png"] = str(render_png or "")
    artifact_refs["object_tree_json"] = str(object_tree or "")
    artifact_refs["visual_diff_report_json"] = str((diff_report or {}).get("visual_diff_report_path", ""))
    artifact_refs["visual_diff_overlay_png"] = str((diff_report or {}).get("overlay_path", ""))
    artifact_refs["run_report_json"] = str(scene_dir / RENDER_DIR / RUN_REPORT_JSON)
    artifact_refs["blocked_report_json"] = str(blocked_report or "")

    manifest["summary"]["build_scripts"] = {
        "shell": str(scene_dir / RENDER_DIR / SHELL_SCRIPT),
        "batch": str(scene_dir / RENDER_DIR / BATCH_SCRIPT),
    }
    manifest["summary"]["sandbox_project"] = str(scene_dir / RENDER_DIR)
    manifest["summary"]["render_available"] = (scene_dir / LVGL_RENDER_PNG).is_file()

    layered_artifact_names = {str(LAYERED_PREVIEW), str(LAYERED_PREVIEW_COMPAT)}
    render_artifact_names = {
        str(LVGL_RENDER_PNG),
        str(OBJECT_TREE_JSON),
        str(VISUAL_DIFF_REPORT_JSON),
        str(VISUAL_DIFF_OVERLAY_PNG),
    }
    if manifest["artifacts"]:
        manifest["artifacts"] = [str(path) for path in manifest["artifacts"] if Path(str(path)).name not in layered_artifact_names | render_artifact_names]

    if design_reference:
        manifest["artifacts"].append(design_reference)
    if layered_preview:
        manifest["artifacts"].append(layered_preview)
    if render_png and render_png.is_file():
        manifest["artifacts"].append(str(render_png))
    if object_tree and object_tree.is_file():
        manifest["artifacts"].append(str(object_tree))

    vis_path = (diff_report or {}).get("visual_diff_report_path")
    if isinstance(vis_path, str) and vis_path:
        manifest["artifacts"].append(vis_path)
    vis_overlay = (diff_report or {}).get("overlay_path")
    if isinstance(vis_overlay, str) and vis_overlay:
        manifest["artifacts"].append(vis_overlay)
    manifest["artifacts"].append(str(scene_dir / QUALITY_GATES_JSON))
    manifest["artifacts"].append(str(scene_dir / RENDER_DIR / SHELL_SCRIPT))
    manifest["artifacts"].append(str(scene_dir / RENDER_DIR / BATCH_SCRIPT))
    manifest["artifacts"].append(str(scene_dir / RENDER_DIR / RUN_REPORT_JSON))
    if blocked_report:
        manifest["artifacts"].append(blocked_report)

    manifest["artifacts"] = sorted(set(str(Path(item)) for item in manifest["artifacts"] if str(item)))
    _write_json(manifest_path, manifest)


def run_scene(args: argparse.Namespace) -> int:
    if args.scene not in SCENE_PRESETS:
        print(f"[ERROR] unknown scene: {args.scene}")
        return 2

    spec = SCENE_PRESETS[args.scene]
    scene_dir = Path(args.output_dir) if args.output_dir else ROOT / "artifacts" / "lvgl_ui" / spec["page_name"]

    design_path = ROOT / spec["design"]
    background_path = ROOT / spec["background"]
    pet_path = ROOT / spec["pet"]
    mood_paths = {key: ROOT / value for key, value in spec["mood_paths"].items()}

    required = [design_path, background_path, pet_path, *mood_paths.values()]
    if not all(path.is_file() for path in required):
        print("[ERROR] required assets missing:")
        for label, path in [("design", design_path), ("background", background_path), ("pet", pet_path)] + [
            (f"mood:{key}", path) for key, path in mood_paths.items()
        ]:
            if not path.is_file():
                print(f"  - missing {label}: {path}")
        return 2

    width, height = _image_size(design_path)
    mood_order = _mood_order_from_args({
        "mood_order": list(spec["default_mood_order"]),
        "mood_paths": {k: str(v) for k, v in mood_paths.items()},
    })

    preflight = _preflight_interactive_scene(
        design_path=design_path,
        background_path=background_path,
        pet_path=pet_path,
        mood_paths=mood_paths,
        mood_order=mood_order,
        design_dir=ROOT / "ui",
        background_gate_threshold=float(args.background_gate_threshold),
    )

    if preflight.get("errors"):
        print("[ERROR] preflight failed:")
        for err in preflight.get("errors", []):
            print(f"  - {err.get('check', 'unknown')}: {err.get('message', 'error')}")
        return 2

    blocked = preflight.get("quality", {}).get("background_consistency", "pass") == "blocked"
    allow_layered_reconstruction = args.force_complete or not blocked
    if blocked and not args.force_complete:
        for legacy in (scene_dir / LAYERED_PREVIEW, scene_dir / LAYERED_PREVIEW_COMPAT):
            if legacy.is_file():
                legacy.unlink()

    if blocked:
        print("[BLOCK] background consistency gate blocked: layered pixel reconstruction skipped")

    generation = generate_interactive_scene_page({
        "design_dir": ROOT / "ui",
        "output_dir": scene_dir,
        "page_name": spec["page_name"],
        "design_path": str(design_path),
        "background_path": str(background_path),
        "pet_path": str(pet_path),
        "mood_order": list(mood_order),
        "mood_paths": {k: str(v) for k, v in mood_paths.items()},
        "background_gate_threshold": float(args.background_gate_threshold),
        "width": width,
        "height": height,
        "top_text": spec["top_text"],
        "title_text": spec["title_text"],
        "hint_text": spec["hint_text"],
        "preview_design_reference": blocked,
        "allow_preflight_warnings": True,
        "allow_layered_reconstruction": allow_layered_reconstruction,
        "return_mode": "full",
    })

    design_reference = _ensure_design_reference_preview(scene_dir)
    layered_preview = _ensure_layered_preview(scene_dir) if allow_layered_reconstruction else None
    render_png = None
    object_tree = None
    diff_report = None
    should_render = (not args.no_render) and allow_layered_reconstruction
    run_report_path = scene_dir / RENDER_DIR / RUN_REPORT_JSON

    render_entry: dict[str, Any] = {"status": "skipped", "available": False, "ok": False, "artifacts": []}
    if should_render:
        render_entry = _run_render(scene_dir, spec["page_name"], width, height, args.render_mode)
        copied_png, copied_tree = _copy_render_outputs(scene_dir, render_entry)
        if copied_png:
            render_png = copied_png
            render_entry["lvgl_render_png"] = str(render_png)
        if copied_tree:
            object_tree = copied_tree
            render_entry["object_tree_json"] = str(object_tree)
        if copied_png and args.run_visual_diff:
            diff_report = _run_visual_diff(design_path, copied_png, scene_dir, threshold=args.diff_threshold)
        _write_json(run_report_path, render_entry.get("result", {}))
    else:
        _remove_if_exists([
            scene_dir / LVGL_RENDER_PNG,
            scene_dir / OBJECT_TREE_JSON,
            scene_dir / VISUAL_DIFF_REPORT_JSON,
            scene_dir / VISUAL_DIFF_OVERLAY_PNG,
        ])
        render_entry["status"] = "skipped"
        render_entry["available"] = False
        render_entry["result"] = {
            "ok": False,
            "available": False,
            "stage": "skipped",
            "status": "blocked",
            "blocked_reason": "background_consistency_gate",
        }
        _write_json(run_report_path, render_entry["result"])

    shell_script, batch_script = _write_render_scripts(scene_dir / RENDER_DIR, width, height)
    quality_gates = _build_quality_gates(
        preflight,
        generation,
        render_entry,
        diff_report,
        render_requested=not args.no_render,
        render_attempted=should_render,
    )
    quality_gates_path = scene_dir / QUALITY_GATES_JSON
    _write_json(quality_gates_path, quality_gates)

    blocked_report_path = _write_blocked_report(scene_dir, preflight, spec, args.scene)
    if (scene_dir / "manifest.json").is_file():
        _update_manifest(
            scene_dir,
            scene_dir / "manifest.json",
            design_reference=design_reference,
            layered_preview=layered_preview,
            render_png=render_png,
            object_tree=object_tree,
            diff_report=diff_report,
            quality_gates=quality_gates,
            blocked_report=blocked_report_path,
            render_scripts=(shell_script, batch_script),
        )

    report = {
        "scene": args.scene,
        "page_name": spec["page_name"],
        "output_dir": str(scene_dir),
        "preflight": preflight,
        "preflight_quality": preflight.get("quality", {}),
        "preflight_warnings": preflight.get("warnings", []),
        "generation": {
            "ok": generation.get("ok"),
            "analysis_ok": generation.get("analysis_ok"),
            "page_name": generation.get("page_name"),
            "artifacts": generation.get("artifacts", []),
            "summary": generation.get("summary", {}),
            "validation": generation.get("validation", {}),
        },
        "render": {
            "requested": not args.no_render,
            "entry": render_entry,
            "sandbox_project": str(scene_dir / RENDER_DIR),
            "build_script": batch_script,
            "build_script_unix": shell_script,
            "lvgl_render_png": str(render_png) if render_png else None,
            "object_tree_json": str(object_tree) if object_tree else None,
            "visual_diff_report": (diff_report or {}).get("visual_diff_report_path"),
        },
        "quality_gates": quality_gates,
        "reports": {
            "manifest": str(scene_dir / "manifest.json"),
            "quality_gates": str(quality_gates_path),
            "design_reference_preview": design_reference,
            "layered_preview": layered_preview,
            "blocked_report": blocked_report_path,
            "lvgl_render_png": str(render_png) if render_png else None,
            "object_tree_json": str(object_tree) if object_tree else None,
            "visual_diff": diff_report,
            "run_report": str(scene_dir / RENDER_DIR / RUN_REPORT_JSON),
        },
        "artifacts": sorted(set(generation.get("artifacts", []))),
    }
    report["artifacts"].extend([
        quality_gates_path,
        scene_dir / DESIGN_REFERENCE_PREVIEW,
        shell_script,
        batch_script,
    ])
    if layered_preview:
        report["artifacts"].append(layered_preview)
    if render_png:
        report["artifacts"].append(render_png)
    if object_tree:
        report["artifacts"].append(object_tree)
    if diff_report and diff_report.get("visual_diff_report_path"):
        report["artifacts"].append(diff_report["visual_diff_report_path"])
    if blocked_report_path:
        report["artifacts"].append(blocked_report_path)
    report["artifacts"] = sorted(set(str(path) for path in report["artifacts"] if path))

    _write_json(scene_dir / GENERATION_REPORT_JSON, report)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"[OK] generated: {spec['page_name']}")
        print(f"  output_dir: {scene_dir}")
        print(f"  background_consistency: {preflight.get('quality', {}).get('background_consistency')}")
        print(f"  cutout_completeness: {preflight.get('quality', {}).get('cutout_completeness')}")
        print(f"  quality_gates: {quality_gates}")
        if design_reference:
            print(f"  design_reference_preview: {design_reference}")
        if layered_preview:
            print(f"  layered_preview: {layered_preview}")
        if render_png:
            print(f"  lvgl_render_png: {render_png}")
        if object_tree:
            print(f"  object_tree_json: {object_tree}")
        if diff_report:
            print(f"  visual_diff_report: {diff_report.get('visual_diff_report_path')}")
        if blocked:
            print("  note: background gate blocked, skipped layered pixel reconstruction by design")

    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate LVGL scene from predefined design assets")
    parser.add_argument("--scene", default="interactive_favorite", help="Scene preset name")
    parser.add_argument("--output-dir", default=None, help="Override output directory")
    parser.add_argument("--background-gate-threshold", type=float, default=24.0)
    parser.add_argument("--render-mode", default="auto", choices=["auto", "preview", "probe"])
    parser.add_argument("--no-render", action="store_true", help="Skip LVGL render + screenshot")
    parser.add_argument("--run-visual-diff", action="store_true", help="Run visual diff against design")
    parser.add_argument("--diff-threshold", type=int, default=8)
    parser.add_argument(
        "--force-complete",
        action="store_true",
        help="Force layered reconstruction even when background gate is blocked",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON report")
    parser.add_argument("--list-scenes", action="store_true", help="List available scenes")
    return parser.parse_args(argv)


def list_scenes() -> int:
    for name, spec in SCENE_PRESETS.items():
        print(f"- {name}: page={spec['page_name']} moods={','.join(spec['default_mood_order'])}")
    return 0


def main() -> int:
    args = parse_args()
    if args.list_scenes:
        return list_scenes()
    return run_scene(args)


if __name__ == "__main__":
    raise SystemExit(main())
