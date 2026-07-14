"""Auto-discover a conventional ui/ directory and bind its cutouts."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from mcp.interactive_scene_auto import generate_interactive_scene_page
from mcp.asset_contract import DEFAULT_UI_FLASH_BYTES
from mcp.lvgl_ir.asset_pack import encode_pack, generate_manifest, list_pack_symbols, pack_asset, write_lvgl_v9_c_assets

_FONT_SYMBOL = re.compile(r"\b(?:const\s+)?lv_font_t\s+([A-Za-z_]\w*)\s*=")
_STATUS_VISIBLE_DEFAULTS = {
    "wifi": (297, 20, 31, 23),
    "bluetooth": (363, 18, 21, 29),
    "battery": (413, 23, 36, 18),
}


def _runtime_symbol(expression: str) -> str:
    """Convert the C image expression used by the page into a pack symbol."""
    return expression.strip().lstrip("&").strip()


def _build_render_spec_v2(
    scene_spec: dict[str, Any],
    *,
    status_layouts: dict[str, tuple[int, int, int, int]],
    status_symbols: dict[str, str],
    preview_fonts: list[dict[str, str]],
) -> dict[str, Any]:
    """Project the generated interactive-scene C layout into UI Spec v2.

    The private scene spec remains the source for page-specific runtime
    behavior.  This v2 document is limited to the static initial state that
    the native renderer can execute, and uses the same resolved coordinates,
    strings, image symbols, and styles as the generated C page.
    """
    display = scene_spec["display"]
    width, height = int(display["width"]), int(display["height"])
    components = {item["id"]: item for item in scene_spec["components"]}
    assets = {item["id"]: item for item in scene_spec["assets"]}
    fonts = scene_spec.get("fonts", {}).get("macro_expressions", {})

    def box(component_id: str) -> list[int]:
        component = components[component_id]
        x, y = component["pos"]
        w, h = component["size"]
        return [int(x), int(y), int(w), int(h)]

    def image_node(component_id: str, *, node_id: str | None = None) -> dict[str, Any]:
        asset = assets[component_id]
        return {
            "id": node_id or component_id,
            "type": "image",
            "parent_id": "root",
            "src": _runtime_symbol(str(asset["runtime_src"])),
            "source_bbox": box(component_id),
        }

    nodes: list[dict[str, Any]] = [
        {"id": "root", "type": "screen", "styles": {"bg_color": "#79A05F"}},
        image_node("background"),
        image_node("pet"),
        {
            "id": "top_prompt", "type": "label", "parent_id": "root",
            "text": str(scene_spec.get("copy", {}).get("top", "I am completely\nforgiven-past,\npresent, and")),
            "source_bbox": box("top_prompt"),
            "styles": {"text_color": "#FFFFFF", "text_align": "center", "font_id": _runtime_symbol(str(fonts.get("top", "font_40_bold")))},
        },
    ]
    if "interaction_panel_blur" in assets and "interaction_panel_blur" in components:
        nodes.append(image_node("interaction_panel_blur"))
    nodes.extend([
        {
            "id": "interaction_panel", "type": "container", "parent_id": "root",
            "source_bbox": box("interaction_panel"),
            "styles": {"bg_color": "#FFFFFF", "bg_opa": 61, "border_color": "#FFFFFF", "border_width": 1, "radius": int(components["interaction_panel"]["radius"])},
        },
        {
            "id": "title", "type": "label", "parent_id": "root",
            "text": str(scene_spec.get("copy", {}).get("title", "How's your mood")),
            "source_bbox": box("title"),
            "styles": {"text_color": "#FFFFFF", "text_align": "center", "font_id": _runtime_symbol(str(fonts.get("title", "font_36_bold")))},
        },
        {
            "id": "hint", "type": "label", "parent_id": "root",
            "text": str(scene_spec.get("copy", {}).get("hint", "today?")),
            "source_bbox": box("hint"),
            "styles": {"text_color": "#FFFFFF", "text_align": "center", "font_id": _runtime_symbol(str(fonts.get("hint", "font_36_bold")))},
        },
    ])
    events: list[dict[str, str]] = []
    for component in scene_spec["components"]:
        if component["type"] != "mood_button":
            continue
        mood_id = str(component["id"])
        button = component["button"]
        icon = component["icon"]
        button_id = f"{mood_id}_button"
        nodes.extend([
            {
                "id": button_id, "type": "button", "parent_id": "root",
                "source_bbox": [int(button["x"]), int(button["y"]), int(button["w"]), int(button["h"])],
                "styles": {"bg_color": "#FFFFFF", "bg_opa": 255, "border_width": 0, "radius": int(button["radius"])},
            },
            {
                "id": f"{mood_id}_icon", "type": "image", "parent_id": "root",
                "src": _runtime_symbol(str(assets[mood_id]["runtime_src"])),
                "source_bbox": [int(icon["x"]), int(icon["y"]), int(icon["w"]), int(icon["h"])],
            },
        ])
        events.append({"node_id": button_id, "event_type": "clicked"})
    for key, (x, y, w, h) in sorted(status_layouts.items()):
        symbol = status_symbols.get(key)
        if symbol:
            nodes.append({"id": f"status_{key}", "type": "image", "parent_id": "root", "src": symbol, "source_bbox": [x, y, w, h]})

    return {
        "schema_version": "2.0",
        "page_name": str(scene_spec["page_name"]),
        "display": {"width": width, "height": height, "color_depth": int(display.get("color_depth", 16))},
        "lvgl_version": str(scene_spec["lvgl_version"]),
        "assets": [{"symbol": item["symbol"], "source": item["path"]} for item in scene_spec.get("assets", []) if "symbol" in item and "path" in item],
        "fonts": preview_fonts,
        "nodes": nodes,
        "events": events,
        "metadata": {
            "source_generator": "interactive_scene_auto",
            "source_spec": "interactive-scene.v1",
            "render_state": "initial_static_state",
            "runtime_behavior": "mood selection and server-update handlers remain in generated C",
            "runtime_fonts": {key: _runtime_symbol(str(value)) for key, value in fonts.items()},
        },
    }


_FONT_ROLES = (
    ("top", "top", "top_prompt", 40),
    ("action", "action", "action", 36),
    ("title", "title", "title", 36),
    ("hint", "hint", "hint", 36),
)


def _select_ttf(root: Path, font_path: str | Path | None) -> Path | None:
    """Select an explicitly supplied TTF, or the package's primary TTF."""
    if font_path:
        candidate = Path(font_path).expanduser().resolve()
        if candidate.suffix.lower() not in {".ttf", ".otf"}:
            raise ValueError("font_path must reference a .ttf or .otf font")
        if not candidate.is_file():
            raise ValueError(f"font_path not found: {candidate}")
        return candidate
    fonts_dir = root / "fonts"
    for name in ("ui_font.ttf", "font.ttf"):
        candidate = fonts_dir / name
        if candidate.is_file():
            return candidate
    candidates = sorted(path for path in fonts_dir.glob("*.*tf") if path.is_file())
    return candidates[0] if candidates else None


