"""Single source of truth for LVGL pipeline capabilities."""
from __future__ import annotations

from copy import deepcopy
from typing import Any


CAPABILITIES: dict[str, dict[str, Any]] = {
    "v8": {
        "codegen": True,
        "static_compile": True,
        "python_preview": True,
        "native_render": False,
        "native_render_authoritative": False,
        "native_render_reason": "The bundled native simulator currently supports LVGL v9 only.",
    },
    "v9": {
        "codegen": True,
        "static_compile": True,
        "python_preview": True,
        "native_render": True,
        "native_render_authoritative": True,
        "native_render_reason": "Bundled native simulator available.",
    },
}


def get_capabilities(lvgl_version: str) -> dict[str, Any]:
    """Return a copy so callers cannot mutate the registry."""
    if lvgl_version not in CAPABILITIES:
        raise ValueError(f"Unsupported LVGL version: {lvgl_version}")
    return {"lvgl_version": lvgl_version, **deepcopy(CAPABILITIES[lvgl_version])}


def verification_plan(lvgl_version: str) -> dict[str, Any]:
    """Describe the strongest validation chain available for a target version."""
    capability = get_capabilities(lvgl_version)
    if capability["native_render"]:
        return {
            "authoritative": True,
            "steps": ["static_compile", "native_render", "visual_compare"],
            "fallback": "python_preview is diagnostic only and cannot verify visual fidelity.",
        }
    return {
        "authoritative": False,
        "steps": ["static_compile", "python_preview"],
        "capability_gap": capability["native_render_reason"],
        "fallback": "Run native rendering against an integrator-provided LVGL v8 harness for visual acceptance.",
    }
