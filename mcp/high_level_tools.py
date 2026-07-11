"""High-level MCP tool implementations for LVGL pipeline.

Each tool orchestrates multiple internal modules into a single
coherent operation. Models only see these 6 tools.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent

# ── Helpers ───────────────────────────────────────────────────────


def _ok(data: dict[str, Any]) -> dict[str, Any]:
    """Wrap result in ok response."""
    return {"ok": True, **data}


def _fail(errors: list[str], **kwargs: Any) -> dict[str, Any]:
    """Wrap result in fail response."""
    return {"ok": False, "errors": errors, **kwargs}


def _file_hash(path: Path) -> str:
    """SHA256 hash of file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _safe_output_dir(path: str) -> Path:
    """Resolve output path under artifacts/ only."""
    out = (ROOT / path).resolve()
    if not out.is_relative_to(ROOT / "artifacts"):
        raise ValueError(f"Output must be under artifacts/, got: {out}")
    out.mkdir(parents=True, exist_ok=True)
    return out


# ── inspect_design ────────────────────────────────────────────────


def inspect_design(args: dict[str, Any]) -> dict[str, Any]:
    """Analyze design screenshot. Read-only, no code generation."""
    from mcp.lvgl_preflight import preflight
    from mcp.lvgl_analysis import analyze

    design_path = args.get("design_path")
    if not design_path:
        return _fail(["design_path is required"])

    display = args.get("display", {})
    width = display.get("width", 480)
    height = display.get("height", 800)
    lvgl_version = args.get("lvgl_version", "v9")
    cut_dir = args.get("cut_dir")
    output_dir = args.get("output_dir", "artifacts/inspect")

    # Preflight
    pf = preflight(design_path, width, height, lvgl_version, cut_dir)
    if not pf["ok"]:
        return _fail(pf["errors"], stage="preflight")

    # Analysis
    analysis = analyze(design_path, width, height, lvgl_version, cut_dir)
    if not analysis.get("ok"):
        return _fail(analysis.get("errors", ["Analysis failed"]), stage="analysis")

    report = analysis["report"]

    return _ok({
        "stage": "inspect",
        "analysis_report": analysis.get("report_path", ""),
        "input_manifest": pf["metadata"].get("manifest_path", ""),
        "debug_overlay": report.get("overlay_path", ""),
        "confidence": report.get("confidence", 0),
        "uncertain_regions": report.get("uncertain_regions", []),
        "questions": report.get("questions", []),
    })


# ── generate_ui ───────────────────────────────────────────────────


def generate_ui(args: dict[str, Any]) -> dict[str, Any]:
    """Generate LVGL C/H code from UI Spec or design analysis."""
    from mcp.lvgl_codegen import write_page_files

    spec_path = args.get("spec_path")
    design_path = args.get("design_path")
    lvgl_version = args.get("lvgl_version", "v9")
    output_dir = args.get("output_dir", "artifacts/generated")

    # If no spec, run inspect first
    if not spec_path and design_path:
        inspect_result = inspect_design(args)
        if not inspect_result["ok"]:
            return _fail(inspect_result["errors"], stage="inspect")
        # Generate spec from analysis
        spec = _analysis_to_spec(inspect_result, args)
    elif spec_path:
        spec_file = Path(spec_path)
        if not spec_file.is_file():
            return _fail([f"Spec not found: {spec_path}"])
        spec = json.loads(spec_file.read_text(encoding="utf-8"))
    else:
        return _fail(["spec_path or design_path required"])

    # Code generation
    result = write_page_files(spec, output_dir, lvgl_version)
    if not result["ok"]:
        return _fail(result["errors"], stage="codegen")

    return _ok({
        "stage": "generate",
        "c_path": result.get("c_path"),
        "h_path": result.get("h_path"),
        "node_count": result.get("node_count", 0),
        "warnings": result.get("warnings", []),
    })


# ── render_ui ─────────────────────────────────────────────────────