def _font_subset_plan(scene_spec: dict[str, Any], source: Path) -> list[dict[str, Any]]:
    """Use analyzed text bounds to derive the smallest TTF subsets per role."""
    copy = scene_spec.get("copy", {}) if isinstance(scene_spec.get("copy"), dict) else {}
    analysis = scene_spec.get("analysis", {}) if isinstance(scene_spec.get("analysis"), dict) else {}
    analysis_text = analysis.get("text", {}) if isinstance(analysis.get("text"), dict) else {}
    role_sources = scene_spec.get("font_sources", {}) if isinstance(scene_spec.get("font_sources"), dict) else {}
    plan: list[dict[str, Any]] = []
    for role, copy_key, analysis_key, fallback_size in _FONT_ROLES:
        text = str(copy.get(copy_key, ""))
        if not text:
            continue
        measured = analysis_text.get(analysis_key, {})
        raw_size = measured.get("font", fallback_size) if isinstance(measured, dict) else fallback_size
        try:
            # Detection measures the visible glyph box, while lv_font_conv
            # expects an em size. Keep the template's role size as the lower
            # bound so a tight glyph bbox cannot shrink the runtime font.
            size = max(fallback_size, int(round(float(raw_size))))
        except (TypeError, ValueError):
            size = fallback_size
        plan.append({
            "role": role,
            "symbol": f"ui_font_{role}_{size}",
            "size_px": size,
            "text": text,
            "glyph_count": len(set(text)),
            "source": str(role_sources.get(role) or source),
        })
    return plan


