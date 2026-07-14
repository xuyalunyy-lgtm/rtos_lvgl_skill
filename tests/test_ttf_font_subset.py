from pathlib import Path

from mcp.standard_ui_package import _font_subset_plan


def test_font_subset_plan_uses_analyzed_text_sizes_and_glyphs() -> None:
    source = Path("ui/fonts/custom.ttf")
    scene_spec = {
        "copy": {
            "top": "AB\nCA",
            "title": "Hello",
            "hint": "Go!",
        },
        "analysis": {
            "text": {
                "top_prompt": {"font": 31.6},
                "title": {"font": 28},
                "hint": {"font": "invalid"},
            }
        },
    }

    plan = _font_subset_plan(scene_spec, source)

    assert [(item["role"], item["size_px"], item["symbol"]) for item in plan] == [
        ("top", 32, "ui_font_top_32"),
        ("title", 28, "ui_font_title_28"),
        ("hint", 30, "ui_font_hint_30"),
    ]
    assert plan[0]["glyph_count"] == 4  # A, B, C, and the line break.
    assert plan[1]["text"] == "Hello"
    assert plan[2]["source"] == str(source)


def test_font_subset_plan_accepts_role_specific_sources() -> None:
    scene_spec = {
        "copy": {"top": "Title", "hint": "Body"},
        "font_sources": {"top": "fonts/bold.ttf", "hint": "fonts/regular.ttf"},
    }

    plan = _font_subset_plan(scene_spec, Path("fonts/fallback.ttf"))

    assert plan[0]["source"] == "fonts/bold.ttf"
    assert plan[1]["source"] == "fonts/regular.ttf"
