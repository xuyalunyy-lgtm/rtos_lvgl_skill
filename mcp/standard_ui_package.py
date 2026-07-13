"""Auto-discover a conventional ui/ directory and bind its cutouts."""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

from mcp.interactive_scene_auto import generate_interactive_scene_page
from mcp.lvgl_ir.asset_pack import encode_pack, generate_manifest, list_pack_symbols, pack_asset, write_lvgl_v9_c_assets

_FONT_SYMBOL = re.compile(r"\b(?:const\s+)?lv_font_t\s+([A-Za-z_]\w*)\s*=")
_STATUS_VISIBLE_DEFAULTS = {
    "wifi": (297, 20, 31, 23),
    "bluetooth": (363, 18, 21, 29),
    "battery": (413, 23, 36, 18),
}


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
    font_cmake: Path,
) -> dict[str, Any]:
    """Atomically publish only compilable code and direct dependencies."""
    staging = delivery.parent / f".{delivery.name}_staging"
    _fresh_directory(staging)
    required = [
        page_c, page_h, Path(firmware_assets["header"]), Path(firmware_assets["cmake"]),
        *[Path(path) for path in firmware_assets["sources"]],
        *[path for _, path in font_sources], font_header, font_cmake,
    ]
    for source in required:
        if not source.is_file():
            raise FileNotFoundError(f"required delivery dependency missing: {source}")
        shutil.copy2(source, staging / source.name)
    aggregate = staging / "ui_generated.cmake"
    aggregate.write_text(
        "include(\"${CMAKE_CURRENT_LIST_DIR}/ui_auto_assets.cmake\")\n"
        "include(\"${CMAKE_CURRENT_LIST_DIR}/ui_auto_fonts.cmake\")\n"
        "set(UI_GENERATED_SOURCES\n"
        f"    \"${{CMAKE_CURRENT_LIST_DIR}}/{page_c.name}\"\n"
        "    ${UI_AUTO_ASSET_SOURCES}\n"
        "    ${UI_AUTO_FONT_SOURCES}\n"
        ")\n",
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
    strict_asset_contract: bool = True,
    final_only: bool = True,
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
        requested_font_symbols = {"font_40_bold", "font_20_bold", "font_14_regular"}
    header = Path(firmware_assets["header"])
    font_sources: list[tuple[str, Path]] = []
    for source in sorted((root / "fonts" / "lvgl").glob("*.c")):
        match = _FONT_SYMBOL.search(source.read_text(encoding="utf-8", errors="ignore"))
        if match and match.group(1) in requested_font_symbols:
            copied = out / source.name
            shutil.copy2(source, copied)
            font_sources.append((match.group(1), copied))
    font_header = out / "ui_auto_fonts.h"
    font_header.write_text(
        "#ifndef UI_AUTO_FONTS_H\n#define UI_AUTO_FONTS_H\n#include \"lvgl.h\"\n\n" +
        "\n".join(f"LV_FONT_DECLARE({symbol});" for symbol, _ in font_sources) +
        "\n\n#endif\n", encoding="utf-8", newline="\n"
    )
    font_cmake = out / "ui_auto_fonts.cmake"
    font_cmake.write_text(
        "set(UI_AUTO_FONT_SOURCES\n" + "\n".join(f'    "${{CMAKE_CURRENT_LIST_DIR}}/{path.name}"' for _, path in font_sources) + "\n)\n",
        encoding="utf-8", newline="\n",
    )
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
    c_path = out / "ui_interactive_scene_auto.c"
    source = c_path.read_text(encoding="utf-8")
    # Replace the status approximations with the supplied image cutouts. A
    # missing cutout remains dynamic, preserving runtime behaviour.
    snippets = []
    resolved_status = {item["symbol"].removeprefix("icon_"): item for item in system_items} if contract_mode else {}
    for key, path in sorted(systems.items()):
        symbol = f"icon_{key}"
        if any(name == symbol for name, _ in assets):
            x, y, w, h = _status_icon_layout(key, path, resolved_status.get(key))
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
            font_header=font_header, font_cmake=font_cmake,
        )
        delivered_firmware = {
            **firmware_assets,
            "header": str(delivery / Path(firmware_assets["header"]).name),
            "sources": [str(delivery / Path(path).name) for path in firmware_assets["sources"]],
            "cmake": str(delivery / Path(firmware_assets["cmake"]).name),
        }
    else:
        delivered_firmware = firmware_assets
    return {
        "ok": closure["ok"], "status": "asset_contract_ready" if contract_mode else "inferred_without_design",
        "output_dir": str(delivery if final_only else out), "evidence_dir": str(out),
        "c_path": delivery_result["page_c"] if delivery_result else str(c_path),
        "h_path": delivery_result["page_h"] if delivery_result else str(out / "ui_interactive_scene_auto.h"),
        "asset_pack_path": str(out / "asset.pack"), "asset_manifest": asset_manifest,
        "firmware_assets": delivered_firmware, "resource_closure": closure,
        "symbols": contract["symbols"], "font_sources": contract["font_sources"],
        "delivery": delivery_result, "warnings": result.get("summary", {}).get("warnings", []),
    }
