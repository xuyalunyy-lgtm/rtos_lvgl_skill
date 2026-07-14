from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw

from mcp.asset_contract import DEFAULT_UI_FLASH_BYTES, resolve_asset_contract, validate_initial_manifest
from mcp import high_level_tools


def _rgba(path: Path, size: tuple[int, int] = (20, 20), inset: int = 2) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGBA", size, (0, 0, 0, 0))
    ImageDraw.Draw(image).rectangle((inset, inset, size[0] - inset - 1, size[1] - inset - 1), fill=(40, 120, 220, 255))
    image.save(path)


def _rgb(path: Path, size: tuple[int, int] = (48, 80)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, (20, 40, 60)).save(path)


def _manifest(root: Path, assets: list[dict], size: tuple[int, int] = (48, 80)) -> Path:
    design = root / "design" / "screen.png"
    _rgb(design, size)
    payload = {
        "schema_version": "1.0",
        "project": "fixture",
        "design_reference": "design/screen.png",
        "asset_root": "assets",
        "display": {"width": size[0], "height": size[1], "rotation": 0, "color_format": "RGB565"},
        "assets": assets,
    }
    path = root / "initial_asset_manifest.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _intent(symbol: str, asset_type: str, hint: str, **extra: object) -> dict:
    return {"symbol": symbol, "type": asset_type, "file_hint": hint, "required": True, **extra}


def test_schema_rejects_physical_fields_invalid_symbol_and_duplicates() -> None:
    manifest = {
        "schema_version": "1.0", "project": "x", "design_reference": "design.png",
        "display": {"width": 1, "height": 1, "rotation": 0, "color_format": "RGB565"},
        "assets": [
            {"symbol": "bad-symbol", "type": "status_icon", "file_hint": "a.png", "width": 1},
            {"symbol": "bad-symbol", "type": "status_icon", "file_hint": "b.png"},
        ],
    }
    result = validate_initial_manifest(manifest)
    assert not result["valid"]
    assert any("forbidden physical fields" in error for error in result["errors"])
    assert any("valid C identifier" in error for error in result["errors"])


def test_exact_filename_physical_metadata_and_per_asset_closure(tmp_path: Path) -> None:
    root = tmp_path / "ui"
    pet = root / "assets" / "characters" / "pet_idle.png"
    _rgba(pet, (20, 30), 2)
    manifest = _manifest(root, [_intent("ui_pet", "transparent_character", "pet_idle.png")])
    out = tmp_path / "out"
    result = resolve_asset_contract(manifest, package_root=root, asset_root=root / "assets", output_dir=out)
    assert result["ok"] and result["status"] == "asset_contract_ready"
    resolved = result["resolved_assets"][0]
    assert resolved["match_method"] == "exact_filename"
    assert resolved["original_size"] == [20, 30]
    assert resolved["converted_size"] == [16, 26]
    assert resolved["crop_offset"] == [2, 2]
    assert resolved["stride"] == 32
    assert resolved["flash_bytes"] == 16 * 26 * 3
    assert (out / "ui_pet.c").is_file()
    assert "ui_pet.c" in (out / "ui_auto_assets.cmake").read_text(encoding="utf-8")
    assert result["resource_closure"]["ok"]


def test_unique_wifi_fuzzy_match_and_close_candidates_are_rejected(tmp_path: Path) -> None:
    root = tmp_path / "ui"
    _rgba(root / "assets" / "icons" / "system" / "icon_wifi_connected_3.png")
    manifest = _manifest(root, [_intent("icon_wifi", "status_icon", "wifi.png")])
    accepted = resolve_asset_contract(manifest, package_root=root, asset_root=root / "assets", output_dir=tmp_path / "accepted")
    assert accepted["ok"]
    assert accepted["resolved_assets"][0]["match_method"] == "unique_fuzzy_match"

    _rgba(root / "assets" / "icons" / "system" / "icon_wifi_connected_4.png")
    rejected = resolve_asset_contract(manifest, package_root=root, asset_root=root / "assets", output_dir=tmp_path / "rejected")
    assert not rejected["ok"] and rejected["status"] == "manual_required"
    report = json.loads((tmp_path / "rejected" / "asset_resolution_report.json").read_text(encoding="utf-8"))
    assert report["items"][0]["reason"] == "fuzzy_match_not_unique"
    assert len(report["items"][0]["candidates"]) >= 2


