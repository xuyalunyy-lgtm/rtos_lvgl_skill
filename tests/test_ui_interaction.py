import json
from pathlib import Path

import pytest

from mcp.high_level_schemas import HIGH_LEVEL_SCHEMAS
from mcp.ui_interaction import build_interaction_contract, load_decisions, write_interaction_artifacts


def test_high_interaction_blocks_until_all_asset_and_global_decisions_exist(tmp_path: Path) -> None:
    assets = [{"symbol": "card_left"}, {"symbol": "card_center"}]
    initial = build_interaction_contract(
        mode="high", analysis_questions=["Confirm title alignment"], asset_intents=assets, decisions={}
    )
    assert not initial["ready_for_codegen"]
    assert "coordinate_space" in initial["unresolved_ids"]
    assert "asset:card_left" in initial["unresolved_ids"]
    assert "analysis:1" not in initial["unresolved_ids"]

    decisions = {
        "coordinate_space": {"design_width": 480, "design_height": 800, "display_mapping": "1:1"},
        "bbox_canvas_policy": {"include_transparent_padding": True},
        "font_policy": {"source": "ui.ttf", "match_sizes": True, "fallback": "none", "glyph_scope": "used_text"},
        "interaction_policy": {"transition": "next_page", "targets": ["screen"], "persistent_state": []},
        "asset:card_left": {"page": "home", "state": "default", "layer": "content", "bbox": [0, 235, 464, 564], "size_policy": "native", "reuse_scope": "home"},
        "asset:card_center": {"page": "home", "state": "default", "layer": "content", "bbox": [8, 235, 464, 564], "size_policy": "native", "reuse_scope": "home"},
    }
    ready = build_interaction_contract(
        mode="high", analysis_questions=["Confirm title alignment"], asset_intents=assets, decisions=decisions
    )
    assert ready["ready_for_codegen"]
    assert ready["unresolved_ids"] == []

    contract_path, decisions_path = write_interaction_artifacts(tmp_path, ready, decisions)
    assert json.loads(contract_path.read_text(encoding="utf-8"))["ready_for_codegen"] is True
    assert load_decisions(str(decisions_path), {"font_policy": {"source": "new.ttf"}})["font_policy"] == {"source": "new.ttf"}


def test_placeholder_answers_do_not_bypass_high_interaction_gate() -> None:
    contract = build_interaction_contract(
        mode="high",
        analysis_questions=[],
        asset_intents=[{"symbol": "hero"}],
        decisions={"coordinate_space": {"confirmed": True}, "asset:hero": {"confirmed": True}},
    )
    assert "coordinate_space" in contract["unresolved_ids"]
    assert "asset:hero" in contract["unresolved_ids"]


def test_standard_interaction_is_non_blocking() -> None:
    contract = build_interaction_contract(
        mode="standard", analysis_questions=["Confirm color"], asset_intents=None, decisions={}
    )
    assert contract["ready_for_codegen"]
    assert contract["unresolved_ids"] == []


def test_invalid_decision_file_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "decisions.json"
    path.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="JSON object"):
        load_decisions(str(path), None)


def test_inspect_schema_exposes_high_interaction_inputs() -> None:
    schema = next(item for item in HIGH_LEVEL_SCHEMAS if item["name"] == "inspect_design")
    properties = schema["inputSchema"]["properties"]
    assert properties["interaction_mode"]["enum"] == ["standard", "high"]
    assert "interaction_decisions" in properties
    assert "ui_decisions_path" in properties
    assert "page_input_path" in properties
