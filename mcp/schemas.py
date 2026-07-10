"""LVGL MCP public tool schemas and static config exports."""
from __future__ import annotations

try:
    from codegen import (
        ASSET_INPUT_EXTENSIONS,
        COLOR_FORMATS,
        DEFAULT_FONT_CANDIDATES,
        DISPLAY_CONFIG,
        IMAGE_FORMATS,
        LVGL_TOOL_SCHEMAS,
        LVGL_VERSIONS,
        REGRESSION_SANDBOX_CONFIG,
    )
except ImportError:  # pragma: no cover - package import fallback
    from .codegen import (
        ASSET_INPUT_EXTENSIONS,
        COLOR_FORMATS,
        DEFAULT_FONT_CANDIDATES,
        DISPLAY_CONFIG,
        IMAGE_FORMATS,
        LVGL_TOOL_SCHEMAS,
        LVGL_VERSIONS,
        REGRESSION_SANDBOX_CONFIG,
    )


__all__ = [
    "ASSET_INPUT_EXTENSIONS",
    "COLOR_FORMATS",
    "DEFAULT_FONT_CANDIDATES",
    "DISPLAY_CONFIG",
    "IMAGE_FORMATS",
    "LVGL_TOOL_SCHEMAS",
    "LVGL_VERSIONS",
    "REGRESSION_SANDBOX_CONFIG",
]
