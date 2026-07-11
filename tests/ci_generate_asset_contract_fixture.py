"""Generate deterministic CI-only asset-contract inputs and link harness."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mcp.asset_contract import resolve_asset_contract  # noqa: E402
from mcp.lvgl_ir.scene_encoder import encode_spec  # noqa: E402


def main() -> int:
    package = ROOT / "artifacts" / "asset_contract_ci" / "ui"
    output = ROOT / "artifacts" / "asset_contract_ci" / "generated"
    design = package / "design" / "screen.png"
    background = package / "assets" / "backgrounds" / "fixture_background.png"
    icon = package / "assets" / "icons" / "system" / "icon_wifi_connected_3.png"
    for path in (design, background, icon):
        path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (48, 80), (10, 20, 30)).save(design)
    Image.new("RGB", (48, 80), (30, 60, 90)).save(background)
    icon_image = Image.new("RGBA", (12, 12), (0, 0, 0, 0))
    ImageDraw.Draw(icon_image).ellipse((2, 2, 9, 9), fill=(255, 255, 255, 255))
    icon_image.save(icon)
    manifest = {
        "schema_version": "1.0", "project": "ci_asset_contract", "design_reference": "design/screen.png",
        "asset_root": "assets", "display": {"width": 48, "height": 80, "rotation": 0, "color_format": "RGB565"},
        "assets": [
            {"symbol": "ui_bg", "type": "full_screen_background", "file_hint": "fixture_background.png", "required": True},
            {"symbol": "icon_wifi", "type": "status_icon", "file_hint": "wifi.png", "required": True},
        ],
    }
    manifest_path = package / "initial_asset_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    result = resolve_asset_contract(manifest_path, package_root=package, asset_root=package / "assets", output_dir=output)
    if not result.get("ok"):
        print(json.dumps(result, indent=2))
        return 1
    symbols = [item["symbol"] for item in result["resolved_assets"]]
    (output / "asset_link_harness.c").write_text(
        '#include "ui_auto_assets.h"\n\n'
        "int main(void) {\n"
        "    const lv_image_dsc_t *assets[] = {" + ", ".join(f"&{symbol}" for symbol in symbols) + "};\n"
        "    return assets[0]->header.magic == LV_IMAGE_HEADER_MAGIC ? 0 : 1;\n"
        "}\n",
        encoding="utf-8", newline="\n",
    )
    scene = {
        "schema_version": "2.0", "page_name": "asset_contract_ci", "display": {"width": 48, "height": 80},
        "lvgl_version": "v9", "nodes": [
            {"id": "root", "type": "screen"},
            {"id": "background", "type": "image", "parent_id": "root", "src": "ui_bg"},
            {"id": "wifi", "type": "image", "parent_id": "root", "src": "icon_wifi"},
        ],
    }
    (output / "scene.bin").write_bytes(encode_spec(scene))
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
