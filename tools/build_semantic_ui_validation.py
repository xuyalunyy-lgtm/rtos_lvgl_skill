"""Build a deterministic four-page UI Spec v2 validation package.

This is intentionally an explicit asset matrix, not a generic screenshot to
widget converter.  It proves the production path for the shared home/push
assets while preserving a manual-slice queue for designs that do not have an
approved runtime asset yet.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mcp.asset_contract import build_initial_manifest, resolve_asset_contract, write_initial_manifest
from mcp.high_level_tools import compare_ui, render_ui
from mcp.lvgl_compile_gate import validate_directory
from mcp.lvgl_codegen import generate_page_code
from mcp.standard_ui_package import _generate_ttf_font_subsets, _write_font_bundle


DISPLAY = {"width": 480, "height": 800, "rotation": 0, "color_format": "RGB565"}
DEFAULT_MAX_FLASH_BYTES = 8 * 1024 * 1024
FONT_SOURCE = ROOT / "ui" / "fonts" / "InriaSerif-Bold.ttf"
FONT_REGULAR_SOURCE = ROOT / "ui" / "fonts" / "InriaSerif-Regular.ttf"
PACKAGE_ROOT = ROOT / "ui" / "multipage"
ASSET_ROOT = PACKAGE_ROOT / "assets"

# Every source below was visually checked.  The asset resolver still performs
# the authoritative path, hash, format, alpha and budget checks.
SHARED_ASSETS = [
    ("UI_IMG_BG_HOME", "full_screen_background", "backgrounds/background_home.png"),
    ("UI_IMG_BG_AFFIRMATION", "full_screen_background", "backgrounds/background_affirmation_favorited.png"),
    ("UI_IMG_PET_IDLE", "transparent_character", "characters/character_pet_idle.png"),
    ("UI_IMG_LOADING_SPIRIT", "transparent_character", "characters/character_loading_spirit.png"),
    ("UI_IMG_WIFI", "decorative_image", "controls/control_wifi.png"),
    ("UI_IMG_BLUETOOTH", "decorative_image", "controls/control_bluetooth.png"),
    ("UI_IMG_BATTERY", "decorative_image", "controls/control_battery.png"),
    ("UI_IMG_MOOD_CALM", "decorative_image", "moods/mood_calmness.png"),
    ("UI_IMG_MOOD_GOOD", "decorative_image", "moods/mood_good.png"),
    ("UI_IMG_MOOD_DOWN", "decorative_image", "moods/mood_down.png"),
    ("UI_IMG_MOOD_STRESSED", "decorative_image", "moods/mood_stressed.png"),
    ("UI_IMG_TEXT_CARD", "decorative_image", "content/content_text_card.png"),
    ("UI_IMG_BACK", "decorative_image", "controls/control_back.png"),
    ("UI_IMG_REC_01", "decorative_image", "content/content_daily_recommendation_01.png"),
    ("UI_IMG_REC_02", "decorative_image", "content/content_daily_recommendation_02.png"),
    ("UI_IMG_REC_03", "decorative_image", "content/content_daily_recommendation_03.png"),
    ("UI_IMG_SCHEDULE_DECORATION", "decorative_image", "content/content_text_label.png"),
    ("UI_IMG_BLUR_HOME_CARD", "decorative_image", "generated/blur_home_card.png"),
    ("UI_IMG_BLUR_PUSH_CARD", "decorative_image", "generated/blur_push_card.png"),
    ("UI_IMG_BLUR_STATUS_CARD", "decorative_image", "generated/blur_status_card.png"),
]


def _image(node_id: str, symbol: str, bbox: list[int], *, image_fit: str | None = None) -> dict[str, Any]:
    node = {
        "id": node_id, "type": "image", "parent_id": "root", "src": symbol,
        "src_expr": f"&{symbol}", "source_bbox": bbox,
    }
    if image_fit:
        node["image_fit"] = image_fit
    return node


def _label(
    node_id: str,
    text: str,
    bbox: list[int],
    font: str,
    size: int,
    align: str = "left",
    text_color: str = "#FFFFFF",
) -> dict[str, Any]:
    return {
        "id": node_id, "type": "label", "parent_id": "root", "text": text,
        "source_bbox": bbox,
        # font_id is consumed by the renderer; font is the C expression.
        "styles": {"text_color": text_color, "font_id": font, "font": f"&{font}", "text_font_size": size, "text_align": align},
    }


def _card(node_id: str, bbox: list[int]) -> dict[str, Any]:
    return {
        "id": node_id, "type": "container", "parent_id": "root", "source_bbox": bbox,
        "styles": {"bg_color": "#6E7947", "bg_opa": 255, "border_width": 1, "border_color": "#F5F2DF", "radius": 24},
    }


def _mood_button(node_id: str, bbox: list[int]) -> dict[str, Any]:
    return {
        "id": node_id, "type": "container", "parent_id": "root", "source_bbox": bbox,
        "styles": {"bg_color": "#FFFFFF", "bg_opa": 255, "radius": 35},
    }


def _dot(node_id: str, bbox: list[int], color: str, *, border_color: str | None = None) -> dict[str, Any]:
    styles: dict[str, Any] = {"bg_color": color, "bg_opa": 255, "radius": min(bbox[2], bbox[3]) // 2}
    if border_color:
        styles.update({"border_width": 2, "border_color": border_color})
    return {"id": node_id, "type": "container", "parent_id": "root", "source_bbox": bbox, "styles": styles}


def _status_bar() -> list[dict[str, Any]]:
    return [
        # The icon cuts include transparent canvas padding.  Bboxes therefore
        # position the full cut, not only its visible alpha bounds.
        _image("wifi", "UI_IMG_WIFI", [288, 8, 48, 48]),
        _image("bluetooth", "UI_IMG_BLUETOOTH", [348, 8, 48, 48]),
        _image("battery", "UI_IMG_BATTERY", [408, 8, 48, 48]),
    ]


def _write_blur_patch(
    destination: Path,
    *,
    background: Path,
    foreground: Path | None,
    foreground_xy: tuple[int, int],
    bbox: tuple[int, int, int, int],
    radius: int = 4,
    corner_radius: int = 24,
) -> None:
    from PIL import Image, ImageDraw, ImageFilter

    scene = Image.open(background).convert("RGBA")
    if foreground:
        cut = Image.open(foreground).convert("RGBA")
        scene.alpha_composite(cut, foreground_xy)
    x, y, width, height = bbox
    patch = scene.filter(ImageFilter.GaussianBlur(radius=radius)).crop((x, y, x + width, y + height))
    mask = Image.new("L", (width, height), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, width - 1, height - 1), radius=corner_radius, fill=255)
    patch.putalpha(mask)
    destination.parent.mkdir(parents=True, exist_ok=True)
    patch.save(destination)


def _prepare_contract_package(output_dir: Path) -> Path:
    """Stage immutable sources plus generated blur layers inside the run."""
    package = output_dir / "contract_package"
    assets = package / "assets"
    for _symbol, _kind, hint in SHARED_ASSETS:
        source = ASSET_ROOT / hint
        if not source.is_file():
            continue
        destination = assets / hint
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    design = PACKAGE_ROOT / "designs" / "home" / "home_default.png"
    design_copy = package / "designs" / "home_default.png"
    design_copy.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(design, design_copy)

    bg_home = ASSET_ROOT / "backgrounds" / "background_home.png"
    bg_push = ASSET_ROOT / "backgrounds" / "background_affirmation_favorited.png"
    pet = ASSET_ROOT / "characters" / "character_pet_idle.png"
    spirit = ASSET_ROOT / "characters" / "character_loading_spirit.png"
    _write_blur_patch(
        assets / "generated" / "blur_home_card.png", background=bg_home,
        foreground=pet, foreground_xy=(96, 124), bbox=(40, 544, 400, 187),
    )
    _write_blur_patch(
        assets / "generated" / "blur_push_card.png", background=bg_push,
        foreground=pet, foreground_xy=(96, 124), bbox=(40, 543, 400, 187),
    )
    _write_blur_patch(
        assets / "generated" / "blur_status_card.png", background=bg_home,
        foreground=spirit, foreground_xy=(145, 227), bbox=(40, 544, 400, 187),
    )
    return package


def _page_nodes(page_id: str) -> tuple[Path, list[dict[str, Any]], list[dict[str, Any]]]:
    root = [{"id": "root", "type": "screen", "full_screen_tap": True}]
    common = [_image("background", "UI_IMG_BG_HOME", [0, 0, 480, 800]), *_status_bar()]
    if page_id == "home_default":
        nodes = root + common + [
            _image("pet", "UI_IMG_PET_IDLE", [96, 124, 305, 428]),
            _image("message_blur", "UI_IMG_BLUR_HOME_CARD", [40, 544, 400, 187]),
            _image("message_card", "UI_IMG_TEXT_CARD", [40, 544, 400, 187], image_fit="stretch"),
            _label("hello", "Hello", [61, 572, 150, 48], "ui_font_top_40", 40),
            _label("message", "I'm your healing companion.\nPlease complete the binding in the App.", [61, 621, 350, 90], "ui_font_hint_24", 24),
        ]
        return PACKAGE_ROOT / "designs" / "home" / "home_default.png", nodes, []
    if page_id == "push_interactive_favorited":
        nodes = root + [_image("background", "UI_IMG_BG_AFFIRMATION", [0, 0, 480, 800]), *_status_bar()] + [
            _image("pet", "UI_IMG_PET_IDLE", [96, 124, 305, 428]),
            _label("affirmation", "I am completely\nforgiven-past,\npresent, and\nfuture.", [90, 138, 300, 176], "ui_font_top_40", 40, "center"),
            _image("mood_blur", "UI_IMG_BLUR_PUSH_CARD", [40, 543, 400, 187]),
            _image("mood_card", "UI_IMG_TEXT_CARD", [40, 543, 400, 187], image_fit="stretch"),
            _label("mood_prompt", "How's your mood\ntoday?", [90, 534, 300, 90], "ui_font_action_36", 36, "center"),
            _mood_button("mood_calm_button", [64, 636, 70, 70]),
            _mood_button("mood_good_button", [154, 636, 70, 70]),
            _mood_button("mood_down_button", [244, 636, 70, 70]),
            _mood_button("mood_stressed_button", [334, 636, 70, 70]),
            _image("mood_calm", "UI_IMG_MOOD_CALM", [81, 653, 37, 37]),
            _image("mood_good", "UI_IMG_MOOD_GOOD", [169, 651, 40, 40]),
            _image("mood_down", "UI_IMG_MOOD_DOWN", [259, 651, 40, 40]),
            _image("mood_stressed", "UI_IMG_MOOD_STRESSED", [349, 651, 40, 40]),
        ]
        return PACKAGE_ROOT / "designs" / "push" / "push_interactive_favorited.png", nodes, []
    if page_id == "home_schedule":
        root[0]["styles"] = {"bg_color": "#FFFAF5", "bg_opa": 255}
        nodes = root + [
            _image("back", "UI_IMG_BACK", [18, 9, 48, 48]),
            _image("battery", "UI_IMG_BATTERY", [408, 8, 48, 48]),
            _label("title", "Schedule", [120, 76, 240, 48], "ui_font_top_36", 36, "center", "#70563C"),
            _image("heading_left", "UI_IMG_SCHEDULE_DECORATION", [74, 136, 14, 18]),
            _label("subtitle", "Your gentle rhythm for the day", [94, 133, 292, 30], "ui_font_title_20", 20, "center", "#876846"),
            _image("heading_right", "UI_IMG_SCHEDULE_DECORATION", [393, 136, 14, 18]),
            {"id": "timeline_line", "type": "container", "parent_id": "root", "source_bbox": [67, 185, 346, 2], "styles": {"bg_color": "#D6C6B5", "bg_opa": 255, "radius": 1}},
            _dot("timeline_0700", [57, 176, 20, 20], "#E8E0D6", border_color="#D1C5B7"),
            _dot("timeline_1000", [172, 176, 20, 20], "#E8E0D6", border_color="#D1C5B7"),
            _dot("timeline_1200", [287, 176, 20, 20], "#C9986C", border_color="#F1DDC8"),
            _dot("timeline_1400", [402, 176, 20, 20], "#E8E0D6", border_color="#D1C5B7"),
            _label("time_0700", "7:00", [50, 199, 40, 22], "ui_font_hint_18", 18, "center", "#B9AA9A"),
            _label("time_1000", "10:00", [163, 199, 40, 22], "ui_font_hint_18", 18, "center", "#B9AA9A"),
            _label("time_1200", "12:00", [277, 199, 40, 22], "ui_font_hint_18", 18, "center", "#98734F"),
            _label("time_1400", "14:00", [392, 199, 40, 22], "ui_font_hint_18", 18, "center", "#B9AA9A"),
            # Keep all supplied canvases at their native 464x564 size.  The
            # neighbouring cards intentionally overflow the 480px screen.
            _image("card_previous", "UI_IMG_REC_01", [-448, 235, 464, 564]),
            _image("card_next", "UI_IMG_REC_03", [464, 235, 464, 564]),
            _image("card_current", "UI_IMG_REC_02", [8, 235, 464, 564]),
            _label("card_time", "12:00", [69, 271, 100, 30], "ui_font_title_20", 20),
            _label("card_date", "May 30", [69, 299, 100, 25], "ui_font_hint_18", 18),
            _label("card_title", "Drink Water\nReminder", [69, 362, 310, 92], "ui_font_top_36", 36),
            _dot("dot_current", [192, 752, 16, 16], "#B17D4B"),
            _dot("dot_second", [232, 752, 16, 16], "#E5D3BE"),
            _dot("dot_third", [272, 752, 16, 16], "#E5D3BE"),
        ]
        return PACKAGE_ROOT / "designs" / "home" / "home_schedule.png", nodes, []
    if page_id == "status_device_initial":
        nodes = root + common + [
            _image("loading_spirit", "UI_IMG_LOADING_SPIRIT", [145, 227, 189, 284]),
            _image("message_blur", "UI_IMG_BLUR_STATUS_CARD", [40, 544, 400, 187]),
            _image("message_card", "UI_IMG_TEXT_CARD", [40, 544, 400, 187], image_fit="stretch"),
            _label("hello", "Hello", [61, 572, 150, 48], "ui_font_top_40", 40),
            _label("message", "I'm your healing companion.\nPlease complete the binding in the App.", [61, 621, 350, 90], "ui_font_hint_24", 24),
        ]
        return PACKAGE_ROOT / "designs" / "status" / "status_device_initial.png", nodes, [
            {"design_family": "status_firmware_*|status_network_*", "blocking": False, "reason": "state-specific panels and progress art are not available as approved cut assets", "required_action": "crop each panel/state icon from its complete design before generating that state"},
        ]
    raise ValueError(f"unsupported page: {page_id}")


def _font_scene(nodes: list[dict[str, Any]]) -> dict[str, Any]:
    role_text: dict[str, list[str]] = {"top": [], "action": [], "title": [], "hint": []}
    role_size: dict[str, int] = {"top": 40, "action": 36, "title": 20, "hint": 18}
    for node in (item for item in nodes if item["type"] == "label"):
        styles = node.get("styles", {})
        font_id = str(styles.get("font_id", ""))
        role = "top" if "_top_" in font_id else "action" if "_action_" in font_id else "title" if "_title_" in font_id else "hint"
        role_text[role].append(str(node.get("text", "")))
        role_size[role] = int(styles.get("text_font_size", role_size[role]))
    return {
        "copy": {role: "\n".join(text) for role, text in role_text.items()},
        "font_sources": {
            "top": str(FONT_SOURCE),
            "action": str(FONT_SOURCE),
            "title": str(FONT_REGULAR_SOURCE),
            "hint": str(FONT_REGULAR_SOURCE),
        },
        "analysis": {"text": {
            "top_prompt": {"font": role_size["top"]},
            "action": {"font": role_size["action"]},
            "title": {"font": role_size["title"]},
            "hint": {"font": role_size["hint"]},
        }},
    }


def _copy_runtime_sources(source_dir: Path, target_dir: Path) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    for path in source_dir.glob("*.h"):
        shutil.copy2(path, target_dir / path.name)
    for path in source_dir.glob("*.c"):
        shutil.copy2(path, target_dir / path.name)


def _all_page_inventory(bound_pages: set[str], page_data: dict[str, tuple[Path, list[dict[str, Any]], list[dict[str, Any]]]]) -> list[dict[str, Any]]:
    """Inventory every supplied design, never silently assigning a guessed cut."""
    rows: list[dict[str, Any]] = []
    for design in sorted((PACKAGE_ROOT / "designs").rglob("*.png")):
        if design.name == "debug_overlay.png":
            continue
        page_id = design.stem
        if page_id in bound_pages:
            _, nodes, gaps = page_data[page_id]
            rows.append({
                "id": page_id, "design_reference": design.relative_to(PACKAGE_ROOT).as_posix(),
                "status": "manual_required" if any(gap.get("blocking") for gap in gaps) else "semantic_bound",
                "asset_symbols": sorted({node["src"] for node in nodes if node["type"] == "image"}),
                "manual_asset_gaps": gaps,
            })
            continue
        family = design.parent.name
        reason = "requires a visual review and explicit asset bindings before generation"
        if family == "status":
            reason = "requires explicit state-panel and progress-art crops from this design"
        elif family == "push":
            reason = "requires a page-specific background and content-card cuts from this design"
        rows.append({
            "id": page_id, "design_reference": design.relative_to(PACKAGE_ROOT).as_posix(),
            "status": "manual_required", "asset_symbols": [],
            "manual_asset_gaps": [{"reason": reason, "required_action": "review, crop, name, and approve the runtime assets"}],
        })
    return rows


def build(output_dir: Path, pages: list[str], max_flash_bytes: int = DEFAULT_MAX_FLASH_BYTES) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    artifacts_root = (ROOT / "artifacts").resolve()
    if not output_dir.is_relative_to(artifacts_root):
        raise ValueError(f"output_dir must be under {artifacts_root}")
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    matrix: dict[str, Any] = {"schema_version": "1.0", "display": DISPLAY, "pages": []}
    page_data: dict[str, tuple[Path, list[dict[str, Any]], list[dict[str, Any]]]] = {}
    for page_id in pages:
        page_data[page_id] = _page_nodes(page_id)
        design, nodes, gaps = page_data[page_id]
    matrix["pages"] = _all_page_inventory(set(pages), page_data)
    (output_dir / "asset_matrix.json").write_text(json.dumps(matrix, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    contract_package = _prepare_contract_package(output_dir)
    intents = [
        {
            "symbol": symbol,
            "type": kind,
            "file_hint": hint,
            "confidence": 1.0,
            "preserve_source_canvas": True,
        }
        for symbol, kind, hint in SHARED_ASSETS
    ]
    initial = build_initial_manifest(
        project="semantic_ui_validation", design_reference="designs/home_default.png", display=DISPLAY,
        assets=intents, asset_root="assets", max_flash_bytes=max_flash_bytes,
    )
    manifest_path = output_dir / "initial_asset_manifest.json"
    initial_result = write_initial_manifest(manifest_path, initial)
    if not initial_result["ok"]:
        return initial_result
    assets_dir = output_dir / "assets"
    asset_result = resolve_asset_contract(
        manifest_path, package_root=contract_package,
        asset_root=contract_package / "assets", output_dir=assets_dir,
    )
    if not asset_result["ok"]:
        return asset_result

    results: list[dict[str, Any]] = []
    for page_id, (design, nodes, gaps) in page_data.items():
        blockers = [gap for gap in gaps if gap.get("blocking")]
        if blockers:
            results.append({"page": page_id, "status": "manual_required", "design": str(design), "manual_asset_gaps": blockers})
            continue
        page_dir = output_dir / page_id
        font_dir = page_dir / "fonts"
        font_dir.mkdir(parents=True, exist_ok=True)
        font_sources, font_previews, plan, warnings = _generate_ttf_font_subsets(_font_scene(nodes), FONT_SOURCE, font_dir)
        if warnings or not font_sources:
            return {"ok": False, "status": "font_generation_failed", "page": page_id, "warnings": warnings}
        font_header, _ = _write_font_bundle(font_dir, font_sources)
        spec = {
            "schema_version": "2.0", "page_name": page_id, "display": {"width": 480, "height": 800}, "lvgl_version": "v9",
            "metadata": {"design_reference": str(design), "matrix": str(output_dir / "asset_matrix.json"), "manual_asset_gaps": gaps},
            "asset_bundle": {"header": "ui_auto_assets.h"}, "font_bundle": {"header": font_header.name}, "fonts": font_previews,
            "nodes": nodes, "events": [{"node_id": "root", "event_type": "clicked"}],
        }
        spec_path = page_dir / "ui_spec.json"
        page_dir.mkdir(parents=True, exist_ok=True)
        spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        generated = generate_page_code(spec)
        if not generated["ok"]:
            return {"ok": False, "status": "codegen_failed", "page": page_id, "errors": generated["errors"]}
        firmware = page_dir / "firmware"
        _copy_runtime_sources(assets_dir, firmware)
        _copy_runtime_sources(font_dir, firmware)
        (firmware / f"ui_page_{page_id}.c").write_text(generated["c_code"], encoding="utf-8", newline="\n")
        (firmware / f"ui_page_{page_id}.h").write_text(generated["h_code"], encoding="utf-8", newline="\n")
        results.append({
            "page": page_id,
            "design": str(design),
            "spec": str(spec_path),
            "firmware": str(firmware),
            "font_plan": plan,
            "warnings": warnings,
        })
    unresolved = [result for result in results if result.get("status") == "manual_required"]
    summary = {
        "ok": not unresolved, "status": "manual_required" if unresolved else "ready_for_render",
        "asset_matrix": str(output_dir / "asset_matrix.json"),
        "asset_pack": asset_result["asset_pack_path"], "resource_closure": asset_result["resource_closure"],
        "pages": results, "unresolved_pages": unresolved,
    }
    (output_dir / "build_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def verify(build_result: dict[str, Any], render_dir: Path) -> dict[str, Any]:
    """Run the repeatable compile, native-render and strict visual gates."""
    render_dir = render_dir.resolve()
    artifacts_root = (ROOT / "artifacts").resolve()
    if not render_dir.is_relative_to(artifacts_root):
        raise ValueError(f"render_dir must be under {artifacts_root}")
    pages: list[dict[str, Any]] = []
    for page in build_result.get("pages", []):
        if page.get("status") == "manual_required":
            continue
        page_id = str(page["page"])
        compile_result = validate_directory(str(page["firmware"]), "v9")
        rendered = render_ui({
            "spec_path": page["spec"],
            "output_dir": str(render_dir / page_id),
            "asset_pack_path": build_result["asset_pack"],
            "engine": "lvgl_simulator",
            "lvgl_version": "v9",
            "display": {"width": DISPLAY["width"], "height": DISPLAY["height"]},
        })
        compared: dict[str, Any]
        if rendered.get("ok"):
            compared = compare_ui({
                "actual_path": rendered["render_path"],
                "baseline_path": page["design"],
                "spec_path": page["spec"],
                "object_tree_path": rendered.get("object_tree_json_path"),
                "threshold_profile": "golden_strict",
            })
        else:
            compared = {
                "ok": False,
                "status": "render_failed",
                "errors": rendered.get("errors", ["native render failed"]),
            }
        pages.append({
            "page": page_id,
            "compile": compile_result,
            "render": rendered,
            "compare": compared,
        })
    result = {
        "ok": bool(pages) and all(
            page["compile"].get("ok")
            and page["render"].get("ok")
            and page["compare"].get("ok")
            for page in pages
        ),
        "threshold_profile": "golden_strict",
        "pages": pages,
    }
    render_dir.mkdir(parents=True, exist_ok=True)
    (render_dir.parent / "render_compare_summary.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "artifacts" / "multipage_ui" / "semantic_validation")
    parser.add_argument("--page", action="append", choices=["home_default", "home_schedule", "push_interactive_favorited", "status_device_initial"])
    parser.add_argument("--max-flash-bytes", type=int, default=DEFAULT_MAX_FLASH_BYTES)
    parser.add_argument("--verify", action="store_true", help="run static compile, authoritative native render, and golden-strict visual comparison")
    parser.add_argument("--render-dir", type=Path, default=ROOT / "artifacts" / "multipage_ui" / "render")
    args = parser.parse_args()
    result = build(args.output_dir, args.page or ["home_default", "home_schedule", "push_interactive_favorited", "status_device_initial"], args.max_flash_bytes)
    if args.verify and result.get("ok"):
        result = {"build": result, "verification": verify(result, args.render_dir)}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    passed = result.get("ok") if "build" not in result else result["build"].get("ok") and result["verification"].get("ok")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
