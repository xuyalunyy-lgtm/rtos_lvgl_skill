import json

from mcp.app_v21_codegen import generate_app_c, generate_presenter_c, generate_router_c
from mcp.high_level_tools import _json_safe_value
from mcp.lvgl_codegen import generate_page_code


PAGES = [{"id": "home"}, {"id": "detail"}]
ROUTES = [{"id": "next_home", "from": "home", "to": "detail", "mode": "replace"}]


def test_v21_generated_sources_include_sibling_directories() -> None:
    router = generate_router_c(PAGES)
    presenter = generate_presenter_c(
        {"id": "home", "events": []}, ROUTES, [{"name": "prefs", "fields": []}],
    )
    app = generate_app_c("home", [{"name": "prefs", "fields": []}])

    assert '#include "../pages/home/ui_page_home.h"' in router
    assert '#include "../presenters/presenter_home.h"' in router
    assert '#include "../app/ui_router.h"' in presenter
    assert '#include "../models/model_prefs.h"' in presenter
    assert '#include "../models/model_prefs.h"' in app


def test_v21_router_factory_uses_owned_root_and_active_page_handles() -> None:
    router = generate_router_c(PAGES)

    assert "candidate = ui_page_home_create(s_root);" in router
    assert "ui_page_home_destroy(candidate);" in router
    assert "ui_page_home_destroy(s_active);" in router
    assert "presenter_home_on_enter(s_active);" in router
    assert "ui_page_home_create(parent)" not in router
    assert "ui_page_home_destroy(root)" not in router
    assert "presenter_home_on_enter(root)" not in router


def test_screen_node_is_router_owned_and_can_receive_taps() -> None:
    result = generate_page_code({
        "schema_version": "2.0",
        "page_name": "tap_page",
        "display": {"width": 480, "height": 800},
        "lvgl_version": "v9",
        "nodes": [{"id": "root", "type": "screen", "full_screen_tap": True}],
    })

    assert result["ok"], result
    assert "s_root = lv_obj_create(root);" in result["c_code"]
    assert "lv_obj_set_size(s_root, LV_PCT(100), LV_PCT(100));" in result["c_code"]
    assert "lv_obj_add_flag(s_root, LV_OBJ_FLAG_CLICKABLE);" in result["c_code"]


def test_page_codegen_binds_asset_descriptors_and_source_bboxes() -> None:
    result = generate_page_code({
        "schema_version": "2.0",
        "page_name": "asset_page",
        "display": {"width": 480, "height": 800},
        "lvgl_version": "v9",
        "asset_bundle": {"header": "ui_auto_assets.h"},
        "font_bundle": {"header": "ui_auto_fonts.h"},
        "nodes": [
            {"id": "root", "type": "screen"},
            {
                "id": "background", "type": "image", "parent_id": "root",
                "src": "UI_IMG_BG_HOME", "src_expr": "&UI_IMG_BG_HOME",
                "source_bbox": [0, 0, 480, 800],
            },
            {
                "id": "resizable_card", "type": "image", "parent_id": "root",
                "src": "UI_IMG_CARD", "src_expr": "&UI_IMG_CARD",
                "source_bbox": [40, 500, 360, 150], "image_fit": "stretch",
            },
            {
                "id": "title", "type": "label", "parent_id": "root", "text": "Hello",
                "source_bbox": [20, 40, 120, 30],
                "styles": {"font": "&ui_font_title_20"},
            },
        ],
    })

    assert result["ok"], result
    code = result["c_code"]
    assert '#include "ui_auto_assets.h"' in code
    assert '#include "ui_auto_fonts.h"' in code
    assert "lv_image_set_src(s_background, &UI_IMG_BG_HOME);" in code
    assert "lv_image_set_inner_align(s_resizable_card, LV_IMAGE_ALIGN_STRETCH);" in code
    assert '#define UI_IMG_BG_HOME "UI_IMG_BG_HOME"' not in code
    assert "lv_obj_set_pos(s_background, 0, 0);" in code
    assert "lv_obj_set_size(s_title, 120, 30);" in code
    assert "lv_obj_set_style_text_font(s_title, &ui_font_title_20, 0);" in code


def test_page_codegen_retains_offscreen_carousel_source_bboxes() -> None:
    result = generate_page_code({
        "schema_version": "2.0", "page_name": "schedule", "display": {"width": 480, "height": 800},
        "lvgl_version": "v9", "nodes": [
            {"id": "root", "type": "screen"},
            {"id": "previous", "type": "image", "parent_id": "root", "src": "UI_IMG_REC_01",
             "src_expr": "&UI_IMG_REC_01", "source_bbox": [-448, 235, 464, 564]},
        ],
    })

    assert result["ok"], result
    assert "lv_obj_set_pos(s_previous, -448, 235);" in result["c_code"]
    assert "lv_obj_set_size(s_previous, 464, 564);" in result["c_code"]


def test_mcp_result_normalizes_validator_sets_for_json_rpc() -> None:
    result = _json_safe_value({"route_graph": {"reachable": {"home", "detail"}}})

    assert result["route_graph"]["reachable"] == ["detail", "home"]
    json.dumps(result)
