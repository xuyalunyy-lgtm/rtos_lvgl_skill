import json
from pathlib import Path

from PIL import Image

from mcp import high_level_tools, lvgl_run
from mcp.page_input import (
    build_page_input_template,
    load_page_input,
    page_input_to_asset_intents,
    page_input_to_decisions,
    page_input_to_spec,
    validate_page_input,
    write_page_input,
)


def _confirmed_payload() -> dict:
    payload = build_page_input_template(
        design_path="schedule.png",
        display={"width": 480, "height": 800},
        asset_intents=[{
            "symbol": "schedule_card",
            "type": "decorative_image",
            "file_hint": "daily_recommendation_02.png",
            "estimated_bbox": [8, 218, 464, 564],
            "preserve_source_canvas": True,
            "allow_shared_source": True,
        }],
    )
    payload["status"] = "confirmed"
    payload["fonts"] = [{"role": "title", "source": "InriaSerif-Bold.ttf", "size": 40}]
    payload["elements"] = [{
        "id": "page_title",
        "type": "label",
        "text": "Schedule",
        "bbox": [0, 73, 480, 52],
        "font_role": "title",
        "styles": {"text_color": "#6B5137", "text_align": "center"},
    }]
    payload["interactions"] = {
        "transition": "next_page",
        "targets": ["screen"],
        "persistent_state": [],
    }
    return payload


def test_template_is_user_editable_and_preserves_candidates(tmp_path: Path) -> None:
    payload = _confirmed_payload()
    path = write_page_input(tmp_path / "page_input.json", payload)
    loaded = load_page_input(path)

    assert json.loads(Path(path).read_text(encoding="utf-8"))["display"] == [480, 800]
    assert loaded["assets"][0]["bbox"] == [8, 218, 464, 564]
    assert loaded["assets"][0]["preserve_canvas"] is True
    assert loaded["assets"][0]["reuse_scope"] == "shared"
    assert validate_page_input(loaded)["ok"]


def test_draft_or_incomplete_page_input_is_blocked() -> None:
    payload = build_page_input_template(
        design_path="screen.png",
        display={"width": 480, "height": 800},
        asset_intents=None,
    )
    validation = validate_page_input(payload)
    assert not validation["ok"]
    assert "status must be 'confirmed' after user review" in validation["errors"]
    assert "assets must contain at least one confirmed asset" in validation["errors"]


def test_page_input_rejects_codegen_injection_and_generated_node_collisions() -> None:
    payload = _confirmed_payload()
    payload["elements"][0]["styles"]["border_width"] = "0); injected_call();"
    payload["elements"][0]["text_macro"] = "BAD\n#define INJECTED"
    payload["elements"].append({
        "id": "asset_schedule_card",
        "type": "container",
        "bbox": [0, 0, 1, 1],
        "styles": {},
    })

    validation = validate_page_input(payload)
    assert not validation["ok"]
    assert "elements[0].styles.border_width must be a non-negative integer" in validation["errors"]
    assert "elements[0].text_macro must be an uppercase C identifier" in validation["errors"]
    assert "elements[1].id collides with a generated node" in validation["errors"]


def test_confirmed_page_input_adapts_to_existing_contracts() -> None:
    payload = _confirmed_payload()
    intents = page_input_to_asset_intents(payload)
    decisions = page_input_to_decisions(payload)

    assert intents[0]["file_hint"] == "daily_recommendation_02.png"
    assert intents[0]["preserve_source_canvas"] is True
    assert decisions["asset:schedule_card"]["size_policy"] == "native"
    assert decisions["font_policy"]["source"] == "InriaSerif-Bold.ttf"


def test_confirmed_page_input_converts_assets_and_fonts_to_ui_spec() -> None:
    payload = _confirmed_payload()
    payload["assets"][0]["scale"] = "stretch"
    spec = page_input_to_spec(
        payload,
        asset_header="ui_auto_assets.h",
        font_header="ui_schedule_fonts.h",
        font_symbols={"title": "ui_font_schedule_title_40"},
    )

    image = next(node for node in spec["nodes"] if node["type"] == "image")
    label = next(node for node in spec["nodes"] if node["type"] == "label")
    assert image["src"] == "schedule_card"
    assert image["src_expr"] == "&schedule_card"
    assert image["source_bbox"] == [8, 218, 464, 564]
    assert image["image_fit"] == "stretch"
    assert label["styles"]["font"] == "&ui_font_schedule_title_40"
    assert spec["asset_bundle"]["header"] == "ui_auto_assets.h"
    assert spec["font_bundle"]["header"] == "ui_schedule_fonts.h"