def _generate_ttf_font_subsets(
    scene_spec: dict[str, Any],
    source: Path,
    output_dir: Path,
) -> tuple[list[tuple[str, Path]], list[dict[str, str]], list[dict[str, Any]], list[str]]:
    """Generate firmware C fonts and native `.bin` subsets with per-role sources."""
    from mcp.assets import find_lv_font_conv, unique_glyph_text

    converter = find_lv_font_conv()
    plan = _font_subset_plan(scene_spec, source)
    if not converter:
        return [], [], plan, ["TTF font generation unavailable: lv_font_conv is missing."]
    sources: list[tuple[str, Path]] = []
    previews: list[dict[str, str]] = []
    warnings: list[str] = []
    for item in plan:
        symbol, size = str(item["symbol"]), int(item["size_px"])
        item_source = Path(str(item["source"]))
        if not item_source.is_file():
            warnings.append(f"TTF font source not found for {symbol}: {item_source}")
            continue
        glyphs = unique_glyph_text(str(item["text"]))
        c_path = output_dir / f"{symbol}.c"
        bin_path = output_dir / f"{symbol}.bin"
        common = [converter, "--font", str(item_source), "--symbols", glyphs, "--size", str(size), "--bpp", "4", "--no-compress"]
        commands = (
            ("lvgl", c_path, [*common, "--format", "lvgl", "--lv-include", "lvgl.h", "--lv-font-name", symbol, "-o", str(c_path)]),
            ("bin", bin_path, [*common, "--format", "bin", "-o", str(bin_path)]),
        )
        failed = False
        for kind, path, command in commands:
            try:
                process = subprocess.run(command, capture_output=True, encoding="utf-8", errors="replace", timeout=120)
            except OSError as exc:
                warnings.append(f"TTF font generation failed for {symbol} ({kind}): {exc}")
                failed = True
                break
            if process.returncode != 0 or not path.is_file() or path.stat().st_size == 0:
                warnings.append(f"TTF font generation failed for {symbol} ({kind}): lv_font_conv failed")
                failed = True
                break
        if failed:
            c_path.unlink(missing_ok=True)
            bin_path.unlink(missing_ok=True)
            continue
        sources.append((symbol, c_path))
        previews.append({"symbol": symbol, "preview_bin": str(bin_path), "source": str(item_source)})
    return sources, previews, plan, warnings


def _write_font_bundle(output_dir: Path, font_sources: list[tuple[str, Path]]) -> tuple[Path, Path]:
    """Write the firmware declarations and CMake list for generated fonts."""
    font_header = output_dir / "ui_auto_fonts.h"
    font_header.write_text(
        "#ifndef UI_AUTO_FONTS_H\n#define UI_AUTO_FONTS_H\n#include \"lvgl.h\"\n\n"
        + "\n".join(f"LV_FONT_DECLARE({symbol});" for symbol, _ in font_sources)
        + "\n\n#endif\n",
        encoding="utf-8", newline="\n",
    )
    font_cmake = output_dir / "ui_auto_fonts.cmake"
    font_cmake.write_text(
        "set(UI_AUTO_FONT_SOURCES\n"
        + "\n".join(f'    "${{CMAKE_CURRENT_LIST_DIR}}/{path.name}"' for _, path in font_sources)
        + "\n)\n",
        encoding="utf-8", newline="\n",
    )
    return font_header, font_cmake


def _status_icon_layout(key: str, path: Path, resolved: dict[str, Any] | None = None) -> tuple[int, int, int, int]:
    """Keep status icon size equal to its source texture canvas."""
    from PIL import Image

    with Image.open(path) as image:
        width, height = image.size
        alpha_bbox = image.convert("RGBA").getchannel("A").getbbox() or (0, 0, width, height)
    default = _STATUS_VISIBLE_DEFAULTS.get(key, (0, 0, width, height))
    estimated = (resolved or {}).get("estimated_bbox") or default
    visible_x, visible_y = int(estimated[0]), int(estimated[1])
    return visible_x - int(alpha_bbox[0]), visible_y - int(alpha_bbox[1]), width, height