def test_status_icon_keeps_source_canvas_without_alpha_crop(tmp_path: Path) -> None:
    root = tmp_path / "ui"
    icon = root / "assets" / "icons" / "system" / "icon_wifi.png"
    _rgba(icon, (48, 48), 8)
    manifest = _manifest(root, [_intent("icon_wifi", "status_icon", "icon_wifi.png")])
    result = resolve_asset_contract(manifest, package_root=root, asset_root=root / "assets", output_dir=tmp_path / "out")
    assert result["ok"]
    resolved = result["resolved_assets"][0]
    assert resolved["original_size"] == [48, 48]
    assert resolved["converted_size"] == [48, 48]
    assert resolved["crop_offset"] == [0, 0]
    assert resolved["flash_bytes"] == 48 * 48 * 3


def test_explicit_flat_icon_names_are_type_compatible(tmp_path: Path) -> None:
    root = tmp_path / "ui"
    _rgba(root / "assets" / "icon_back.png", (48, 48), 8)
    _rgba(root / "assets" / "icon_battery.png", (48, 48), 8)
    manifest = _manifest(root, [
        _intent("icon_back", "control_icon", "icon_back.png", preserve_source_canvas=True),
        _intent("icon_battery", "status_icon", "icon_battery.png", preserve_source_canvas=True),
    ])
    result = resolve_asset_contract(
        manifest,
        package_root=root,
        asset_root=root / "assets",
        output_dir=tmp_path / "out",
    )
    assert result["ok"]
    assert [item["match_method"] for item in result["resolved_assets"]] == ["exact_relative_path", "exact_relative_path"]
    assert all(item["crop_offset"] == [0, 0] for item in result["resolved_assets"])


def test_explicit_source_canvas_contract_preserves_transparent_padding(tmp_path: Path) -> None:
    root = tmp_path / "ui"
    pet = root / "assets" / "characters" / "pet_idle.png"
    _rgba(pet, (20, 30), 2)
    manifest = _manifest(root, [
        _intent(
            "ui_pet",
            "transparent_character",
            "pet_idle.png",
            preserve_source_canvas=True,
        )
    ])
    result = resolve_asset_contract(
        manifest,
        package_root=root,
        asset_root=root / "assets",
        output_dir=tmp_path / "out",
    )
    assert result["ok"]
    resolved = result["resolved_assets"][0]
    assert resolved["original_size"] == [20, 30]
    assert resolved["converted_size"] == [20, 30]
    assert resolved["crop_offset"] == [0, 0]
    assert resolved["preserve_source_canvas"] is True
    assert resolved["flash_bytes"] == 20 * 30 * 3


def test_source_canvas_contract_requires_boolean() -> None:
    manifest = {
        "schema_version": "1.0", "project": "x", "design_reference": "design.png",
        "display": {"width": 1, "height": 1, "rotation": 0, "color_format": "RGB565"},
        "assets": [{
            "symbol": "ui_pet", "type": "transparent_character", "file_hint": "pet.png",
            "preserve_source_canvas": "yes",
        }],
    }
    result = validate_initial_manifest(manifest)
    assert not result["valid"]
    assert any("preserve_source_canvas must be a boolean" in error for error in result["errors"])


def test_path_escape_wrong_directory_and_duplicate_source_are_rejected(tmp_path: Path) -> None:
    root = tmp_path / "ui"
    _rgba(root / "assets" / "icons" / "system" / "icon_wifi.png")
    escaped = _manifest(root, [_intent("icon_wifi", "status_icon", "../icon_wifi.png")])
    result = resolve_asset_contract(escaped, package_root=root, asset_root=root / "assets", output_dir=tmp_path / "escape")
    assert not result["ok"] and "file_hint_path_escape" in result["errors"][0]

    wrong = _manifest(root, [_intent("ui_pet", "transparent_character", "icon_wifi.png")])
    result = resolve_asset_contract(wrong, package_root=root, asset_root=root / "assets", output_dir=tmp_path / "wrong")
    assert not result["ok"] and "no_type_compatible_candidate" in result["errors"][0]

    duplicate = _manifest(root, [
        _intent("icon_wifi", "status_icon", "icon_wifi.png"),
        _intent("icon_wlan", "status_icon", "icon_wifi.png"),
    ])
    result = resolve_asset_contract(duplicate, package_root=root, asset_root=root / "assets", output_dir=tmp_path / "duplicate")
    assert not result["ok"] and any("source already bound" in error for error in result["errors"])


def test_design_path_and_renamed_hash_copy_are_forbidden(tmp_path: Path) -> None:
    root = tmp_path / "ui"
    design = root / "design" / "screen.png"
    _rgb(design)
    copied = root / "assets" / "backgrounds" / "background.png"
    copied.parent.mkdir(parents=True, exist_ok=True)
    copied.write_bytes(design.read_bytes())
    manifest = _manifest(root, [_intent("ui_bg", "full_screen_background", "background.png")])
    result = resolve_asset_contract(manifest, package_root=root, asset_root=root / "assets", output_dir=tmp_path / "out")
    assert not result["ok"]
    assert "design reference cannot be a runtime asset" in result["errors"][0]
    assert hashlib.sha256(copied.read_bytes()).digest() == hashlib.sha256(design.read_bytes()).digest()


