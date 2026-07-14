"""High-level MCP tool implementations for LVGL pipeline.

Each tool orchestrates multiple internal modules into a single
coherent operation. Models only see these 6 tools.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
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


def _result_artifacts(result: dict[str, Any], output_dir: str | None) -> dict[str, str]:
    """Extract stable artifact paths from a high-level tool response."""
    keys = (
        "analysis_report", "debug_overlay", "initial_asset_manifest", "spec_path", "asset_pack_path",
        "c_path", "h_path", "render_path", "object_tree_path",
        "object_tree_json_path", "diff_overlay_path", "app_evidence_path", "evidence_path",
        "clarification_contract", "ui_decisions",
    )
    artifacts = {
        key: str(result[key]) for key in keys
        if isinstance(result.get(key), str) and result[key]
    }
    if output_dir:
        artifacts["output_dir"] = output_dir
    return artifacts


def _record_run_result(run_id: str | None, stage: str, args: dict[str, Any], result: dict[str, Any], *, success_status: str) -> dict[str, Any]:
    """Record an MCP stage without changing legacy path-mode responses."""
    if not run_id:
        return result
    from mcp.lvgl_run import manifest_path, record_stage

    status = success_status if result.get("ok") else str(result.get("status") or "failed")
    if status not in {"inspected", "generated", "rendered", "compared", "verified", "manual_required", "capability_unavailable"}:
        status = "failed"
    manifest = record_stage(
        run_id,
        stage=stage,
        status=status,
        artifacts=_result_artifacts(result, args.get("output_dir")),
        details={
            "tool_status": result.get("status"),
            "ok": bool(result.get("ok")),
            "authoritative": bool(result.get("authoritative", False)),
            "engine": result.get("engine"),
        },
    )
    result["run_id"] = run_id
    result["run_status"] = manifest["status"]
    result["stage_manifest_path"] = str(manifest_path(run_id))
    return result


def _resolve_run_args(args: dict[str, Any], stage: str) -> tuple[dict[str, Any], str | None]:
    run_id = args.get("run_id")
    if not run_id:
        return dict(args), None
    from mcp.lvgl_run import resolve_args
    resolved, _run = resolve_args(str(run_id), args, stage=stage)
    return resolved, str(run_id)


# ── inspect_design ────────────────────────────────────────────────


def _inspect_design_legacy(args: dict[str, Any]) -> dict[str, Any]:
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
    out = _safe_output_dir(args.get("output_dir", "artifacts/inspect"))

    # Preflight
    pf = preflight(design_path, width, height, lvgl_version, cut_dir)
    if not pf["ok"]:
        return _fail(pf["errors"], stage="preflight")

    # Analysis
    analysis = analyze(design_path, width, height, lvgl_version, cut_dir, output_dir=out)
    if not analysis.get("ok"):
        return _fail(analysis.get("errors", ["Analysis failed"]), stage="analysis")

    report = analysis["report"]

    response = {
        "stage": "inspect",
        "analysis_report": analysis.get("report_path", ""),
        "debug_overlay": report.get("overlay_path", ""),
        "confidence": report.get("confidence", 0),
        "uncertain_regions": report.get("uncertain_regions", []),
        "questions": report.get("questions", []),
    }
    asset_intents = args.get("asset_intents")
    from mcp.ui_interaction import build_interaction_contract, load_decisions, write_interaction_artifacts
    try:
        decisions = load_decisions(args.get("ui_decisions_path"), args.get("interaction_decisions"))
        interaction = build_interaction_contract(
            mode=str(args.get("interaction_mode", "standard")),
            analysis_questions=report.get("questions", []),
            asset_intents=asset_intents,
            decisions=decisions,
        )
    except ValueError as exc:
        return _fail([str(exc)], stage="clarification", status="invalid_input")
    clarification_path, decisions_path = write_interaction_artifacts(out, interaction, decisions)
    response.update({
        "interaction": interaction,
        "clarification_contract": str(clarification_path),
        "ui_decisions": str(decisions_path),
        "questions": interaction["questions"],
    })
    if not interaction["ready_for_codegen"]:
        return _ok({
            **response,
            "status": "manual_required",
            "manual_required": interaction["unresolved_ids"],
        })
    if asset_intents is None:
        return _ok({**response, "status": "manual_required", "manual_required": ["asset_intents must be supplied by visual analysis before deterministic asset resolution"]})

    from mcp.asset_contract import DEFAULT_UI_FLASH_BYTES, build_initial_manifest, write_initial_manifest

    asset_root_arg = args.get("asset_root") or args.get("cut_dir")
    asset_root = Path(asset_root_arg).resolve() if asset_root_arg else None
    package_root = asset_root.parent if asset_root and asset_root.name.lower() == "assets" else None
    design = Path(design_path).resolve()
    if package_root:
        try:
            design_reference = design.relative_to(package_root).as_posix()
        except ValueError:
            design_reference = str(design)
        stored_asset_root = asset_root.relative_to(package_root).as_posix()
    else:
        design_reference = str(design)
        stored_asset_root = str(asset_root) if asset_root else None
    requested_flash_budget = args.get("asset_flash_budget_bytes")
    manifest = build_initial_manifest(
        project=str(args.get("project") or design.stem), design_reference=design_reference,
        display=display, assets=asset_intents, asset_root=stored_asset_root,
        max_flash_bytes=DEFAULT_UI_FLASH_BYTES if requested_flash_budget is None else requested_flash_budget,
    )
    written = write_initial_manifest(out / "initial_asset_manifest.json", manifest)
    if not written.get("ok"):
        return _fail(written["errors"], stage="asset_intent_contract", status="invalid_asset_contract")
    return _ok({**response, "status": "initial_asset_manifest_ready", "initial_asset_manifest": written["path"]})


def inspect_design(args: dict[str, Any]) -> dict[str, Any]:
    """Analyze a design and create a run ledger for subsequent pipeline calls."""
    result = _inspect_design_legacy(args)
    if not result.get("ok"):
        return result
    from mcp.lvgl_capabilities import get_capabilities, verification_plan
    from mcp.lvgl_run import create_run, manifest_path, record_stage

    display = args.get("display") or {"width": 480, "height": 800}
    lvgl_version = str(args.get("lvgl_version", "v9"))
    artifacts = _result_artifacts(result, args.get("output_dir", "artifacts/inspect"))
    run = create_run(
        design_path=str(args["design_path"]),
        display=display,
        lvgl_version=lvgl_version,
        artifacts=artifacts,
    )
    if result.get("status") == "manual_required":
        run = record_stage(run["run_id"], stage="asset_contract", status="manual_required", artifacts=artifacts)
    result.update({
        "run_id": run["run_id"],
        "run_status": run["status"],
        "stage_manifest_path": str(manifest_path(run["run_id"])),
        "capabilities": get_capabilities(lvgl_version),
        "verification_plan": verification_plan(lvgl_version),
    })
    return result


# ── generate_ui ───────────────────────────────────────────────────


def _generate_ui_legacy(args: dict[str, Any]) -> dict[str, Any]:
    """Generate LVGL C/H code from UI Spec or design analysis."""
    from mcp.lvgl_codegen import write_page_files

    ui_dir = args.get("ui_dir")
    if ui_dir:
        from mcp.standard_ui_package import generate_standard_ui_package
        return generate_standard_ui_package(
            ui_dir,
            _safe_output_dir(args.get("output_dir", "artifacts/auto_ui")),
            asset_manifest_path=args.get("asset_manifest_path"),
            font_path=args.get("font_path"),
            strict_asset_contract=bool(args.get("strict_asset_contract", True)),
            final_only=args.get("delivery_mode", "final_only") == "final_only",
            cleanup_intermediates=bool(args.get("cleanup_intermediates", True)),
        )

    manifest_path = args.get("manifest_path")
    if manifest_path:
        return _generate_app_mvp(manifest_path, args)

    spec_path = args.get("spec_path")
    design_path = args.get("design_path")
    lvgl_version = args.get("lvgl_version", "v9")
    output_dir = args.get("output_dir", "artifacts/generated")
    template = str(args.get("template", "auto"))

    if design_path and not spec_path and not args.get("asset_manifest_path") and bool(args.get("strict_asset_contract", True)):
        return _fail(
            ["A design-driven generation requires asset_manifest_path from inspect_design; design screenshots cannot be used as runtime assets or cutout sources"],
            stage="asset_contract", status="manual_required",
        )

    if template not in {"auto", "interactive_scene", "generic"}:
        return _fail([f"Unknown template: {template}"], stage="generate")

    if not spec_path and design_path and _should_use_interactive_scene(template, args):
        return _generate_interactive_scene_v2(args)

    # If no spec, run inspect first
    if not spec_path and design_path:
        from mcp.lvgl_preflight import preflight
        from mcp.lvgl_analysis import analyze

        display = args.get("display", {})
        width = display.get("width", 480)
        height = display.get("height", 800)
        preflight = preflight(design_path, width, height, lvgl_version, args.get("cut_dir"))
        if not preflight.get("ok"):
            return _fail(preflight.get("errors", ["Design preflight failed"]), stage="preflight")
        analysis = analyze(design_path, width, height, lvgl_version, args.get("cut_dir"))
        if not analysis.get("ok"):
            return _fail(analysis.get("errors", ["Design analysis failed"]), stage="analysis")
        spec = _analysis_to_spec(analysis["report"], args)
        if len(spec["nodes"]) <= 1:
            return _fail(["Analysis did not produce renderable UI nodes; provide a supported template or a UI Spec v2 file"], stage="analysis", status="insufficient_analysis")
    elif spec_path:
        spec_file = Path(spec_path)
        if not spec_file.is_file():
            return _fail([f"Spec not found: {spec_path}"])
        spec = json.loads(spec_file.read_text(encoding="utf-8"))
    else:
        return _fail(["spec_path or design_path required"])

    out = _safe_output_dir(output_dir)

    # A UI project may declare its own LVGL fonts in ui/manifest.json.  Apply
    # that contract to every codegen path, not only semantic templates.
    font_warnings: list[str] = []
    cut_dir_arg = args.get("cut_dir")
    if cut_dir_arg:
        cut_dir = Path(str(cut_dir_arg)).resolve()
        if cut_dir.is_dir():
            source_design = Path(str(design_path)).resolve() if design_path else None
            try:
                manifest_fonts, font_warnings = _resolve_manifest_fonts(
                    cut_dir,
                    source_design,
                    page_name=str(spec.get("page_name", "")),
                    template=template,
                )
            except ValueError as exc:
                return _fail([str(exc)], stage="fonts", status="font_config_invalid")
            if manifest_fonts:
                bundle = _write_user_font_bundle(out, manifest_fonts, str(spec.get("page_name", "page")))
                _apply_manifest_fonts_to_spec(spec, manifest_fonts, bundle)

    # Validate generated spec before writing
    from mcp.lvgl_ir.spec_validator import validate_spec
    display_cfg = args.get("display", {})
    validation = validate_spec(
        spec,
        asset_pack_path=args.get("asset_pack_path"),
        display=display_cfg,
        expected_lvgl_version=lvgl_version,
    )
    if not validation["valid"]:
        return _fail(
            validation["errors"],
            stage="generate",
            status="invalid_input",
            validation=validation,
        )

    spec_path_out = out / "ui_spec.json"
    spec_path_out.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")

    # Code generation
    result = write_page_files(spec, str(out), lvgl_version)
    if not result["ok"]:
        return _fail(result["errors"], stage="codegen")

    return _ok({
        "stage": "generate",
        "c_path": result.get("c_path"),
        "h_path": result.get("h_path"),
        "spec_path": str(spec_path_out),
        "node_count": result.get("node_count", 0),
        "font_sources": [
            font.get("output_source") or font.get("source")
            for font in spec.get("fonts", []) if isinstance(font, dict) and (font.get("output_source") or font.get("source"))
        ],
        "font_cmake_path": spec.get("font_bundle", {}).get("cmake_path", ""),
        "warnings": font_warnings + result.get("warnings", [], ) + validation.get("warnings", []),
        "validation": validation,
    })


def generate_ui(args: dict[str, Any]) -> dict[str, Any]:
    """Generate code, optionally inheriting deterministic inputs from a run."""
    try:
        resolved, run_id = _resolve_run_args(args, "generate")
        if run_id:
            from mcp.lvgl_run import load_run
            run = load_run(run_id)
            if run.get("status") == "manual_required":
                return _fail(
                    ["Run has unresolved design decisions. Complete inspect_design clarification before code generation."],
                    stage="clarification", status="manual_required", run_id=run_id,
                )
        if run_id and not resolved.get("asset_manifest_path"):
            from mcp.lvgl_run import latest_artifact
            asset_manifest_path = latest_artifact(run_id, "initial_asset_manifest")
            if asset_manifest_path:
                resolved["asset_manifest_path"] = asset_manifest_path
        if run_id and resolved.get("ui_dir") and "delivery_mode" not in args:
            # A ledger-backed request is expected to continue to native render.
            # Keep the v2 render spec and asset pack as run evidence.
            resolved["delivery_mode"] = "full_evidence"
            resolved["cleanup_intermediates"] = False
    except ValueError as exc:
        return _fail([str(exc)], stage="generate", status="invalid_run")
    result = _generate_ui_legacy(resolved)
    if result.get("ok"):
        from mcp.lvgl_capabilities import get_capabilities, verification_plan
        version = str(resolved.get("lvgl_version", "v9"))
        result["capabilities"] = get_capabilities(version)
        result["verification_plan"] = verification_plan(version)
    return _record_run_result(run_id, "generate", resolved, result, success_status="generated")


# ── render_ui ─────────────────────────────────────────────────────


def _render_ui_legacy(args: dict[str, Any]) -> dict[str, Any]:
    """Render LVGL code using server-side preset."""
    spec_path = args.get("spec_path")
    if not spec_path:
        return _fail(["spec_path is required"])

    engine = args.get("engine", "lvgl_simulator")
    preset = args.get("preset", "headless-480x800")
    output_dir = args.get("output_dir", "artifacts/render")
    lvgl_version = args.get("lvgl_version", "v9")

    if engine == "lvgl_simulator":
        # Real LVGL rendering via built-in simulator
        from mcp.lvgl_sim_resolver import resolve_runner, run_simulator
        from mcp.lvgl_ir.scene_encoder import encode_spec
        from mcp.lvgl_ir.spec_validator import validate_spec

        # Read and validate spec
        try:
            spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return _fail([f"Unable to read UI Spec: {exc}"], stage="render", status="invalid_spec")

        # Full structural validation before encoding
        display_cfg = args.get("display", {})
        validation = validate_spec(
            spec,
            asset_pack_path=args.get("asset_pack_path"),
            display=display_cfg,
            expected_lvgl_version=lvgl_version,
        )
        if not validation["valid"]:
            return _fail(
                validation["errors"],
                stage="render",
                status="invalid_input",
                validation=validation,
            )

        out = _safe_output_dir(output_dir)

        # Resolve built-in runner
        runner = resolve_runner(lvgl_version)
        if not runner["ok"]:
            return _fail([runner.get("error", "Runner not found")], stage="render", status="environment_unavailable")

        font_bindings, missing_font_previews = _native_font_bindings(spec)
        if missing_font_previews:
            return _fail(
                ["Native render requires LVGL .bin preview fonts for: " + ", ".join(missing_font_previews)],
                stage="render",
                status="font_preview_unavailable",
                missing_font_ids=missing_font_previews,
            )

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
            asset_pack_path=args.get("asset_pack_path"),
            font_bindings=font_bindings,
        )

        if not result["ok"]:
            return _fail([result.get("error", "Simulator failed")], stage="render")

        loaded_font_ids = set(result.get("font_load_report", {}).get("font_ids", []))
        if set(font_bindings) != loaded_font_ids:
            return _fail(
                ["Native runner did not provide complete font-load evidence"],
                stage="render",
                status="font_evidence_missing",
                expected_font_ids=sorted(font_bindings),
                loaded_font_ids=sorted(loaded_font_ids),
            )

        # Determine status — capability_gap if unsupported opcodes were hit
        render_status = "scene_rendered"
        if result.get("capability_gap"):
            render_status = "capability_gap"

        metadata = spec.get("metadata", {})
        limitations = metadata.get("native_render_limitations", []) if isinstance(metadata, dict) else []
        limitations = [str(item) for item in limitations if isinstance(item, str) and item]
        authoritative = not limitations
        if limitations and render_status == "scene_rendered":
            render_status = "scene_rendered_with_limitations"

        response = {
            "stage": "render",
            "engine": engine,
            "authoritative": authoritative,
            "render_path": result.get("render_png", str(out / "render.png")),
            "object_tree_path": result.get("tree", str(out / "object_tree.bin")),
            "object_tree_json_path": result.get("tree_json"),
            "status": render_status,
            "platform": runner["platform"],
            "lvgl_version": lvgl_version,
        }
        if limitations:
            response["native_render_limitations"] = limitations
        if font_bindings:
            response["font_evidence"] = {
                "requested": [
                    {"id": font_id, "source": source, "sha256": _file_hash(Path(source))}
                    for font_id, source in sorted(font_bindings.items())
                ],
                "loaded_ids": sorted(loaded_font_ids),
            }

        # Pass through evidence
        if result.get("asset_load_report"):
            response["asset_load_report"] = result["asset_load_report"]
        if result.get("renderer_capabilities"):
            response["renderer_capabilities"] = result["renderer_capabilities"]
        if result.get("font_load_report"):
            response["font_load_report"] = result["font_load_report"]
        if result.get("unsupported_opcodes"):
            response["unsupported_opcodes"] = result["unsupported_opcodes"]
        if result.get("capability_gap"):
            response["capability_gap"] = True

        if render_status == "capability_gap":
            return _fail(
                ["Native runner encountered unsupported scene operations"],
                **response,
            )
        return _ok(response)

    elif engine == "python_preview":
        # Fast preview using static analysis (not authoritative)
        out = _safe_output_dir(output_dir)
        from mcp.lvgl_compile_gate import validate_directory
        validation_result = validate_directory(
            str(Path(spec_path).parent) if spec_path else ".",
            lvgl_version,
        )

        placeholder = out / "render.png"
        if not placeholder.exists():
            _create_placeholder_png(placeholder, 480, 800)

        return _ok({
            "stage": "render",
            "engine": engine,
            "authoritative": False,
            "render_path": str(placeholder),
            "static_validation": validation_result,
            "status": "preview_only",
        })

    else:
        return _fail([f"Unknown engine: {engine}"])


def render_ui(args: dict[str, Any]) -> dict[str, Any]:
    """Render a UI with an explicit capability contract for v8/v9."""
    try:
        resolved, run_id = _resolve_run_args(args, "render")
        if run_id and not resolved.get("spec_path"):
            from mcp.lvgl_run import latest_artifact
            spec_path = latest_artifact(run_id, "spec_path")
            if not spec_path:
                return _fail(["run_id has no generated ui_spec.json; call generate_ui first"], stage="render", status="missing_stage")
            resolved["spec_path"] = spec_path
        if run_id and not resolved.get("asset_pack_path"):
            from mcp.lvgl_run import latest_artifact
            asset_pack_path = latest_artifact(run_id, "asset_pack_path")
            if asset_pack_path:
                resolved["asset_pack_path"] = asset_pack_path
    except ValueError as exc:
        return _fail([str(exc)], stage="render", status="invalid_run")

    from mcp.lvgl_capabilities import get_capabilities, verification_plan
    version = str(resolved.get("lvgl_version", "v9"))
    capability = get_capabilities(version)
    engine = str(resolved.get("engine", "lvgl_simulator"))
    if engine == "lvgl_simulator" and not capability["native_render"]:
        result = _fail(
            [capability["native_render_reason"]],
            stage="render",
            status="capability_unavailable",
            capabilities=capability,
            verification_plan=verification_plan(version),
            recommended_engine="python_preview",
        )
        return _record_run_result(run_id, "render", resolved, result, success_status="rendered")

    result = _render_ui_legacy(resolved)
    result["capabilities"] = capability
    result["verification_plan"] = verification_plan(version)
    return _record_run_result(run_id, "render", resolved, result, success_status="rendered")


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


def _compare_ui_legacy(args: dict[str, Any]) -> dict[str, Any]:
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

    profile = args.get("threshold_profile", "golden_strict")
    result = compare(actual_path, baseline_path, spec, profile=profile)

    if spec:
        result["refinements"] = suggest_refinements(result, spec)

    return result


def compare_ui(args: dict[str, Any]) -> dict[str, Any]:
    """Compare artifacts from one run, or preserve legacy path-mode usage."""
    try:
        resolved, run_id = _resolve_run_args(args, "compare")
        if run_id:
            from mcp.lvgl_run import latest_artifact, load_run
            run = load_run(run_id)
            inherited = {
                "actual_path": latest_artifact(run_id, "render_path"),
                "baseline_path": run.get("inputs", {}).get("design_path"),
                "spec_path": latest_artifact(run_id, "spec_path"),
            }
            for key, value in inherited.items():
                if not resolved.get(key) and value:
                    resolved[key] = value
    except ValueError as exc:
        return _fail([str(exc)], stage="compare", status="invalid_run")
    result = _compare_ui_legacy(resolved)
    success_status = "compared"
    if run_id and result.get("status") == "passed":
        from mcp.lvgl_run import latest_artifact, load_run
        expected_render = latest_artifact(run_id, "render_path")
        same_render = expected_render and Path(expected_render).resolve() == Path(str(resolved.get("actual_path", ""))).resolve()
        run = load_run(run_id)
        render_stages = [stage for stage in run.get("stages", []) if stage.get("stage") == "render"]
        authoritative = bool(render_stages and render_stages[-1].get("details", {}).get("authoritative"))
        if same_render and authoritative:
            success_status = "verified"
        else:
            result["verification_note"] = "Comparison passed, but verification requires the run's own authoritative native render."
    return _record_run_result(run_id, "compare", resolved, result, success_status=success_status)


# ── refine_ui ─────────────────────────────────────────────────────


def _refine_ui_legacy(args: dict[str, Any]) -> dict[str, Any]:
    """Evaluate external native evidence and promote the best candidate."""
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
        baseline_evidence_path=args.get("baseline_evidence_path"),
        candidate_evidence_paths=args.get("candidate_evidence_paths"),
    )
    return result


def refine_ui(args: dict[str, Any]) -> dict[str, Any]:
    """Promote evidence candidates; this tool intentionally does not edit specs."""
    try:
        resolved, run_id = _resolve_run_args(args, "refine")
    except ValueError as exc:
        return _fail([str(exc)], stage="refine", status="invalid_run")
    if not resolved.get("design_path"):
        return _fail(["design_path or run_id required"], stage="refine", status="missing_input")
    result = _refine_ui_legacy(resolved)
    status = "verified" if result.get("ok") else str(result.get("status") or "failed")
    return _record_run_result(run_id, "refine", resolved, result, success_status=status)


# ── apply_patch ───────────────────────────────────────────────────


def apply_patch(args: dict[str, Any]) -> dict[str, Any]:
    """Write verified files to user project. Default dry-run."""
    run_id = args.get("run_id")
    source_dir = args.get("source_dir")
    target_dir = args.get("target_dir")
    expected_hashes = args.get("expected_hashes", {})
    mode = args.get("mode", "dry_run")

    if not target_dir:
        return _fail(["target_dir required"])

    if run_id:
        try:
            from mcp.lvgl_run import latest_artifact, load_run, stage_artifact
            run = load_run(str(run_id))
            if run.get("status") != "verified":
                return _fail(
                    [f"Run status is {run.get('status')!r}, not 'verified'. Only verified runs may apply patches."],
                    stage="apply",
                    status=run.get("status"),
                    run_id=run_id,
                )
            c_path = latest_artifact(str(run_id), "c_path")
            generated_output = stage_artifact(str(run_id), "generate", "output_dir")
            if not c_path and not generated_output:
                return _fail(["verified run has no generated output artifact"], stage="apply", status="missing_artifact", run_id=run_id)
            derived_source = str(Path(c_path).parent) if c_path else str(generated_output)
            if source_dir and Path(source_dir).resolve() != Path(derived_source).resolve():
                return _fail(["source_dir conflicts with run_id generated output"], stage="apply", status="invalid_run", run_id=run_id)
            source_dir = derived_source
        except ValueError as exc:
            return _fail([str(exc)], stage="apply", status="invalid_run", run_id=run_id)

    if not source_dir:
        return _fail(["source_dir or run_id required"])

    src = Path(source_dir)
    dst = Path(target_dir)

    if not src.is_dir():
        return _fail([f"source_dir not found: {source_dir}"])

    # Gate: only verified runs may apply in replace mode
    if mode == "replace_generated_files":
        run_manifest_path = src / "run_manifest.json"
        if run_manifest_path.is_file():
            try:
                run_manifest = json.loads(run_manifest_path.read_text(encoding="utf-8"))
                run_status = run_manifest.get("status")
                if run_status != "verified":
                    return _fail(
                        [f"Run status is {run_status!r}, not 'verified'. Only verified runs may apply patches."],
                        stage="apply",
                        status=run_status,
                    )
            except (OSError, json.JSONDecodeError):
                pass  # No valid manifest — allow legacy behavior

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
        if f.is_file() and f.suffix.lower() in (".c", ".h", ".cmake"):
            files.append({
                "filename": f.name,
                "source": str(f),
                "hash": _file_hash(f),
                "size": f.stat().st_size,
            })

    if mode == "dry_run":
        response = _ok({
            "stage": "apply",
            "mode": "dry_run",
            "files": files,
            "target_dir": str(dst),
            "message": "Dry run — no files written. Pass mode=replace_generated_files to apply.",
        })
        if not run_id:
            response["migration_hint"] = "Prefer run_id from inspect_design; source_dir mode is retained for compatibility."
        return response

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

    response = _ok({
        "stage": "apply",
        "mode": "replace_generated_files",
        "written": written,
        "target_dir": str(dst),
    })
    if run_id:
        response["run_id"] = run_id
    return response


# ── Internal helpers ──────────────────────────────────────────────


def _generate_app_mvp(manifest_path: str, args: dict[str, Any]) -> dict[str, Any]:
    """Generate multi-page app from Manifest v2.

    Validates the manifest, resolves shared inheritance, then generates
    per-page code plus app-level Router/Presenter/Model scaffolding.
    """
    from mcp.manifest_v2 import load_manifest, validate_manifest, resolve_manifest

    try:
        manifest = load_manifest(manifest_path)
    except FileNotFoundError as exc:
        return _fail([str(exc)], stage="manifest", status="file_not_found")
    except Exception as exc:
        return _fail([f"Failed to read manifest: {exc}"], stage="manifest")

    manifest_root = Path(manifest_path).resolve().parent
    validation = validate_manifest(manifest, manifest_root)
    if not validation["ok"]:
        return _fail(
            validation["errors"],
            stage="manifest",
            status="invalid_manifest",
            warnings=validation.get("warnings", []),
        )

    if manifest.get("schema_version") not in {"2.0", "2.1"}:
        return _fail(
            ["manifest_path requires schema_version '2.0' or '2.1'; use spec_path for single-page v1"],
            stage="manifest",
            status="wrong_version",
        )

    if manifest.get("schema_version") == "2.1":
        return _generate_app_v21(manifest_path, manifest, args, validation)

    resolved = resolve_manifest(manifest)
    app_id = resolved["app"]["id"]
    display = resolved.get("display", {})
    lvgl_version = args.get("lvgl_version", "v9")

    out = _safe_output_dir(args.get("output_dir", f"artifacts/ui_app/{app_id}"))
    app_dir = out / "app"
    app_dir.mkdir(parents=True, exist_ok=True)

    # Write resolved manifest
    resolved_path = app_dir / "ui_app_manifest_resolved.json"
    resolved_path.write_text(
        json.dumps(resolved, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8", newline="\n",
    )

    page_results: list[dict[str, Any]] = []
    page_errors: list[str] = []

    # Per-page: generate code using existing single-page pipeline
    for page in resolved.get("pages", []):
        page_id = page.get("id", "unknown")
        page_out = out / "pages" / page_id
        page_out.mkdir(parents=True, exist_ok=True)

        page_design = page.get("design")
        if not page_design:
            page_errors.append(f"Page {page_id!r}: no design specified")
            page_results.append({"page_id": page_id, "ok": False, "errors": ["no design"]})
            continue

        # Resolve design path relative to manifest location
        design_file = Path(manifest_path).parent / page_design
        if not design_file.is_file():
            page_errors.append(f"Page {page_id!r}: design not found: {page_design}")
            page_results.append({"page_id": page_id, "ok": False, "errors": [f"design not found: {page_design}"]})
            continue

        # Run inspect + generate for each page
        page_args = {
            "design_path": str(design_file),
            "display": display,
            "lvgl_version": lvgl_version,
            "output_dir": str(page_out),
            "template": page.get("template", "auto"),
        }
        cut_dir = args.get("cut_dir")
        if cut_dir:
            page_args["cut_dir"] = cut_dir

        try:
            page_result = generate_ui(page_args)
        except Exception as exc:
            page_result = {"ok": False, "errors": [f"Page {page_id!r} generation failed: {exc}"]}

        page_result["page_id"] = page_id
        page_results.append(page_result)
        if not page_result.get("ok"):
            page_errors.extend(
                f"Page {page_id!r}: {e}" for e in page_result.get("errors", [])
            )

    # Preliminary status from page results (refined after codegen + validation)
    all_ok = all(r.get("ok") for r in page_results)
    # v2.0 deliberately remains scaffold-only.  Static generation is useful,
    # but cannot substitute for state renders, native compilation and flows.
    status = "needs_manual_work"

    # ── Generate app-level C/H scaffolding ──
    from mcp.app_codegen import (
        generate_app_c, generate_app_h,
        generate_router_c, generate_router_h,
        generate_presenter_c, generate_presenter_h,
        generate_model_c, generate_model_h,
    )
    from mcp.lvgl_codegen import safe_c_identifier

    pages = resolved.get("pages", [])
    routes = resolved.get("routes", [])
    models = resolved.get("models", [])
    entry_page = resolved["app"]["entry_page"]
    max_depth = resolved.get("app", {}).get("navigation", {}).get("max_depth", 8)
    generated_files: list[str] = []

    # Router
    router_c = generate_router_c(app_id, pages, routes, max_depth)
    router_h = generate_router_h(app_id, pages, max_depth)
    (app_dir / "ui_router.c").write_text(router_c, encoding="utf-8", newline="\n")
    (app_dir / "ui_router.h").write_text(router_h, encoding="utf-8", newline="\n")
    generated_files.extend(["app/ui_router.c", "app/ui_router.h"])

    # App
    app_c = generate_app_c(app_id, entry_page, models)
    app_h = generate_app_h(app_id)
    (app_dir / "ui_app.c").write_text(app_c, encoding="utf-8", newline="\n")
    (app_dir / "ui_app.h").write_text(app_h, encoding="utf-8", newline="\n")
    generated_files.extend(["app/ui_app.c", "app/ui_app.h"])

    # Presenters
    pres_dir = out / "presenters"
    pres_dir.mkdir(parents=True, exist_ok=True)
    for page in pages:
        pid = page.get("id", "")
        pres_c = generate_presenter_c(pid, page.get("events", []), routes, models)
        pres_h = generate_presenter_h(pid)
        safe_pid = safe_c_identifier(pid)
        (pres_dir / f"presenter_{safe_pid}.c").write_text(pres_c, encoding="utf-8", newline="\n")
        (pres_dir / f"presenter_{safe_pid}.h").write_text(pres_h, encoding="utf-8", newline="\n")
        generated_files.append(f"presenters/presenter_{safe_pid}.c")
        generated_files.append(f"presenters/presenter_{safe_pid}.h")

    # Models
    model_dir = out / "models"
    model_dir.mkdir(parents=True, exist_ok=True)
    for model in models:
        mname = model.get("name", "")
        m_c = generate_model_c(mname, model.get("fields", []))
        m_h = generate_model_h(mname, model.get("fields", []))
        safe_mname = safe_c_identifier(mname)
        (model_dir / f"model_{safe_mname}.c").write_text(m_c, encoding="utf-8", newline="\n")
        (model_dir / f"model_{safe_mname}.h").write_text(m_h, encoding="utf-8", newline="\n")
        generated_files.append(f"models/model_{safe_mname}.c")
        generated_files.append(f"models/model_{safe_mname}.h")

    # CMake source list
    cmake_sources = generated_files + [
        f"pages/{page.get('id', '')}/ui_{safe_c_identifier(page.get('id', ''))}.c"
        for page in pages
    ]
    cmake_path = out / "ui_app_sources.cmake"
    cmake_lines = [f"# Auto-generated CMake source list for {app_id}", "set(UI_APP_SOURCES"]
    cmake_lines.extend(f"    \"{s}\"" for s in cmake_sources)
    cmake_lines.append(")")
    cmake_path.write_text("\n".join(cmake_lines) + "\n", encoding="utf-8", newline="\n")

    # ── App-level validation ──
    from mcp.app_validator import validate_app
    generated_content: dict[str, str] = {}
    for rel_path in generated_files:
        abs_path = out / rel_path
        if abs_path.is_file():
            try:
                generated_content[rel_path] = abs_path.read_text(encoding="utf-8")
            except OSError:
                pass

    app_validation = validate_app(resolved, generated_content)
    app_validation_result = _json_safe_value(app_validation)
    if not all_ok:
        status = "needs_manual_work"
    elif app_validation["status"] != "verified":
        status = app_validation["status"]
    # else keep status = "verified"

    # Build and write app-level evidence
    app_evidence = {
        "app_id": app_id,
        "schema_version": "2.0",
        "status": status,
        "page_count": len(page_results),
        "pages_ok": sum(1 for r in page_results if r.get("ok")),
        "pages_failed": sum(1 for r in page_results if not r.get("ok")),
        "route_count": len(resolved.get("routes", [])),
        "model_count": len(resolved.get("models", [])),
        "page_results": page_results,
        "validation": app_validation_result,
    }
    evidence_path = out / "app_evidence.json"
    evidence_path.write_text(
        json.dumps(app_evidence, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8", newline="\n",
    )

    if page_errors:
        return _fail(
            page_errors,
            stage="app_mvp",
            status=status,
            app_evidence_path=str(evidence_path),
            resolved_manifest_path=str(resolved_path),
            page_results=page_results,
            generated_files=generated_files,
            app_validation=app_validation_result,
            warnings=validation.get("warnings", []),
        )

    return _ok({
        "stage": "app_mvp",
        "status": status,
        "app_id": app_id,
        "app_evidence_path": str(evidence_path),
        "resolved_manifest_path": str(resolved_path),
        "cmake_path": str(cmake_path),
        "page_results": page_results,
        "generated_files": generated_files,
        "app_validation": app_validation_result,
        "warnings": validation.get("warnings", []),
    })


def _generate_app_v21(
    manifest_path: str,
    manifest: dict[str, Any],
    args: dict[str, Any],
    validation: dict[str, Any],
) -> dict[str, Any]:
    """Generate a v2.1 app with one independently auditable artifact per state."""
    from mcp.manifest_v2 import resolve_manifest
    from mcp.app_v21_codegen import (
        generate_app_c, generate_app_h, generate_presenter_c, generate_presenter_h,
        generate_router_c, generate_router_h,
    )
    from mcp.app_codegen import generate_model_c, generate_model_h
    from mcp.lvgl_codegen import safe_c_identifier
    from mcp.app_validator import validate_app

    resolved = resolve_manifest(manifest)
    app_id = resolved["app"]["id"]
    root = Path(manifest_path).resolve().parent
    out = _safe_output_dir(args.get("output_dir", f"artifacts/ui_app/{app_id}"))
    app_dir = out / "app"
    app_dir.mkdir(parents=True, exist_ok=True)
    (app_dir / "ui_app_manifest_resolved.json").write_text(
        json.dumps(resolved, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )

    page_results: list[dict[str, Any]] = []
    generated_files: list[str] = []
    errors: list[str] = []
    display = resolved["display"]
    for page in resolved["pages"]:
        page_id = page["id"]
        page_dir = out / "pages" / page_id
        state_results: list[dict[str, Any]] = []
        for state_id, state in page["states"].items():
            state_dir = page_dir if state_id == "default" else page_dir / "states" / state_id
            design_path = root / state["design"]
            result = generate_ui({
                "design_path": str(design_path),
                "display": display,
                "lvgl_version": args.get("lvgl_version", "v9"),
                "output_dir": str(state_dir),
                "template": page.get("template", "auto"),
                "cut_dir": args.get("cut_dir", str(root)),
                "page_name": page_id,
                "screen_tap": True,
                # Manifest v2.1 has already bound every design state and
                # declared its resource inventory.  The state image is input
                # evidence for analysis only; it is never emitted as a
                # runtime image asset by the generic generator.
                "strict_asset_contract": False,
            })
            result["state_id"] = state_id
            state_results.append(result)
            if not result.get("ok"):
                errors.extend(f"{page_id}.{state_id}: {item}" for item in result.get("errors", []))
        default = next((item for item in state_results if item["state_id"] == "default"), {})
        if default.get("ok"):
            generated_files.extend([
                f"pages/{page_id}/ui_page_{safe_c_identifier(page_id)}.c",
                f"pages/{page_id}/ui_page_{safe_c_identifier(page_id)}.h",
            ])
        page_results.append({"page_id": page_id, "states": state_results, "ok": all(item.get("ok") for item in state_results)})

    pages, routes, models = resolved["pages"], resolved.get("routes", []), resolved.get("models", [])
    max_depth = resolved["app"].get("navigation", {}).get("max_depth", 8)
    router_h = generate_router_h(pages, max_depth)
    router_c = generate_router_c(pages)
    app_h = generate_app_h()
    app_c = generate_app_c(resolved["app"]["entry_page"], models)
    for name, content in {
        "ui_router.h": router_h, "ui_router.c": router_c, "ui_app.h": app_h, "ui_app.c": app_c,
    }.items():
        (app_dir / name).write_text(content, encoding="utf-8", newline="\n")
        generated_files.append(f"app/{name}")

    presenter_dir = out / "presenters"; presenter_dir.mkdir(parents=True, exist_ok=True)
    for page in pages:
        pid = safe_c_identifier(page["id"])
        for suffix, content in {
            ".h": generate_presenter_h(pid),
            ".c": generate_presenter_c(page, routes, models),
        }.items():
            name = f"presenter_{pid}{suffix}"
            (presenter_dir / name).write_text(content, encoding="utf-8", newline="\n")
            generated_files.append(f"presenters/{name}")

    model_dir = out / "models"; model_dir.mkdir(parents=True, exist_ok=True)
    for model in models:
        name = safe_c_identifier(model["name"])
        for suffix, content in {
            ".h": generate_model_h(model["name"], model["fields"]),
            ".c": generate_model_c(model["name"], model["fields"]),
        }.items():
            filename = f"model_{name}{suffix}"
            (model_dir / filename).write_text(content, encoding="utf-8", newline="\n")
            generated_files.append(f"models/{filename}")

    cmake_lines = ["# Auto-generated v2.1 app source list", "set(UI_APP_SOURCES"]
    cmake_lines.extend(f'    "{path}"' for path in generated_files if path.endswith(".c"))
    cmake_lines.append(")")
    cmake_path = out / "ui_app_sources.cmake"
    cmake_path.write_text("\n".join(cmake_lines) + "\n", encoding="utf-8", newline="\n")

    missing = [path for path in generated_files if not (out / path).is_file()]
    generated_content = {path: (out / path).read_text(encoding="utf-8") for path in generated_files if (out / path).is_file()}
    app_validation = validate_app(resolved, generated_content)
    app_validation_result = _json_safe_value(app_validation)
    manual_required = [
        "native_app_compile_pending_ci",
        "native_state_render_pending_ci",
        "flow_execution_pending_ci",
    ]
    if missing:
        errors.extend(f"generated file missing: {path}" for path in missing)
    status = "needs_manual_work" if not errors else "invalid"
    evidence = {
        "app_id": app_id, "schema_version": "2.1", "status": status,
        "authoritative": False, "manual_required": manual_required,
        "page_results": page_results, "validation": app_validation_result,
        "generated_files": generated_files,
        "file_hashes": {path: _file_hash(out / path) for path in generated_files if (out / path).is_file()},
        "next_gate": "native_app_compile_and_flow",
    }
    evidence_path = out / "app_evidence.json"
    evidence_path.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2, default=_json_evidence_value) + "\n",
        encoding="utf-8", newline="\n",
    )
    if errors:
        return _fail(errors, stage="app_mvp", status=status, app_evidence_path=str(evidence_path), page_results=page_results)
    return _ok({
        "stage": "app_mvp", "status": status, "app_id": app_id,
        "app_evidence_path": str(evidence_path), "cmake_path": str(cmake_path),
        "page_results": page_results, "generated_files": generated_files,
        "app_validation": app_validation_result, "warnings": validation.get("warnings", []),
    })


def _json_evidence_value(value: Any) -> list[Any]:
    """Encode validator sets deterministically in generated evidence."""
    if isinstance(value, set):
        return sorted(value)
    raise TypeError(f"unsupported evidence value: {type(value).__name__}")


def _json_safe_value(value: Any) -> Any:
    """Normalize tool responses to values that JSON-RPC can serialize."""
    return json.loads(json.dumps(value, ensure_ascii=False, default=_json_evidence_value))


def _analysis_to_spec(report: dict[str, Any], args: dict[str, Any]) -> dict[str, Any]:
    """Convert inspection result to UI Spec v2."""
    display = args.get("display", {})
    nodes: list[dict[str, Any]] = [{
        "id": "root",
        "type": "screen",
        "full_screen_tap": bool(args.get("screen_tap", False)),
    }]
    for index, region in enumerate(report.get("detected_regions", [])):
        if not isinstance(region, dict):
            continue
        bbox = region.get("bbox", [])
        if not isinstance(bbox, list) or len(bbox) != 4 or not all(isinstance(value, int) for value in bbox):
            continue
        region_type = str(region.get("type", "container"))
        node_type = region_type if region_type in {"container", "label", "button", "image", "bar"} else "container"
        nodes.append({
            "id": str(region.get("id", f"region_{index}")),
            "type": node_type,
            "parent_id": "root",
            "source_bbox": bbox,
            "confidence": region.get("confidence", 0.0),
        })
    return {
        "schema_version": "2.0",
        "page_name": str(args.get("page_name", "page")),
        "display": {
            "width": display.get("width", 480),
            "height": display.get("height", 800),
        },
        "lvgl_version": args.get("lvgl_version", "v9"),
        "nodes": nodes,
    }


def _should_use_interactive_scene(template: str, args: dict[str, Any]) -> bool:
    if template == "interactive_scene":
        return True
    if template != "auto":
        return False
    cut_dir = args.get("cut_dir")
    if not cut_dir:
        return False
    try:
        names = {path.stem.lower() for path in Path(str(cut_dir)).rglob("*") if path.is_file()}
    except OSError:
        return False
    has_pet = bool({"initial_page_pet", "pet_idle"} & names)
    mood_sets = (
        {"mood_calmness", "mood_good", "mood_down", "mood_stressed"},
        {"calmness", "good", "down", "stressed"},
    )
    return has_pet and any(mood_set.issubset(names) for mood_set in mood_sets)


def _find_scene_asset(asset_root: Path, candidates: tuple[str, ...]) -> Path | None:
    """Resolve a named scene asset from either the legacy flat or organized tree."""
    wanted = {name.casefold(): index for index, name in enumerate(candidates)}
    matches: list[tuple[int, str, Path]] = []
    try:
        for path in asset_root.rglob("*"):
            if path.is_file() and path.name.casefold() in wanted:
                matches.append((wanted[path.name.casefold()], path.as_posix().casefold(), path))
    except OSError:
        return None
    return min(matches)[2] if matches else None


def _scene_bbox(summary: dict[str, Any], name: str, fallback: list[int]) -> list[int]:
    value = summary.get("key_bboxes", {}).get(name, fallback)
    if isinstance(value, list) and len(value) == 4 and all(isinstance(item, int) for item in value):
        return value
    return fallback


_FONT_SYMBOL_RE = re.compile(r"\b(?:const\s+)?lv_font_t\s+([A-Za-z_]\w*)\s*=")


def _resolve_manifest_fonts(
    cut_dir: Path,
    design_path: Path | None,
    *,
    page_name: str = "",
    template: str = "",
) -> tuple[list[dict[str, str]], list[str]]:
    """Resolve declared UI fonts and their LVGL symbols from ui/manifest.json."""
    manifest_path = cut_dir / "manifest.json"
    if not manifest_path.is_file():
        return [], ["No ui/manifest.json font mapping found; generated C uses integrator-provided UI_FONT_* overrides or LVGL defaults."]
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read {manifest_path.name}: {exc}") from exc
    pages = manifest.get("pages")
    if not isinstance(pages, list):
        raise ValueError("ui/manifest.json must contain a pages array")

    selected: dict[str, Any] | None = None
    for page in pages:
        if not isinstance(page, dict):
            continue
        raw_design = page.get("design")
        if design_path is not None and isinstance(raw_design, str) and (cut_dir / raw_design).resolve() == design_path:
            selected = page
            break
    if selected is None:
        selected = next((page for page in pages if isinstance(page, dict) and page_name and page.get("id") == page_name), None)
    if selected is None and template and template != "auto":
        selected = next((page for page in pages if isinstance(page, dict) and page.get("template") == template), None)
    if selected is None or not selected.get("fonts"):
        return [], ["The selected manifest page does not declare fonts; generated C uses integrator-provided UI_FONT_* overrides or LVGL defaults."]

    raw_fonts = selected["fonts"]
    if not isinstance(raw_fonts, dict):
        raise ValueError("manifest page fonts must be an object with title, body, and caption entries")
    role_map = (("title", "title"), ("body", "body"), ("caption", "caption"))
    resolved: list[dict[str, str]] = []
    for usage, role in role_map:
        raw_font = raw_fonts.get(role)
        if isinstance(raw_font, str):
            raw_path = raw_font
            raw_preview_bin = ""
        elif isinstance(raw_font, dict):
            raw_path = raw_font.get("source", raw_font.get("c", ""))
            raw_preview_bin = raw_font.get("preview_bin", "")
        else:
            raw_path = ""
            raw_preview_bin = ""
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise ValueError(f"manifest page fonts.{role} is required when fonts are declared")
        source = (cut_dir / raw_path).resolve()
        if not source.is_relative_to(cut_dir) or not source.is_file():
            raise ValueError(f"manifest page fonts.{role} is missing or outside ui/: {raw_path}")
        match = _FONT_SYMBOL_RE.search(source.read_text(encoding="utf-8", errors="ignore"))
        if not match:
            raise ValueError(f"cannot find an lv_font_t symbol in manifest page fonts.{role}: {raw_path}")
        entry = {"usage": usage, "role": role, "source": str(source), "symbol": match.group(1)}
        if raw_preview_bin:
            if not isinstance(raw_preview_bin, str):
                raise ValueError(f"manifest page fonts.{role}.preview_bin must be a path string")
            preview_bin = (cut_dir / raw_preview_bin).resolve()
            if not preview_bin.is_relative_to(cut_dir) or not preview_bin.is_file():
                raise ValueError(f"manifest page fonts.{role}.preview_bin is missing or outside ui/: {raw_preview_bin}")
            entry["preview_bin"] = str(preview_bin)
        resolved.append(entry)
    return resolved, []


def _write_user_font_bundle(output_dir: Path, fonts: list[dict[str, str]], page_name: str) -> dict[str, str]:
    """Copy manifest fonts and emit declarations plus a build-source list."""
    fonts_dir = output_dir / "fonts"
    fonts_dir.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for font in fonts:
        source = Path(font["source"])
        destination = fonts_dir / source.name
        shutil.copy2(source, destination)
        font["output_source"] = str(destination)
        copied.append(destination.as_posix())

    safe_page = re.sub(r"[^A-Za-z0-9_]", "_", page_name).strip("_").lower() or "page"
    macro_page = re.sub(r"[^A-Za-z0-9_]", "_", page_name).strip("_").upper() or "PAGE"
    header = output_dir / f"ui_{safe_page}_fonts.h"
    unique_symbols = list(dict.fromkeys(font["symbol"] for font in fonts))
    declarations = "\n".join(f"extern const lv_font_t {symbol};" for symbol in unique_symbols)
    header.write_text(
        f"#ifndef UI_{macro_page}_FONTS_H\n#define UI_{macro_page}_FONTS_H\n\n"
        "#include \"lvgl.h\"\n\n"
        f"{declarations}\n\n#endif /* UI_{macro_page}_FONTS_H */\n",
        encoding="utf-8", newline="\n",
    )
    cmake = output_dir / f"ui_{safe_page}_fonts.cmake"
    lines = [f"# Add these sources to the target that builds ui_{safe_page}.c.", f"set(UI_{macro_page}_FONT_SOURCES"]
    lines.extend(f'    "{Path(path).as_posix()}"' for path in copied)
    lines.append(")")
    cmake.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return {"header": header.name, "header_path": str(header), "cmake_path": str(cmake)}


def _apply_manifest_fonts_to_spec(spec: dict[str, Any], fonts: list[dict[str, str]], bundle: dict[str, str]) -> None:
    """Attach font provenance and deterministic role-based references to a UI Spec."""
    by_role = {font["role"]: font for font in fonts}
    for node in spec.get("nodes", []):
        if not isinstance(node, dict) or node.get("type") not in {"label", "button", "checkbox", "dropdown"}:
            continue
        styles = node.setdefault("styles", {})
        if not isinstance(styles, dict) or styles.get("font"):
            continue
        node_id = str(node.get("id", "")).casefold()
        requested_role = str(styles.get("font_role", "")).casefold()
        if requested_role not in by_role:
            if any(token in node_id for token in ("title", "header", "top", "heading")):
                requested_role = "title"
            elif any(token in node_id for token in ("caption", "hint", "subtitle", "footnote")):
                requested_role = "caption"
            else:
                requested_role = "body"
        selected = by_role.get(requested_role, by_role["body"])
        styles["font"] = f"&{selected['symbol']}"
        styles["font_role"] = requested_role
        styles["font_id"] = selected["symbol"]
    spec["fonts"] = fonts
    spec["font_bundle"] = bundle


def _native_font_bindings(spec: dict[str, Any]) -> tuple[dict[str, str], list[str]]:
    """Resolve official LVGL .bin fonts required by a native render."""
    requested: set[str] = set()
    for node in spec.get("nodes", []):
        if not isinstance(node, dict):
            continue
        styles = node.get("styles", {})
        if not isinstance(styles, dict):
            continue
        value = styles.get("font_id", styles.get("font", ""))
        if isinstance(value, str) and value.strip():
            requested.add(value.strip().lstrip("&"))
    if not requested:
        return {}, []

    available: dict[str, str] = {}
    for font in spec.get("fonts", []):
        if not isinstance(font, dict):
            continue
        symbol = font.get("symbol")
        preview_bin = font.get("preview_bin")
        if isinstance(symbol, str) and isinstance(preview_bin, str) and Path(preview_bin).is_file():
            available[symbol] = preview_bin
    return {font_id: available[font_id] for font_id in requested if font_id in available}, sorted(requested - available.keys())


def _generate_interactive_scene_v2(args: dict[str, Any]) -> dict[str, Any]:
    """Adapt the semantic interactive-scene generator to UI Spec v2 + asset.pack."""
    from mcp.interactive_scene_auto import generate_interactive_scene_page
    from mcp.lvgl_ir.asset_pack import encode_pack, generate_manifest, pack_asset

    design_path = Path(str(args["design_path"])).resolve()
    cut_dir = Path(str(args.get("cut_dir") or design_path.parent)).resolve()
    out = _safe_output_dir(str(args.get("output_dir", "artifacts/generated")))
    display = args.get("display", {})
    width = int(display.get("width", 480))
    height = int(display.get("height", 800))
    try:
        manifest_fonts, font_warnings = _resolve_manifest_fonts(
            cut_dir, design_path, page_name="interactive_scene", template="interactive_scene"
        )
    except ValueError as exc:
        return _fail([str(exc)], stage="fonts", status="font_config_invalid")
    font_header = ""
    font_cmake_path = ""
    if manifest_fonts:
        font_bundle = _write_user_font_bundle(out, manifest_fonts, "interactive_scene")
        font_header = font_bundle["header"]
        font_cmake_path = font_bundle["cmake_path"]
    font_macros = {
        "top": f"&{next(font['symbol'] for font in manifest_fonts if font['role'] == 'title')}",
        "title": f"&{next(font['symbol'] for font in manifest_fonts if font['role'] == 'body')}",
        "hint": f"&{next(font['symbol'] for font in manifest_fonts if font['role'] == 'caption')}",
    } if manifest_fonts else {}
    mood_keys = ("calmness", "good", "down", "stressed")
    mood_paths = {
        key: _find_scene_asset(cut_dir, (f"mood_{key}.png", f"{key}.png"))
        for key in mood_keys
    }
    # Prefer the state-matched background when it is supplied.  `home_bg.jpg`
    # belongs to a different scene state in the interactive-scene cutout set,
    # while `Affirmation-bg.png` is the compositing background for the
    # affirmative/favorited design.  Keep the former as a backwards-compatible
    # fallback for older cutout bundles.
    background = _find_scene_asset(cut_dir, (
        "affirmation_favorited.png",
        "Affirmation-bg.png",
        "affirmation-bg.png",
        "home_default.jpg",
        "home_bg.jpg",
    ))
    pet = _find_scene_asset(cut_dir, ("pet_idle.png", "initial_page_pet.png"))
    required_assets = (background, pet, *mood_paths.values())
    missing = [
        "scene background" if index == 0 else "pet" if index == 1 else f"mood_{mood_keys[index - 2]}"
        for index, path in enumerate(required_assets) if path is None
    ]
    if missing:
        return _fail([f"interactive_scene requires cutouts: {', '.join(missing)}"], stage="assets", status="missing_assets")

    try:
        generated = generate_interactive_scene_page({
            "design_dir": str(cut_dir),
            "design_path": str(design_path),
            "background_path": str(background),
            "pet_path": str(pet),
            "mood_order": list(mood_keys),
            "mood_paths": {key: str(path) for key, path in mood_paths.items()},
            "output_dir": str(out),
            "page_name": "interactive_scene",
            "width": width,
            "height": height,
            "lvgl_version": args.get("lvgl_version", "v9"),
            "allow_preflight_warnings": True,
            "font_header": font_header,
            "font_macro_exprs": font_macros,
            "return_mode": "compact",
        })
    except Exception as exc:
        return _fail([f"interactive_scene generation failed: {exc}"], stage="generate")
    if not generated.get("ok"):
        return _fail(["interactive_scene code generation failed"], stage="generate", details=generated)

    symbols = {
        "SCENE_BG": background,
        "SCENE_PET": pet,
        **{f"MOOD_{key.upper()}": path for key, path in mood_paths.items()},
    }
    packed = [pack_asset(path, symbol, "AUTO") for symbol, path in symbols.items()]
    failures = [asset.get("error", asset.get("symbol", "unknown")) for asset in packed if not asset.get("ok")]
    if failures:
        return _fail([f"asset.pack conversion failed: {', '.join(str(item) for item in failures)}"], stage="assets")
    asset_pack_path = out / "asset.pack"
    asset_pack_path.write_bytes(encode_pack(packed))
    generate_manifest(packed, out)

    summary = generated.get("summary", {})
    pet_box = _scene_bbox(summary, "pet", [95, 123, 305, 428])
    panel_box = _scene_bbox(summary, "glass_panel", [40, 534, 400, 180])
    title_box = _scene_bbox(summary, "title", [94, 537, 294, 38])
    hint_box = _scene_bbox(summary, "hint", [184, 583, 112, 36])
    favorite_box = _scene_bbox(summary, "favorite", [28, 18, 40, 40])
    nodes: list[dict[str, Any]] = [
        {"id": "root", "type": "screen", "styles": {"bg_color": "#718049"}},
        {"id": "background", "type": "image", "parent_id": "root", "src": "SCENE_BG", "source_bbox": [0, 0, width, height]},
        {"id": "pet", "type": "image", "parent_id": "root", "src": "SCENE_PET", "source_bbox": pet_box},
        {"id": "favorite_button", "type": "button", "parent_id": "root", "source_bbox": favorite_box, "styles": {"bg_color": "#FFFFFF", "radius": 20}},
        {"id": "favorite_icon", "type": "label", "parent_id": "root", "text": "*", "source_bbox": favorite_box, "styles": {"text_color": "#D8A500"}},
        {"id": "top_prompt", "type": "label", "parent_id": "root", "text": "I am completely\\nforgiven-past,\\npresent, future", "source_bbox": [78, 140, 324, 134], "styles": {"text_color": "#FFFFFF", **({"font": font_macros["top"]} if font_macros else {})}},
        {"id": "mood_panel", "type": "container", "parent_id": "root", "source_bbox": panel_box, "styles": {"bg_color": "#E4E2C7", "bg_opa": 96, "border_color": "#FFFFFF", "border_width": 1, "radius": 28}},
        {"id": "mood_title", "type": "label", "parent_id": "root", "text": "How's your mood", "source_bbox": title_box, "styles": {"text_color": "#FFFFFF", **({"font": font_macros["title"]} if font_macros else {})}},
        {"id": "mood_hint", "type": "label", "parent_id": "root", "text": "today?", "source_bbox": hint_box, "styles": {"text_color": "#FFFFFF", **({"font": font_macros["hint"]} if font_macros else {})}},
    ]
    mood_boxes = summary.get("key_bboxes", {}).get("mood_buttons", {})
    mood_icons = summary.get("key_bboxes", {}).get("mood_icons", {})
    for index, key in enumerate(mood_keys):
        button_box = mood_boxes.get(key, [64 + index * 94, 636, 70, 70]) if isinstance(mood_boxes, dict) else [64 + index * 94, 636, 70, 70]
        icon_box = mood_icons.get(key, [80 + index * 94, 652, 37, 37]) if isinstance(mood_icons, dict) else [80 + index * 94, 652, 37, 37]
        button_id = f"mood_{key}_button"
        nodes.extend([
            {"id": button_id, "type": "button", "parent_id": "root", "source_bbox": button_box, "styles": {"bg_color": "#FFFFFF", "radius": 35}},
            # source_bbox is expressed in screen coordinates, so the icon is
            # a root-level overlay rather than a button child (which would
            # apply the button position a second time in LVGL).
            {"id": f"mood_{key}_icon", "type": "image", "parent_id": "root", "src": f"MOOD_{key.upper()}", "source_bbox": icon_box},
        ])

    spec = {
        "schema_version": "2.0",
        "page_name": "interactive_scene",
        "display": {"width": width, "height": height, "color_depth": 16},
        "lvgl_version": "v9",
        "assets": [{"symbol": symbol, "source": str(path)} for symbol, path in symbols.items()],
        "fonts": manifest_fonts,
        "nodes": nodes,
        "events": [{"node_id": "favorite_button", "event_type": "clicked"}, *[{"node_id": f"mood_{key}_button", "event_type": "clicked"} for key in mood_keys]],
        "metadata": {
            "template": "interactive_scene",
            "source_generator": "interactive_scene_auto",
            "font_policy": "manifest_required_when_declared",
            "native_preview_font_support": "not_available_for_external_lvgl_c_fonts" if manifest_fonts else "default_or_integrator_override",
        },
    }
    spec_path = out / "ui_spec.json"
    spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return _ok({
        "stage": "generate",
        "template": "interactive_scene",
        "c_path": str(out / "ui_interactive_scene.c"),
        "h_path": str(out / "ui_interactive_scene.h"),
        "spec_path": str(spec_path),
        "asset_pack_path": str(asset_pack_path),
        "node_count": len(nodes),
        "font_sources": [font.get("output_source") or font.get("source") for font in manifest_fonts],
        "font_cmake_path": font_cmake_path,
        "warnings": [*font_warnings, *generated.get("summary", {}).get("warnings", [])],
    })


# ── Tool registry ─────────────────────────────────────────────────

HIGH_LEVEL_TOOLS: dict[str, Any] = {
    "inspect_design": inspect_design,
    "generate_ui": generate_ui,
    "render_ui": render_ui,
    "compare_ui": compare_ui,
    "refine_ui": refine_ui,
    "apply_patch": apply_patch,
}
