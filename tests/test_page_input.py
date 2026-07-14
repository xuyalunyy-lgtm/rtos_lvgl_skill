import json
from pathlib import Path

from PIL import Image

from mcp import high_level_tools
from mcp.page_input import (
    build_page_input_template,
    load_page_input,
    page_input_to_asset_intents,
    page_input_to_decisions,
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
        }],
    )
    payload["status"] = "confirmed"
    payload["fonts"] = [{"role": "title", "source": "InriaSerif-Bold.ttf", "size": 40}]
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


def test_confirmed_page_input_adapts_to_existing_contracts() -> None:
    payload = _confirmed_payload()
    intents = page_input_to_asset_intents(payload)
    decisions = page_input_to_decisions(payload)

    assert intents[0]["file_hint"] == "daily_recommendation_02.png"
    assert intents[0]["preserve_source_canvas"] is True
    assert decisions["asset:schedule_card"]["size_policy"] == "native"
    assert decisions["font_policy"]["source"] == "InriaSerif-Bold.ttf"


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