def test_background_and_alpha_type_gates(tmp_path: Path) -> None:
    root = tmp_path / "ui"
    _rgb(root / "assets" / "backgrounds" / "wrong.jpg", (47, 80))
    manifest = _manifest(root, [_intent("ui_bg", "full_screen_background", "wrong.jpg")])
    result = resolve_asset_contract(manifest, package_root=root, asset_root=root / "assets", output_dir=tmp_path / "wrong_size")
    assert not result["ok"] and "background_size_mismatch" in result["errors"][0]

    alpha_bg = root / "assets" / "backgrounds" / "alpha.png"
    alpha_bg.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", (48, 80), (1, 2, 3, 128)).save(alpha_bg)
    manifest = _manifest(root, [_intent("ui_bg", "full_screen_background", "alpha.png")])
    result = resolve_asset_contract(manifest, package_root=root, asset_root=root / "assets", output_dir=tmp_path / "alpha_bg")
    assert not result["ok"] and "background_has_effective_alpha" in result["errors"][0]

    _rgb(root / "assets" / "characters" / "opaque.jpg", (20, 30))
    manifest = _manifest(root, [_intent("ui_pet", "transparent_character", "opaque.jpg")])
    result = resolve_asset_contract(manifest, package_root=root, asset_root=root / "assets", output_dir=tmp_path / "opaque")
    assert not result["ok"] and "required_effective_alpha_missing" in result["errors"][0]


def test_output_is_deterministic_for_same_inputs(tmp_path: Path) -> None:
    root = tmp_path / "ui"
    _rgba(root / "assets" / "characters" / "pet.png")
    manifest = _manifest(root, [_intent("ui_pet", "transparent_character", "pet.png")])
    first = tmp_path / "first"
    second = tmp_path / "second"
    assert resolve_asset_contract(manifest, package_root=root, asset_root=root / "assets", output_dir=first)["ok"]
    assert resolve_asset_contract(manifest, package_root=root, asset_root=root / "assets", output_dir=second)["ok"]
    for name in ("resolved_asset_manifest.json", "asset_resolution_report.json", "resource_closure_report.json", "asset.pack", "ui_pet.c", "ui_auto_assets.h", "ui_auto_assets.cmake"):
        assert (first / name).read_bytes() == (second / name).read_bytes()


def test_flash_budget_overrun_requires_manual_resolution(tmp_path: Path) -> None:
    root = tmp_path / "ui"
    _rgba(root / "assets" / "characters" / "pet.png")
    manifest = _manifest(root, [_intent("ui_pet", "transparent_character", "pet.png")])
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["limits"] = {"max_flash_bytes": 10}
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    result = resolve_asset_contract(manifest, package_root=root, asset_root=root / "assets", output_dir=tmp_path / "budget")
    assert not result["ok"] and result["status"] == "manual_required"
    assert "asset flash budget exceeded" in result["errors"][0]
    report = json.loads((tmp_path / "budget" / "asset_resolution_report.json").read_text(encoding="utf-8"))
    assert report["flash_budget"]["passed"] is False


def test_inspect_design_writes_initial_manifest_only_under_artifacts(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(high_level_tools, "ROOT", tmp_path)
    ui = tmp_path / "ui"
    design = ui / "design" / "screen.png"
    _rgb(design, (48, 80))
    (ui / "assets").mkdir(parents=True)
    result = high_level_tools.inspect_design({
        "design_path": str(design),
        "asset_root": str(ui / "assets"),
        "display": {"width": 48, "height": 80, "rotation": 0, "color_format": "RGB565"},
        "asset_intents": [_intent("ui_bg", "full_screen_background", "background.png")],
        "output_dir": "artifacts/inspect_fixture",
    })
    assert result["ok"] and result["status"] == "initial_asset_manifest_ready"
    manifest_path = Path(result["initial_asset_manifest"])
    assert manifest_path == tmp_path / "artifacts" / "inspect_fixture" / "initial_asset_manifest.json"
    generated_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert generated_manifest["limits"]["max_flash_bytes"] == DEFAULT_UI_FLASH_BYTES
    assert not (design.parent / "input_manifest.json").exists()
    assert not (design.parent / "analysis_report.json").exists()
    assert not (design.parent / "debug_overlay.png").exists()
    assert (tmp_path / "artifacts" / "inspect_fixture" / "analysis_report.json").is_file()
    assert (tmp_path / "artifacts" / "inspect_fixture" / "debug_overlay.png").is_file()
