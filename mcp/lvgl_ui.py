"""Aggregated LVGL MCP surface.

The implementation is split by responsibility:
- schemas.py: public schemas and static config
- resources.py: MCP resources
- assets.py: image/font asset helpers
- codegen.py: LVGL layout and source generation
- regression.py: simulator, render, and comparison helpers
"""
from __future__ import annotations

try:
    from assets import convert_assets_to_lvgl, convert_image_to_lvgl_source, generate_font_glyph
    from codegen import (
        analyze_layout_and_patch,
        generate_initial_loading_page,
        generate_interactive_scene_page,
        generate_lvgl_layout_spec,
        generate_lvgl_page_code,
        validate_lvgl_layout_code,
    )
    from regression import (
        build_lvgl_regression_sandbox,
        compare_lvgl_object_tree,
        compare_lvgl_screenshot,
        list_lvgl_regression_artifacts,
        lvgl_render,
        prepare_lvgl_regression_sandbox,
        prepare_lvgl_sim_project,
        run_lvgl_regression_sandbox,
        run_lvgl_ui_regression,
    )
    from resources import RESOURCE_SCHEMAS, RESOURCE_URIS, get_lvgl_theme_skill, get_resource_content
    from schemas import LVGL_TOOL_SCHEMAS
except ImportError:  # pragma: no cover - package import fallback
    from .assets import convert_assets_to_lvgl, convert_image_to_lvgl_source, generate_font_glyph
    from .codegen import (
        analyze_layout_and_patch,
        generate_initial_loading_page,
        generate_interactive_scene_page,
        generate_lvgl_layout_spec,
        generate_lvgl_page_code,
        validate_lvgl_layout_code,
    )
    from .regression import (
        build_lvgl_regression_sandbox,
        compare_lvgl_object_tree,
        compare_lvgl_screenshot,
        list_lvgl_regression_artifacts,
        lvgl_render,
        prepare_lvgl_regression_sandbox,
        prepare_lvgl_sim_project,
        run_lvgl_regression_sandbox,
        run_lvgl_ui_regression,
    )
    from .resources import RESOURCE_SCHEMAS, RESOURCE_URIS, get_lvgl_theme_skill, get_resource_content
    from .schemas import LVGL_TOOL_SCHEMAS


LVGL_TOOLS = {
    "get_lvgl_theme_skill": get_lvgl_theme_skill,
    "convert_image_to_lvgl_source": convert_image_to_lvgl_source,
    "generate_lvgl_layout_spec": generate_lvgl_layout_spec,
    "generate_lvgl_page_code": generate_lvgl_page_code,
    "generate_initial_loading_page": generate_initial_loading_page,
    "generate_interactive_scene_page": generate_interactive_scene_page,
    "generate_font_glyph": generate_font_glyph,
    "convert_assets_to_lvgl": convert_assets_to_lvgl,
    "analyze_layout_and_patch": analyze_layout_and_patch,
    "validate_lvgl_layout_code": validate_lvgl_layout_code,
    "prepare_lvgl_sim_project": prepare_lvgl_sim_project,
    "prepare_lvgl_regression_sandbox": prepare_lvgl_regression_sandbox,
    "build_lvgl_regression_sandbox": build_lvgl_regression_sandbox,
    "run_lvgl_regression_sandbox": run_lvgl_regression_sandbox,
    "compare_lvgl_screenshot": compare_lvgl_screenshot,
    "compare_lvgl_object_tree": compare_lvgl_object_tree,
    "lvgl_render": lvgl_render,
    "run_lvgl_ui_regression": run_lvgl_ui_regression,
    "list_lvgl_regression_artifacts": list_lvgl_regression_artifacts,
}


__all__ = [
    "LVGL_TOOL_SCHEMAS",
    "LVGL_TOOLS",
    "RESOURCE_SCHEMAS",
    "RESOURCE_URIS",
    "get_resource_content",
]