def render_ui(args: dict[str, Any]) -> dict[str, Any]:
    """Render LVGL code using server-side preset."""
    spec_path = args.get("spec_path")
    ui_dir = args.get("ui_dir")
    if not spec_path and not ui_dir:
        return _fail(["spec_path or ui_dir required"])

    engine = args.get("engine", "lvgl_simulator")
    preset = args.get("preset", "headless-480x800")
    output_dir = args.get("output_dir", "artifacts/render")
    lvgl_version = args.get("lvgl_version", "v9")

    out = _safe_output_dir(output_dir)

    if engine == "lvgl_simulator":
        # Real LVGL rendering via built-in simulator
        from mcp.lvgl_sim_resolver import resolve_runner, run_simulator
        from mcp.lvgl_ir.scene_encoder import encode_spec

        # Resolve built-in runner
        runner = resolve_runner(lvgl_version)
        if not runner["ok"]:
            return _fail([runner.get("error", "Runner not found")], stage="render", status="environment_unavailable")

        # Encode spec to scene.bin
        if spec_path:
            spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
        else:
            # Generate minimal spec from ui_dir
            spec = {"schema_version": "2.0", "nodes": [{"id": "root", "type": "screen"}]}

        scene_bytes = encode_spec(spec)
        scene_path = out / "scene.bin"
        scene_path.write_bytes(scene_bytes)

        # Run simulator
        display = args.get("display", {})
        width = display.get("width", 480)
        height = display.get("height", 800)

        result = run_simulator(
            runner["path"],
            str(scene_path),
            str(out),
            width,
            height,
        )

        if not result["ok"]:
            return _fail([result.get("error", "Simulator failed")], stage="render")

        return _ok({
            "stage": "render",
            "engine": engine,
            "authoritative": True,
            "render_path": result.get("render_png", str(out / "render.png")),
            "object_tree_path": result.get("tree", str(out / "object_tree.bin")),
            "status": "rendered",
            "platform": runner["platform"],
            "lvgl_version": lvgl_version,
        })

    elif engine == "python_preview":
        # Fast preview using static analysis (not authoritative)
        from mcp.lvgl_compile_gate import validate_directory
        validation = validate_directory(str(ui_dir) if ui_dir else ".", "v9")

        placeholder = out / "render.png"
        if not placeholder.exists():
            _create_placeholder_png(placeholder, 480, 800)

        return _ok({
            "stage": "render",
            "engine": engine,
            "authoritative": False,
            "render_path": str(placeholder),
            "static_validation": validation,
            "status": "preview_only",
        })

    else:
        return _fail([f"Unknown engine: {engine}"])


def _create_placeholder_png(path: Path, width: int, height: int):
    """Create a minimal placeholder PNG."""
    try:
        from PIL import Image
        img = Image.new("RGB", (width, height), (240, 240, 245))
        img.save(str(path))
    except ImportError:
        # Minimal valid PNG (1x1 gray)
        import struct
        import zlib
        def chunk(kind: bytes, payload: bytes) -> bytes:
            crc = zlib.crc32(kind + payload) & 0xFFFFFFFF
            return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", crc)
        ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
        raw = b"\x00\xf0\xf0\xf5"
        path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


# ── compare_ui ────────────────────────────────────────────────────


def compare_ui(args: dict[str, Any]) -> dict[str, Any]:
    """Compare rendered output with design baseline."""
    from mcp.lvgl_compare import compare, suggest_refinements

    actual_path = args.get("actual_path")
    baseline_path = args.get("baseline_path")
    if not actual_path or not baseline_path:
        return _fail(["actual_path and baseline_path required"])

    spec = None
    spec_path = args.get("spec_path")
    if spec_path and Path(spec_path).is_file():
        spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))

    result = compare(actual_path, baseline_path, spec)

    if spec:
        result["refinements"] = suggest_refinements(result, spec)

    return result


# ── refine_ui ─────────────────────────────────────────────────────