def test_inspect_draft_can_be_confirmed_and_reused(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(high_level_tools, "ROOT", tmp_path)
    ui = tmp_path / "ui"
    design = ui / "schedule.png"
    asset_root = ui / "assets"
    asset_root.mkdir(parents=True)
    Image.new("RGB", (48, 80), (250, 248, 242)).save(design)
    Image.new("RGBA", (48, 80), (30, 60, 90, 255)).save(asset_root / "card.png")

    draft = high_level_tools._inspect_design_legacy({
        "design_path": str(design),
        "asset_root": str(asset_root),
        "display": {"width": 48, "height": 80, "color_format": "RGB565"},
        "output_dir": "artifacts/page_input_draft",
    })
    assert draft["ok"] and draft["status"] == "manual_required"
    page_input_path = Path(draft["page_input"])
    payload = json.loads(page_input_path.read_text(encoding="utf-8"))
    payload["status"] = "confirmed"
    payload["assets"] = [{
        "symbol": "schedule_card",
        "type": "decorative_image",
        "source": "card.png",
        "bbox": [0, 0, 48, 80],
        "scale": "original",
        "preserve_canvas": True,
        "page": "schedule",
        "state": "default",
        "layer": "content",
        "reuse_scope": "page",
    }]
    write_page_input(page_input_path, payload)

    confirmed = high_level_tools._inspect_design_legacy({
        "design_path": str(design),
        "asset_root": str(asset_root),
        "display": {"width": 48, "height": 80, "color_format": "RGB565"},
        "page_input_path": str(page_input_path),
        "output_dir": "artifacts/page_input_confirmed",
    })
    assert confirmed["ok"] and confirmed["status"] == "initial_asset_manifest_ready"
    manifest = json.loads(Path(confirmed["initial_asset_manifest"]).read_text(encoding="utf-8"))
    assert manifest["assets"][0]["symbol"] == "schedule_card"
    assert manifest["assets"][0]["estimated_bbox"] == [0, 0, 48, 80]


def test_generate_ui_consumes_confirmed_page_input_and_publishes_compile_closure(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(high_level_tools, "ROOT", tmp_path)
    ui = tmp_path / "ui"
    assets = ui / "assets"
    designs = ui / "designdrawing"
    assets.mkdir(parents=True)
    designs.mkdir(parents=True)
    Image.new("RGB", (48, 80), (250, 248, 242)).save(designs / "schedule.png")
    Image.new("RGBA", (24, 20), (30, 60, 90, 255)).save(assets / "schedule_card.png")

    payload = build_page_input_template(
        design_path="designdrawing/schedule.png",
        display={"width": 48, "height": 80},
        asset_intents=[{
            "symbol": "schedule_card",
            "type": "decorative_image",
            "file_hint": "schedule_card.png",
            "estimated_bbox": [12, 20, 24, 20],
            "preserve_source_canvas": True,
        }],
    )
    payload["status"] = "confirmed"
    payload["elements"] = [{
        "id": "footer_rule",
        "type": "container",
        "bbox": [8, 72, 32, 2],
        "styles": {"bg_color": "#6B5137", "border_width": 0},
    }]
    page_input_path = Path(write_page_input(ui / "page_input.json", payload))

    result = high_level_tools.generate_ui({
        "page_input_path": str(page_input_path),
        "cut_dir": str(assets),
        "output_dir": "artifacts/direct_page_input",
    })

    assert result["ok"] and result["status"] == "generated"
    output = tmp_path / "artifacts" / "direct_page_input"
    assert Path(result["c_path"]).is_file()
    assert Path(result["h_path"]).is_file()
    assert Path(result["cmake_path"]).is_file()
    assert "lv_image_set_src(s_asset_schedule_card, &schedule_card);" in Path(result["c_path"]).read_text(encoding="utf-8")
    assert "schedule_card.c" in Path(result["cmake_path"]).read_text(encoding="utf-8")
    assert not list(output.glob("*.json"))
    assert not list(output.glob("*.pack"))


def test_generate_ui_run_inherits_page_input_and_keeps_render_evidence(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(high_level_tools, "ROOT", tmp_path)
    monkeypatch.setattr(lvgl_run, "RUNS_ROOT", tmp_path / "artifacts" / "runs")
    ui = tmp_path / "ui"
    assets = ui / "assets"
    assets.mkdir(parents=True)
    design = ui / "schedule.png"
    Image.new("RGB", (48, 80), (250, 248, 242)).save(design)
    Image.new("RGBA", (24, 20), (30, 60, 90, 255)).save(assets / "schedule_card.png")
    payload = build_page_input_template(
        design_path="schedule.png",
        display={"width": 48, "height": 80},
        asset_intents=[{
            "symbol": "schedule_card",
            "type": "decorative_image",
            "file_hint": "schedule_card.png",
            "estimated_bbox": [12, 20, 24, 20],
            "preserve_source_canvas": True,
        }],
    )
    payload["status"] = "confirmed"
    page_input_path = Path(write_page_input(ui / "page_input.json", payload))

    inspected = high_level_tools.inspect_design({
        "design_path": str(design),
        "asset_root": str(assets),
        "page_input_path": str(page_input_path),
        "display": {"width": 48, "height": 80},
        "output_dir": "artifacts/run_inspect",
    })
    assert inspected["ok"] and inspected["run_status"] == "inspected"

    generated = high_level_tools.generate_ui({
        "run_id": inspected["run_id"],
        "cut_dir": str(assets),
        "output_dir": "artifacts/run_generate",
    })
    assert generated["ok"] and generated["run_status"] == "generated"
    assert generated["page_input"] == str(page_input_path.resolve())
    assert Path(generated["spec_path"]).is_file()
    assert Path(generated["asset_pack_path"]).is_file()
