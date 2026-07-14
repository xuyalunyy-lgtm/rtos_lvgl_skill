from pathlib import Path

from mcp.codegen import validate_lvgl_layout_code
from mcp.lvgl_codegen import write_page_files


def test_v2_codegen_marks_authored_absolute_coordinates(tmp_path: Path) -> None:
    spec = {
        "schema_version": "2.0",
        "page_name": "positioned_page",
        "display": {"width": 480, "height": 800},
        "lvgl_version": "v9",
        "nodes": [
            {"id": "screen", "type": "screen"},
            {
                "id": "title",
                "type": "label",
                "parent_id": "screen",
                "text": "Title\nLine 2",
                "text_macro": "UI_TEXT_POSITIONED_TITLE",
                "source_bbox": [20, 30, 100, 40],
                "layout_exception_reason": "pixel-matched title bbox",
            },
        ],
    }

    result = write_page_files(spec, tmp_path, "v9")

    assert result["ok"]
    source = Path(result["c_path"]).read_text(encoding="utf-8")
    assert "LVGL_LAYOUT_EXCEPTION: pixel-matched title bbox" in source
    assert '#define UI_TEXT_POSITIONED_TITLE "Title\\nLine 2"' in source
    assert "lv_obj_remove_style_all(root);" in source
    assert "lv_obj_set_pos(root, 0, 0);" in source
    assert "lv_obj_clear_flag(root, LV_OBJ_FLAG_SCROLLABLE);" in source
    assert "lv_obj_remove_style_all(s_screen);" in source
    assert "lv_obj_set_pos(s_screen, 0, 0);" in source
    assert "lv_obj_clear_flag(s_screen, LV_OBJ_FLAG_SCROLLABLE);" in source
    assert validate_lvgl_layout_code({"path": str(tmp_path)})["ok"]