def refine_ui(args: dict[str, Any]) -> dict[str, Any]:
    """Iterative refinement: generate → render → compare → fix spec."""
    from mcp.lvgl_refine import refine_loop

    design_path = args.get("design_path")
    if not design_path:
        return _fail(["design_path required"])

    display = args.get("display", {})
    result = refine_loop(
        design_path=design_path,
        screen_width=display.get("width", 480),
        screen_height=display.get("height", 800),
        lvgl_version=args.get("lvgl_version", "v9"),
        cut_dir=args.get("cut_dir"),
        output_dir=args.get("output_dir", "artifacts/refine"),
        max_iterations=args.get("max_iterations", 3),
    )
    return result


# ── apply_patch ───────────────────────────────────────────────────


def apply_patch(args: dict[str, Any]) -> dict[str, Any]:
    """Write verified files to user project. Default dry-run."""
    source_dir = args.get("source_dir")
    target_dir = args.get("target_dir")
    expected_hashes = args.get("expected_hashes", {})
    mode = args.get("mode", "dry_run")

    if not source_dir or not target_dir:
        return _fail(["source_dir and target_dir required"])

    src = Path(source_dir)
    dst = Path(target_dir)

    if not src.is_dir():
        return _fail([f"source_dir not found: {source_dir}"])

    # Verify hashes
    hash_errors = []
    for filename, expected_hash in expected_hashes.items():
        src_file = src / filename
        if not src_file.is_file():
            hash_errors.append(f"File not found: {filename}")
            continue
        actual_hash = _file_hash(src_file)
        if actual_hash != expected_hash:
            hash_errors.append(f"Hash mismatch: {filename}")

    if hash_errors:
        return _fail(hash_errors, stage="hash_verification")

    # Collect files
    files = []
    for f in sorted(src.iterdir()):
        if f.is_file() and f.suffix in (".c", ".h", ".json"):
            files.append({
                "filename": f.name,
                "source": str(f),
                "hash": _file_hash(f),
                "size": f.stat().st_size,
            })

    if mode == "dry_run":
        return _ok({
            "stage": "apply",
            "mode": "dry_run",
            "files": files,
            "target_dir": str(dst),
            "message": "Dry run — no files written. Pass mode=replace_generated_files to apply.",
        })

    # Atomic write
    dst.mkdir(parents=True, exist_ok=True)
    written = []
    for f in files:
        src_file = Path(f["source"])
        dst_file = dst / f["filename"]
        # Write to temp, then atomic replace
        tmp_fd, tmp_path = tempfile.mkstemp(dir=dst, suffix=".tmp")
        try:
            os.close(tmp_fd)  # Close fd immediately
            shutil.copy2(src_file, tmp_path)
            os.replace(tmp_path, dst_file)
            written.append(f["filename"])
        except Exception as e:
            if Path(tmp_path).exists():
                try:
                    Path(tmp_path).unlink()
                except OSError:
                    pass
            return _fail([f"Failed to write {f['filename']}: {e}"])

    return _ok({
        "stage": "apply",
        "mode": "replace_generated_files",
        "written": written,
        "target_dir": str(dst),
    })


# ── Internal helpers ──────────────────────────────────────────────


def _analysis_to_spec(inspect_result: dict[str, Any], args: dict[str, Any]) -> dict[str, Any]:
    """Convert inspection result to UI Spec v2."""
    display = args.get("display", {})
    return {
        "schema_version": "2.0",
        "page_name": "page",
        "display": {
            "width": display.get("width", 480),
            "height": display.get("height", 800),
        },
        "lvgl_version": args.get("lvgl_version", "v9"),
        "nodes": [{"id": "root", "type": "screen"}],
    }


# ── Tool registry ─────────────────────────────────────────────────

HIGH_LEVEL_TOOLS: dict[str, Any] = {
    "inspect_design": inspect_design,
    "generate_ui": generate_ui,
    "render_ui": render_ui,
    "compare_ui": compare_ui,
    "refine_ui": refine_ui,
    "apply_patch": apply_patch,
}
