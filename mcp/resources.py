from __future__ import annotations

import json
from typing import Any

try:
    from schemas import DISPLAY_CONFIG, REGRESSION_SANDBOX_CONFIG
except ImportError:  # pragma: no cover - package import fallback
    from .schemas import DISPLAY_CONFIG, REGRESSION_SANDBOX_CONFIG

REGRESSION_SANDBOX_README = """# LVGL Regression Sandbox

Use this sandbox to build generated LVGL UI code, run it in a PC simulator,
and compare screenshots/logs against a baseline.

Flow:
1. `prepare_lvgl_regression_sandbox` creates an isolated sandbox workspace.
2. `build_lvgl_regression_sandbox` configures/builds it with CMake.
3. `run_lvgl_regression_sandbox` runs the executable and captures logs.
4. `compare_lvgl_screenshot` compares actual vs baseline PPM/BMP/PNG images.
5. `lvgl_render` builds/runs one LVGL snippet and returns PNG + object-tree JSON.
6. `run_lvgl_ui_regression` calls `lvgl_render`, then checks pixels, structure, and logs.

The template is source-only. Build outputs, screenshots, and accepted baselines
belong in caller work directories. `lvgl_render` reuses `cache_dir` for the
prepared sandbox, snippet source, and CMake build cache by default.
"""

THEME_SKILL = """# LVGL Theme/Layout Skill

Use `lvgl://display-config` as the first source of truth for resolution,
color depth, LVGL version, fonts, and asset format.

Hard rules:
- Prefer Flex or Grid for generated page layout.
- Do not use `lv_obj_set_pos`, `lv_obj_set_x`, or `lv_obj_set_y` unless the
  code includes `LVGL_LAYOUT_EXCEPTION: <reason>` immediately above the call.
- Reuse `lv_style_t` objects for repeated typography, card, button, and image
  styles. Avoid many one-off `lv_obj_set_style_*` calls.
- Keep image assets behind generated descriptors or a common resource layer.
- All LVGL object mutation must run on the LVGL/UI task or through
  `lv_async_call`/project equivalent.
- Each generated page root should reserve a custom-event listener for server
  updates and unknown project events. Network/MQTT/HTTP threads should post
  through the generated async helper instead of calling LVGL APIs directly.

Default page structure:
1. root screen/container sized from display config.
2. optional header/content/footer containers.
3. Flex rows/columns for repeated cards/buttons.
4. Grid only when alignment depends on fixed tracks.
5. explicit exception list for every absolute coordinate.
"""

RESOURCE_SCHEMAS: list[dict[str, Any]] = [
    {
        "uri": "lvgl://display-config",
        "name": "LVGL display config",
        "description": "Default LVGL display, font, layout, and asset policy for UI generation.",
        "mimeType": "application/json",
    },
    {
        "uri": "lvgl://theme-skill",
        "name": "LVGL theme/layout skill",
        "description": "Flex/Grid-first LVGL layout instructions for design-to-UI generation.",
        "mimeType": "text/markdown",
    },
    {
        "uri": "lvgl://regression-sandbox-config",
        "name": "LVGL regression sandbox config",
        "description": "Default build, run, screenshot, and log-scan policy for LVGL UI regression.",
        "mimeType": "application/json",
    },
    {
        "uri": "lvgl://regression-sandbox-readme",
        "name": "LVGL regression sandbox README",
        "description": "MCP usage flow for the LVGL UI rendering and regression sandbox.",
        "mimeType": "text/markdown",
    },
]

RESOURCE_URIS = {item["uri"] for item in RESOURCE_SCHEMAS}

def get_resource_content(uri: str) -> dict[str, Any]:
    if uri == "lvgl://display-config":
        return {"uri": uri, "mimeType": "application/json", "text": json.dumps(DISPLAY_CONFIG, ensure_ascii=False, indent=2)}
    if uri == "lvgl://theme-skill":
        return {"uri": uri, "mimeType": "text/markdown", "text": THEME_SKILL}
    if uri == "lvgl://regression-sandbox-config":
        return {"uri": uri, "mimeType": "application/json", "text": json.dumps(REGRESSION_SANDBOX_CONFIG, ensure_ascii=False, indent=2)}
    if uri == "lvgl://regression-sandbox-readme":
        return {"uri": uri, "mimeType": "text/markdown", "text": REGRESSION_SANDBOX_README}
    raise ValueError(f"unknown resource: {uri}")

def get_lvgl_theme_skill(_: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "ok": True,
        "uri": "lvgl://theme-skill",
        "display_config_uri": "lvgl://display-config",
        "content": THEME_SKILL,
        "display_config": DISPLAY_CONFIG,
    }

__all__ = [
    "RESOURCE_SCHEMAS",
    "RESOURCE_URIS",
    "get_lvgl_theme_skill",
    "get_resource_content",
]
