"""LVGL MCP resources."""
from __future__ import annotations

try:
    from codegen import RESOURCE_SCHEMAS, RESOURCE_URIS, get_lvgl_theme_skill, get_resource_content
except ImportError:  # pragma: no cover - package import fallback
    from .codegen import RESOURCE_SCHEMAS, RESOURCE_URIS, get_lvgl_theme_skill, get_resource_content


__all__ = [
    "RESOURCE_SCHEMAS",
    "RESOURCE_URIS",
    "get_lvgl_theme_skill",
    "get_resource_content",
]
