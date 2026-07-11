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
    template = str(args.get("template", "auto"))

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


# ── render_ui ─────────────────────────────────────────────────────


def render_ui(args: dict[str, Any]) -> dict[str, Any]:
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

        response = {
            "stage": "render",
            "engine": engine,
            "authoritative": True,
            "render_path": result.get("render_png", str(out / "render.png")),
            "object_tree_path": result.get("tree", str(out / "object_tree.bin")),
            "object_tree_json_path": result.get("tree_json"),
            "status": render_status,
            "platform": runner["platform"],
            "lvgl_version": lvgl_version,
        }
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
        validation_result = validate_directory(str(Path(spec_path).parent) if spec_path else ".", "v9")

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

    profile = args.get("threshold_profile", "golden_strict")
    result = compare(actual_path, baseline_path, spec, profile=profile)

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


def _analysis_to_spec(report: dict[str, Any], args: dict[str, Any]) -> dict[str, Any]:
    """Convert inspection result to UI Spec v2."""
    display = args.get("display", {})
    nodes: list[dict[str, Any]] = [{"id": "root", "type": "screen"}]
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
        "page_name": "page",
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
