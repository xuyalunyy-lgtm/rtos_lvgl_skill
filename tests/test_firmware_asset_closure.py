from pathlib import Path

from PIL import Image, ImageDraw

from mcp.lvgl_ir.asset_pack import write_lvgl_v9_c_assets
from mcp.standard_ui_package import generate_standard_ui_package


def test_emits_real_rgb565a8_descriptor_and_cmake_source(tmp_path: Path) -> None:
    result = write_lvgl_v9_c_assets([
        {
            "ok": True,
            "symbol": "ui_pet",
            "color_format": "RGB565A8",
            "pixel_data": b"\x01\x02\x03\x04",
            "alpha_data": b"\x80\xff",
            "width": 2,
            "height": 1,
            "flash_bytes": 6,
        }
    ], tmp_path)

    assert len(result["sources"]) == 1
    source = Path(result["sources"][0]).read_text(encoding="utf-8")
    header = Path(result["header"]).read_text(encoding="utf-8")
    cmake = Path(result["cmake"]).read_text(encoding="utf-8")
    assert "LV_IMAGE_DECLARE(ui_pet);" in header
    assert "const lv_image_dsc_t ui_pet" in source
    assert ".header.cf = LV_COLOR_FORMAT_RGB565A8" in source
    assert ".header.stride = 4" in source
    assert "0x01, 0x02, 0x03, 0x04, 0x80, 0xFF" in source
    assert "ui_pet.c" in cmake


def test_standard_package_trims_cutout_padding_and_fits_v92_images(tmp_path: Path) -> None:
    root = tmp_path / "ui"
    background = root / "assets" / "backgrounds" / "scene.png"
    pet = root / "assets" / "characters" / "pet_idle.png"
    mood_dir = root / "assets" / "icons" / "mood"
    system_dir = root / "assets" / "icons" / "system"
    for directory in (background.parent, pet.parent, mood_dir, system_dir):
        directory.mkdir(parents=True, exist_ok=True)
    font_dir = root / "fonts" / "lvgl"
    font_dir.mkdir(parents=True, exist_ok=True)
    for filename, symbol in (("40_bold.c", "font_40_bold"), ("20_bold.c", "font_20_bold"), ("14_regular.c", "font_14_regular"), ("unused.c", "font_unused")):
        (font_dir / filename).write_text(f'const lv_font_t {symbol} = {{0}};\n', encoding="utf-8")

    Image.new("RGB", (480, 800), (32, 64, 96)).save(background)
    pet_img = Image.new("RGBA", (30, 40), (0, 0, 0, 0))
    ImageDraw.Draw(pet_img).rectangle((2, 3, 27, 35), fill=(200, 220, 180, 255))
    pet_img.save(pet)
    for name in ("calmness", "good", "down", "stressed"):
        Image.new("RGBA", (37, 37), (255, 255, 255, 255)).save(mood_dir / f"{name}.png")
    battery = Image.new("RGBA", (48, 48), (0, 0, 0, 0))
    ImageDraw.Draw(battery).rectangle((4, 14, 43, 33), fill=(255, 255, 255, 255))
    battery.save(system_dir / "icon_battery.png")

    result = generate_standard_ui_package(root, tmp_path / "out")
    assert result["ok"]
    source = (tmp_path / "out" / "ui_interactive_scene_auto.c").read_text(encoding="utf-8")
    manifest = __import__("json").dumps(result["asset_manifest"])
    assert "lv_image_set_inner_align(pet, LV_IMAGE_ALIGN_STRETCH);" in source
    assert "lv_image_set_inner_align(system_battery, LV_IMAGE_ALIGN_CENTER);" in source
    assert "lv_obj_set_size(system_battery, 48, 48);" in source
    assert '"symbol": "ui_pet"' in manifest
    assert '"width": 26' in manifest
    assert '"height": 33' in manifest
    assert not (tmp_path / "out" / "asset_manifest.json").exists()
    assert not (tmp_path / "out" / "resource_closure_report.json").exists()
    assert not (tmp_path / "out" / "asset.pack").exists()
    assert (tmp_path / "out" / "ui_generated.cmake").is_file()
    assert (tmp_path / "out" / "40_bold.c").is_file()
    assert (tmp_path / "out" / "20_bold.c").is_file()
    assert (tmp_path / "out" / "14_regular.c").is_file()
    assert not (tmp_path / "out" / "unused.c").exists()
    assert result["evidence_dir"] is None
    assert result["asset_pack_path"] is None
    assert result["evidence_removed"] is True
    assert not (tmp_path / ".out_evidence").exists()
    assert (tmp_path / "out" / "delivery_manifest.json").is_file()


def test_standard_package_can_keep_full_generation_evidence(tmp_path: Path) -> None:
    root = tmp_path / "ui"
    background = root / "assets" / "backgrounds" / "scene.png"
    pet = root / "assets" / "characters" / "pet_idle.png"
    mood_dir = root / "assets" / "icons" / "mood"
    font_dir = root / "fonts" / "lvgl"
    for directory in (background.parent, pet.parent, mood_dir, font_dir):
        directory.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (480, 800), (32, 64, 96)).save(background)
    Image.new("RGBA", (30, 40), (200, 220, 180, 255)).save(pet)
    for name in ("calmness", "good", "down", "stressed"):
        Image.new("RGBA", (37, 37), (255, 255, 255, 255)).save(mood_dir / f"{name}.png")
    for filename, symbol in (("40_bold.c", "font_40_bold"), ("20_bold.c", "font_20_bold"), ("14_regular.c", "font_14_regular")):
        (font_dir / filename).write_text(f'const lv_font_t {symbol} = {{0}};\n', encoding="utf-8")

    result = generate_standard_ui_package(root, tmp_path / "out", cleanup_intermediates=False)

    assert result["ok"]
    assert result["evidence_removed"] is False
    assert Path(result["evidence_dir"]).is_dir()
    assert Path(result["asset_pack_path"]).is_file()
