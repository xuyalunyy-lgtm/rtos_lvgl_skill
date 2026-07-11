"""Auto-discover a conventional ui/ directory and bind its cutouts."""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

from mcp.interactive_scene_auto import generate_interactive_scene_page
from mcp.lvgl_ir.asset_pack import encode_pack, generate_manifest, pack_asset

_FONT_SYMBOL = re.compile(r"\b(?:const\s+)?lv_font_t\s+([A-Za-z_]\w*)\s*=")


def generate_standard_ui_package(ui_dir: str | Path, output_dir: str | Path) -> dict[str, Any]:
    root, out = Path(ui_dir).resolve(), Path(output_dir).resolve()
    backgrounds = sorted((root / "assets" / "backgrounds").glob("*"))
    characters = sorted((root / "assets" / "characters").glob("*"))
    mood_dir, system_dir = root / "assets" / "icons" / "mood", root / "assets" / "icons" / "system"
    required = {"calmness", "good", "down", "stressed"}
    moods = {name: mood_dir / f"{name}.png" for name in required}
    systems = {name.removeprefix("icon_"): path for path in system_dir.glob("icon_*.png") for name in [path.stem]}
    if not backgrounds or not characters or any(not path.is_file() for path in moods.values()):
        return {"ok": False, "errors": ["standard ui package needs backgrounds/, characters/, and four mood icons"]}
    out.mkdir(parents=True, exist_ok=True)
    assets: list[tuple[str, Path]] = [("ui_bg", backgrounds[0]), ("ui_pet", characters[0])]
    assets += [(f"mood_{key}", moods[key]) for key in sorted(moods)]
    assets += [(f"icon_{key}", value) for key, value in sorted(systems.items())]
    packed = [pack_asset(path, symbol, "AUTO") for symbol, path in assets]
    failures = [item.get("error", item.get("symbol", "unknown")) for item in packed if not item.get("ok")]
    if failures:
        return {"ok": False, "errors": [f"asset packing failed: {', '.join(map(str, failures))}"]}
    (out / "asset.pack").write_bytes(encode_pack(packed))
    asset_manifest = generate_manifest(packed, out)
    header = out / "ui_auto_assets.h"
    header.write_text(
        "#ifndef UI_AUTO_ASSETS_H\n#define UI_AUTO_ASSETS_H\n#include \"lvgl.h\"\n\n" +
        "\n".join(f"LV_IMG_DECLARE({symbol});" for symbol, _ in assets) +
        "\n\n#endif\n", encoding="utf-8", newline="\n"
    )
    font_sources: list[tuple[str, Path]] = []
    for source in sorted((root / "fonts" / "lvgl").glob("*.c")):
        match = _FONT_SYMBOL.search(source.read_text(encoding="utf-8", errors="ignore"))
        if match:
            copied = out / source.name
            shutil.copy2(source, copied)
            font_sources.append((match.group(1), copied))
    font_header = out / "ui_auto_fonts.h"
    font_header.write_text(
        "#ifndef UI_AUTO_FONTS_H\n#define UI_AUTO_FONTS_H\n#include \"lvgl.h\"\n\n" +
        "\n".join(f"LV_FONT_DECLARE({symbol});" for symbol, _ in font_sources) +
        "\n\n#endif\n", encoding="utf-8", newline="\n"
    )
    (out / "ui_auto_fonts.cmake").write_text(
        "set(UI_AUTO_FONT_SOURCES\n" + "\n".join(f'    "{path.name}"' for _, path in font_sources) + "\n)\n",
        encoding="utf-8", newline="\n",
    )
    font_exprs = {"top": "&font_40_bold", "title": "&font_20_bold", "hint": "&font_14_regular"}
    args = {
        "design_dir": str(root), "design_path": str(backgrounds[0]), "background_path": str(backgrounds[0]),
        "pet_path": str(characters[0]), "mood_paths": {key: str(path) for key, path in moods.items()},
        "output_dir": str(out), "assets_dir": str(out), "page_name": "interactive_scene_auto",
        "width": 480, "height": 800, "lvgl_version": "v9", "skip_preflight": True,
        "auto_analyze": False, "return_mode": "compact", "asset_header": header.name,
        "font_header": font_header.name, "font_macro_exprs": font_exprs,
        "background_src": "&ui_bg", "pet_src": "&ui_pet",
        "mood_src": {key: f"&mood_{key}" for key in moods},
    }
    result = generate_interactive_scene_page(args)
    if not result.get("ok"):
        return result
    c_path = out / "ui_interactive_scene_auto.c"
    source = c_path.read_text(encoding="utf-8")
    # Replace the status approximations with the supplied image cutouts. A
    # missing cutout remains dynamic, preserving runtime behaviour.
    snippets = []
    for key, x, y, w, h in (("wifi", 297, 20, 31, 23), ("bluetooth", 363, 18, 21, 29), ("battery", 413, 23, 36, 18)):
        symbol = f"icon_{key}"
        if any(name == symbol for name, _ in assets):
            snippets.append(f"    lv_obj_t *system_{key} = lv_image_create(s_page);\n    lv_image_set_src(system_{key}, &{symbol});\n    lv_obj_set_pos(system_{key}, {x}, {y});\n    lv_obj_set_size(system_{key}, {w}, {h});")
    if snippets:
        source = re.sub(r"    lv_obj_t \*favorite =.*?(?=\n    s_top_prompt)", "\n\n".join(snippets), source, count=1, flags=re.DOTALL)
        c_path.write_text(source, encoding="utf-8", newline="\n")
    contract = {
        "mode": "standard_directory_autodiscovery", "runtime_asset_pack": "asset.pack",
        "firmware_asset_header": header.name, "symbols": [symbol for symbol, _ in assets],
        "source_root": str(root), "status_cutouts": sorted(systems),
        "font_sources": [path.name for _, path in font_sources],
    }
    (out / "auto_discovery_report.json").write_text(json.dumps(contract, indent=2) + "\n", encoding="utf-8")
    return {"ok": True, "output_dir": str(out), "c_path": str(c_path), "asset_pack_path": str(out / "asset.pack"), "asset_manifest": asset_manifest, "symbols": contract["symbols"], "font_sources": contract["font_sources"], "warnings": result.get("summary", {}).get("warnings", [])}