def _write_panel_blur_asset(
    output_dir: Path,
    background_path: Path,
    pet_path: Path,
    scene_spec: dict[str, Any],
    *,
    blur_radius: int = 18,
) -> Path:
    """Pre-render the frosted panel backdrop from runtime assets only."""
    from PIL import Image, ImageDraw, ImageFilter

    components = {item["id"]: item for item in scene_spec["components"]}
    display = scene_spec["display"]
    width, height = int(display["width"]), int(display["height"])
    panel = components["interaction_panel"]
    pet = components["pet"]
    panel_x, panel_y = (int(value) for value in panel["pos"])
    panel_w, panel_h = (int(value) for value in panel["size"])
    pet_x, pet_y = (int(value) for value in pet["pos"])
    pet_w, pet_h = (int(value) for value in pet["size"])

    with Image.open(background_path) as source:
        backdrop = source.convert("RGBA")
        if backdrop.size != (width, height):
            backdrop = backdrop.resize((width, height), Image.Resampling.LANCZOS)
    with Image.open(pet_path) as source:
        pet_layer = source.convert("RGBA")
        if pet_layer.size != (pet_w, pet_h):
            pet_layer = pet_layer.resize((pet_w, pet_h), Image.Resampling.LANCZOS)
    backdrop.alpha_composite(pet_layer, (pet_x, pet_y))

    crop = backdrop.crop((panel_x, panel_y, panel_x + panel_w, panel_y + panel_h))
    crop = crop.filter(ImageFilter.GaussianBlur(radius=max(0, int(blur_radius))))
    mask = Image.new("L", crop.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, max(0, panel_w - 1), max(0, panel_h - 1)),
        radius=max(0, int(panel.get("radius", 0))),
        fill=255,
    )
    crop.putalpha(mask)
    path = output_dir / "interaction_panel_blur.png"
    crop.save(path)
    return path


def _fresh_directory(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def _publish_final_delivery(
    delivery: Path,
    evidence: Path,
    *,
    page_c: Path,
    page_h: Path,
    firmware_assets: dict[str, Any],
    font_sources: list[tuple[str, Path]],
    font_header: Path,
) -> dict[str, Any]:
    """Atomically publish only compilable code and direct dependencies."""
    staging = delivery.parent / f".{delivery.name}_staging"
    _fresh_directory(staging)
    asset_sources = [Path(path) for path in firmware_assets["sources"]]
    generated_font_sources = [path for _, path in font_sources]
    required = [
        page_c, page_h, Path(firmware_assets["header"]),
        *asset_sources, *generated_font_sources, font_header,
    ]
    for source in required:
        if not source.is_file():
            raise FileNotFoundError(f"required delivery dependency missing: {source}")
        shutil.copy2(source, staging / source.name)
    aggregate = staging / "ui_generated.cmake"
    source_names = [page_c.name, *[path.name for path in asset_sources], *[path.name for path in generated_font_sources]]
    aggregate.write_text(
        "set(UI_GENERATED_SOURCES\n"
        + "".join(f"    \"${{CMAKE_CURRENT_LIST_DIR}}/{name}\"\n" for name in source_names)
        + ")\nset(UI_GENERATED_INCLUDE_DIR \"${CMAKE_CURRENT_LIST_DIR}\")\n",
        encoding="utf-8", newline="\n",
    )
    if delivery.exists():
        shutil.rmtree(delivery)
    staging.replace(delivery)
    files = sorted(str(path) for path in delivery.iterdir() if path.is_file())
    return {
        "delivery_dir": str(delivery),
        "evidence_dir": str(evidence),
        "files": files,
        "page_c": str(delivery / page_c.name),
        "page_h": str(delivery / page_h.name),
        "cmake": str(delivery / aggregate.name),
    }


def generate_standard_ui_package(
    ui_dir: str | Path,
    output_dir: str | Path,
    *,
    asset_manifest_path: str | Path | None = None,
    font_path: str | Path | None = None,
    strict_asset_contract: bool = True,
    final_only: bool = True,
    cleanup_intermediates: bool = True,
) -> dict[str, Any]:
    root, delivery = Path(ui_dir).resolve(), Path(output_dir).resolve()
    out = delivery.parent / f".{delivery.name}_evidence" if final_only else delivery
    if final_only:
        _fresh_directory(out)
    else:
        out.mkdir(parents=True, exist_ok=True)
    contract_mode = asset_manifest_path is not None
    design_images = sorted(path for path in (root / "design").glob("*") if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".bmp"})
    if not contract_mode and strict_asset_contract and design_images:
        return {
            "ok": False,
            "status": "manual_required",
            "errors": ["UI package contains a design reference; provide asset_manifest_path from inspect_design before generation"],
        }
    if contract_mode:
        from mcp.asset_contract import resolve_asset_contract

        resolution = resolve_asset_contract(asset_manifest_path, package_root=root, asset_root=root / "assets", output_dir=out)
        if not resolution.get("ok"):
            return resolution
        packed = resolution["packed_assets"]
        firmware_assets = resolution["firmware_assets"]
        resolved = resolution["resolved_assets"]
        assets = [(item["symbol"], root / item["source_path"]) for item in resolved]
        backgrounds = [root / item["source_path"] for item in resolved if item["type"] == "full_screen_background"]
        characters = [root / item["source_path"] for item in resolved if item["type"] == "transparent_character"]
        mood_items = [item for item in resolved if item["type"] == "control_icon" and item["symbol"].startswith("mood_")]
        moods = {item["symbol"].removeprefix("mood_"): root / item["source_path"] for item in mood_items}
        system_items = [item for item in resolved if item["type"] == "status_icon"]
        systems = {item["symbol"].removeprefix("icon_"): root / item["source_path"] for item in system_items}
        symbol_by_path = {str(root / item["source_path"]): item["symbol"] for item in resolved}
        initial_contract = json.loads(Path(asset_manifest_path).read_text(encoding="utf-8"))
        max_flash_bytes = int(initial_contract.get("limits", {}).get("max_flash_bytes", DEFAULT_UI_FLASH_BYTES))
        design_reference = Path(str(initial_contract["design_reference"]))
        design_path = design_reference if design_reference.is_absolute() else root / design_reference
        design_path = design_path.resolve()
        if not backgrounds or not characters or not moods:
            return {"ok": False, "status": "manual_required", "errors": ["interactive scene requires one resolved background, one character, and control_icon symbols named mood_*"], **{key: value for key, value in resolution.items() if key not in {"ok", "status"}}}
        asset_manifest = json.loads(Path(resolution["resolved_manifest"]).read_text(encoding="utf-8"))
        requested_font_symbols = {"font_40_bold", "font_36_bold"}
    else:
        backgrounds = sorted((root / "assets" / "backgrounds").glob("*"))
        characters = sorted((root / "assets" / "characters").glob("*"))
        mood_dir, system_dir = root / "assets" / "icons" / "mood", root / "assets" / "icons" / "system"
        required = {"calmness", "good", "down", "stressed"}
        moods = {name: mood_dir / f"{name}.png" for name in required}
        systems = {name.removeprefix("icon_"): path for path in system_dir.glob("icon_*.png") for name in [path.stem]}
        if not backgrounds or not characters or any(not path.is_file() for path in moods.values()):
            return {"ok": False, "errors": ["standard ui package needs backgrounds/, characters/, and four mood icons"]}
        assets = [("ui_bg", backgrounds[0]), ("ui_pet", characters[0])]
        assets += [(f"mood_{key}", moods[key]) for key in sorted(moods)]
        assets += [(f"icon_{key}", value) for key, value in sorted(systems.items())]
        # Compatibility mode has no design contract, so it remains explicitly
        # inferred and can never become verified.
        packed = [pack_asset(path, symbol, "AUTO", auto_crop=not symbol.startswith("icon_")) for symbol, path in assets]
        failures = [item.get("error", item.get("symbol", "unknown")) for item in packed if not item.get("ok")]
        if failures:
            return {"ok": False, "errors": [f"asset packing failed: {', '.join(map(str, failures))}"]}
        (out / "asset.pack").write_bytes(encode_pack(packed))
        asset_manifest = generate_manifest(packed, out)
        firmware_assets = write_lvgl_v9_c_assets(packed, out, stem="ui_auto_assets")
        symbol_by_path = {str(path): symbol for symbol, path in assets}
        design_path = None
        max_flash_bytes = DEFAULT_UI_FLASH_BYTES
        requested_font_symbols = {"font_40_bold", "font_20_bold", "font_14_regular"}
    header = Path(firmware_assets["header"])
    font_sources: list[tuple[str, Path]] = []
    for source in sorted((root / "fonts" / "lvgl").glob("*.c")):
        match = _FONT_SYMBOL.search(source.read_text(encoding="utf-8", errors="ignore"))
        if match and match.group(1) in requested_font_symbols:
            copied = out / source.name
            shutil.copy2(source, copied)
            font_sources.append((match.group(1), copied))
    font_header, font_cmake = _write_font_bundle(out, font_sources)
    available_fonts = {symbol for symbol, _ in font_sources}
    if contract_mode:
        font_exprs = {
            "top": "&font_40_bold" if "font_40_bold" in available_fonts else "LV_FONT_DEFAULT",
            "title": "&font_36_bold" if "font_36_bold" in available_fonts else "LV_FONT_DEFAULT",
            "hint": "&font_36_bold" if "font_36_bold" in available_fonts else "LV_FONT_DEFAULT",
        }
    else:
        font_exprs = {
            "top": "&font_40_bold" if "font_40_bold" in available_fonts else "LV_FONT_DEFAULT",
            "title": "&font_20_bold" if "font_20_bold" in available_fonts else "LV_FONT_DEFAULT",
            "hint": "&font_14_regular" if "font_14_regular" in available_fonts else "LV_FONT_DEFAULT",
        }
    args = {
        # No design screenshot was supplied.  This is a declared inference
        # mode; the background remains a runtime cutout and is never treated
        # as a reference image to crop.
        "design_dir": str(root), "design_path": str(design_path) if design_path else None,
        "background_path": str(backgrounds[0]),
        "pet_path": str(characters[0]), "mood_paths": {key: str(path) for key, path in moods.items()},
        "output_dir": str(out), "assets_dir": str(out), "page_name": "interactive_scene_auto",
        "width": 480, "height": 800, "lvgl_version": "v9", "skip_preflight": True, "inferred_layout": not contract_mode,
        "auto_analyze": contract_mode, "return_mode": "compact", "asset_header": header.name,
        "font_header": font_header.name, "font_macro_exprs": font_exprs,
        # Bundled LVGL fonts currently cover ASCII U+0020..U+007E; use the
        # supported apostrophe instead of design U+2019 to prevent tofu.
        "title_text": "How's your mood",
        "background_src": f"&{symbol_by_path[str(backgrounds[0])]}", "pet_src": f"&{symbol_by_path[str(characters[0])]}",
        "mood_src": {key: f"&{symbol_by_path[str(path)]}" for key, path in moods.items()},
    }
    result = generate_interactive_scene_page(args)
    if not result.get("ok"):
        return result
    scene_spec_path = out / "interactive_scene_auto_spec.json"
    scene_spec = json.loads(scene_spec_path.read_text(encoding="utf-8"))
    panel_blur_path = _write_panel_blur_asset(out, backgrounds[0], characters[0], scene_spec)
    panel_blur_symbol = "ui_interaction_panel_blur"
    panel_blur_packed = pack_asset(panel_blur_path, panel_blur_symbol, "RGB565A8", auto_crop=False)
    if not panel_blur_packed.get("ok"):
        return {"ok": False, "status": "asset_pack_failed", "errors": [str(panel_blur_packed.get("error", panel_blur_symbol))]}
    packed = [*packed, panel_blur_packed]
    assets.append((panel_blur_symbol, panel_blur_path))
    symbol_by_path[str(panel_blur_path)] = panel_blur_symbol
    (out / "asset.pack").write_bytes(encode_pack(packed))
    asset_manifest = generate_manifest(packed, out)
    firmware_assets = write_lvgl_v9_c_assets(packed, out, stem="ui_auto_assets")
    header = Path(firmware_assets["header"])
    args.update({
        "asset_header": header.name,
        "panel_blur_path": str(panel_blur_path),
        "panel_blur_src": f"&{panel_blur_symbol}",
    })
    result = generate_interactive_scene_page(args)
    if not result.get("ok"):
        return result
    scene_spec = json.loads(scene_spec_path.read_text(encoding="utf-8"))
    preview_fonts: list[dict[str, str]] = []
    preview_warnings: list[str] = []
    font_subset_plan: list[dict[str, Any]] = []
    ttf_subsets_active = False
    explicit_ttf = bool(font_path)
    try:
        ttf_source = _select_ttf(root, font_path)
    except ValueError as exc:
        return {"ok": False, "status": "font_config_invalid", "errors": [str(exc)]}
    if ttf_source:
        generated_sources, preview_fonts, font_subset_plan, preview_warnings = _generate_ttf_font_subsets(scene_spec, ttf_source, out)
        if font_subset_plan and len(generated_sources) == len(font_subset_plan):
            for _, stale_source in font_sources:
                stale_source.unlink(missing_ok=True)
            font_sources = generated_sources
            font_header, font_cmake = _write_font_bundle(out, font_sources)
            font_exprs = {str(item["role"]): f"&{item['symbol']}" for item in font_subset_plan}
            args["font_header"] = font_header.name
            args["font_macro_exprs"] = font_exprs
            result = generate_interactive_scene_page(args)
            if not result.get("ok"):
                return result
            ttf_subsets_active = True
        elif font_subset_plan:
            preview_warnings.append("TTF subsets were incomplete; retained the package's existing LVGL fonts.")
            if explicit_ttf:
                return {
                    "ok": False,
                    "status": "font_generation_failed",
                    "errors": preview_warnings,
                    "font_source": str(ttf_source),
                    "font_subset_active": False,
                }
    image_flash_bytes = sum(int(item.get("flash_bytes", 0)) for item in packed)
    font_flash_bytes = sum(
        Path(str(item["preview_bin"])).stat().st_size
        for item in preview_fonts
        if item.get("preview_bin") and Path(str(item["preview_bin"])).is_file()
    )
    total_flash_bytes = image_flash_bytes + font_flash_bytes
    flash_budget = {
        "image_bytes": image_flash_bytes,
        "font_bytes": font_flash_bytes,
        "used_bytes": total_flash_bytes,
        "max_bytes": max_flash_bytes,
        "passed": total_flash_bytes <= max_flash_bytes,
    }
    asset_manifest["flash_budget"] = flash_budget
    if not flash_budget["passed"]:
        return {
            "ok": False,
            "status": "manual_required",
            "errors": [f"UI Flash budget exceeded after derived assets: {total_flash_bytes} > {max_flash_bytes}"],
            "asset_manifest": asset_manifest,
            "flash_budget": flash_budget,
        }
    c_path = out / "ui_interactive_scene_auto.c"
    source = c_path.read_text(encoding="utf-8")
    # Replace the status approximations with the supplied image cutouts. A
    # missing cutout remains dynamic, preserving runtime behaviour.
    snippets = []
    status_layouts: dict[str, tuple[int, int, int, int]] = {}
    status_symbols: dict[str, str] = {}
    resolved_status = {item["symbol"].removeprefix("icon_"): item for item in system_items} if contract_mode else {}
    for key, path in sorted(systems.items()):
        symbol = f"icon_{key}"
        if any(name == symbol for name, _ in assets):
            x, y, w, h = _status_icon_layout(key, path, resolved_status.get(key))
            status_layouts[key] = (x, y, w, h)
            status_symbols[key] = symbol
            snippets.append(
                f"    lv_obj_t *system_{key} = lv_image_create(s_page);\n"
                f"    lv_image_set_src(system_{key}, &{symbol});\n"
                f"    lv_image_set_inner_align(system_{key}, LV_IMAGE_ALIGN_CENTER);\n"
                f"    /* LVGL_LAYOUT_EXCEPTION: status icon uses its source texture canvas without scaling. */\n"
                f"    lv_obj_set_pos(system_{key}, {x}, {y});\n"
                f"    lv_obj_set_size(system_{key}, {w}, {h});"
            )
    if snippets:
        source = re.sub(r"    lv_obj_t \*favorite =.*?(?=\n    s_top_prompt)", "\n\n".join(snippets), source, count=1, flags=re.DOTALL)
        c_path.write_text(source, encoding="utf-8", newline="\n")

    scene_spec = json.loads(scene_spec_path.read_text(encoding="utf-8"))
    render_spec = _build_render_spec_v2(
        scene_spec,
        status_layouts=status_layouts,
        status_symbols=status_symbols,
        preview_fonts=preview_fonts,
    )
    render_spec["assets"] = [{"symbol": symbol, "source": str(path)} for symbol, path in assets]
    if ttf_subsets_active:
        render_spec["metadata"]["font_subset"] = {"source": str(ttf_source), "roles": font_subset_plan}
    render_spec_path = out / "ui_spec.json"
    render_spec_path.write_text(json.dumps(render_spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    from mcp.lvgl_ir.spec_validator import validate_spec
    render_validation = validate_spec(render_spec, asset_pack_path=str(out / "asset.pack"), expected_lvgl_version="v9")
    if not render_validation["valid"]:
        return {"ok": False, "status": "render_spec_invalid", "errors": render_validation["errors"]}
    contract = {
        "mode": "asset_intent_contract" if contract_mode else "standard_directory_autodiscovery",
        "visual_mode": "asset_contract_ready" if contract_mode else "inferred_without_design",
        "design_reference_policy": "design-reference-not-runtime-v1", "runtime_asset_pack": "asset.pack",
        "firmware_asset_header": header.name, "firmware_asset_sources": [Path(path).name for path in firmware_assets["sources"]],
        "firmware_asset_cmake": Path(firmware_assets["cmake"]).name, "symbols": [symbol for symbol, _ in assets],
        "alpha_trimmed_cutouts": {item["symbol"]: item["crop_offset"] for item in packed},
        "source_root": str(root), "status_cutouts": sorted(systems),
        "font_sources": [path.name for _, path in font_sources],
    }
    (out / "auto_discovery_report.json").write_text(json.dumps(contract, indent=2) + "\n", encoding="utf-8")
    declared = set(contract["symbols"])
    defined = set(firmware_assets["symbols"])
    source_names = sorted(Path(path).name for path in firmware_assets["sources"])
    cmake_text = Path(firmware_assets["cmake"]).read_text(encoding="utf-8")
    cmake_sources = sorted(name for name in source_names if name in cmake_text)
    pack_symbols = sorted(list_pack_symbols(out / "asset.pack"))
    closure = {
        "ok": declared == defined and sorted(declared) == pack_symbols and source_names == cmake_sources,
        "declared_symbols": sorted(declared),
        "defined_symbols": sorted(defined),
        "missing_definitions": sorted(declared - defined),
        "unexpected_definitions": sorted(defined - declared),
        "firmware_sources": firmware_assets["sources"],
        "cmake": firmware_assets["cmake"],
        "simulator_asset_pack": str(out / "asset.pack"),
        "pack_symbols": pack_symbols,
        "source_files": source_names,
        "cmake_sources": cmake_sources,
        "missing_cmake_sources": sorted(set(source_names) - set(cmake_sources)),
    }
    (out / "resource_closure_report.json").write_text(json.dumps(closure, indent=2) + "\n", encoding="utf-8")
    delivery_result = None
    if final_only and closure["ok"]:
        delivery_result = _publish_final_delivery(
            delivery, out, page_c=c_path, page_h=out / "ui_interactive_scene_auto.h",
            firmware_assets=firmware_assets, font_sources=font_sources,
            font_header=font_header,
        )
        delivered_firmware = {
            **firmware_assets,
            "header": str(delivery / Path(firmware_assets["header"]).name),
            "sources": [str(delivery / Path(path).name) for path in firmware_assets["sources"]],
            "cmake": delivery_result["cmake"],
        }
        if cleanup_intermediates:
            shutil.rmtree(out)
    else:
        delivered_firmware = firmware_assets
    evidence_removed = bool(final_only and cleanup_intermediates and delivery_result)
    return {
        "ok": closure["ok"], "status": "asset_contract_ready" if contract_mode else "inferred_without_design",
        "output_dir": str(delivery if final_only else out),
        "evidence_dir": None if evidence_removed else str(out),
        "evidence_removed": evidence_removed,
        "c_path": delivery_result["page_c"] if delivery_result else str(c_path),
        "h_path": delivery_result["page_h"] if delivery_result else str(out / "ui_interactive_scene_auto.h"),
        "asset_pack_path": None if evidence_removed else str(out / "asset.pack"), "asset_manifest": asset_manifest,
        "firmware_assets": delivered_firmware, "resource_closure": closure,
        "symbols": contract["symbols"], "font_sources": contract["font_sources"],
        "spec_path": None if evidence_removed else str(render_spec_path),
        "render_validation": render_validation,
        "delivery": delivery_result,
        "warnings": [*result.get("summary", {}).get("warnings", []), *preview_warnings],
        "font_source": str(ttf_source) if ttf_source else None,
        "font_subset_active": ttf_subsets_active,
    }
