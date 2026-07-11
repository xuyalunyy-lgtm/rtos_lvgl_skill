"""High-level MCP tool schemas for LVGL pipeline.

Exposes exactly 6 tools to the model. All internal complexity
is hidden behind these schemas.
"""
from __future__ import annotations

from typing import Any

# ── Display config schema ─────────────────────────────────────────

DISPLAY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "width": {"type": "integer", "minimum": 1, "maximum": 4096, "default": 480},
        "height": {"type": "integer", "minimum": 1, "maximum": 4096, "default": 800},
        "rotation": {"type": "integer", "enum": [0, 90, 180, 270], "default": 0},
        "color_format": {"type": "string", "enum": ["RGB565", "RGB565A8", "RGB888", "ARGB8888", "A8"], "default": "RGB565"},
    },
    "required": ["width", "height"],
}

# ── Six high-level tool schemas ───────────────────────────────────

HIGH_LEVEL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "inspect_design",
        "description": "Analyze a design screenshot. Returns analysis report, debug overlay, detected regions/colors/text, and confidence scores. Read-only — does not generate code.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "design_path": {"type": "string", "description": "Path to design screenshot (PNG/JPG)"},
                "cut_dir": {"type": "string", "description": "Directory containing cutout assets"},
                "asset_root": {"type": "string", "description": "Physical asset root, normally ui/assets"},
                "project": {"type": "string", "description": "Stable project identifier used by the Initial Manifest"},
                "asset_flash_budget_bytes": {"type": "integer", "minimum": 1, "description": "Optional hardware Flash budget for all resolved image assets"},
                "asset_intents": {
                    "type": "array",
                    "description": "AI visual intent only. Physical paths, dimensions, formats, hashes, strides, and memory sizes are forbidden.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "symbol": {"type": "string", "pattern": "^[A-Za-z_][A-Za-z0-9_]*$", "maxLength": 31},
                            "type": {"type": "string", "enum": ["full_screen_background", "transparent_character", "status_icon", "control_icon", "decorative_image", "state_image"]},
                            "file_hint": {"type": "string"},
                            "required": {"type": "boolean", "default": True},
                            "state": {"type": "string"},
                            "layer": {"type": "string"},
                            "estimated_bbox": {"type": "array", "minItems": 4, "maxItems": 4, "items": {"type": "integer"}},
                            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                            "allow_shared_source": {"type": "boolean", "default": False},
                        },
                        "required": ["symbol", "type", "file_hint"],
                        "additionalProperties": False,
                    },
                },
                "display": DISPLAY_SCHEMA,
                "lvgl_version": {"type": "string", "enum": ["v8", "v9"], "default": "v9"},
                "output_dir": {"type": "string", "default": "artifacts/inspect"},
            },
            "required": ["design_path"],
            "additionalProperties": False,
        },
    },
    {
        "name": "generate_ui",
        "description": "Generate LVGL C/H page code from a UI Spec or design analysis. Produces assets, fonts, code, and static validation. Use after inspect_design.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ui_dir": {"type": "string", "description": "Standard UI package directory; auto-discovers assets/ and fonts/ when manifest.json is absent"},
                "asset_manifest_path": {"type": "string", "description": "Initial asset intent manifest produced by inspect_design"},
                "strict_asset_contract": {"type": "boolean", "default": True, "description": "Reject design-driven generation without a deterministic asset contract"},
                "delivery_mode": {"type": "string", "enum": ["final_only", "full_evidence"], "default": "final_only", "description": "final_only publishes only compilable C/H, used fonts, assets, and CMake; evidence is isolated outside the delivery directory"},
                "manifest_path": {"type": "string", "description": "Path to Manifest v2 JSON for multi-page app generation"},
                "spec_path": {"type": "string", "description": "Path to ui_spec.json (preferred)"},
                "design_path": {"type": "string", "description": "Path to design screenshot (auto-runs inspect if spec_path omitted)"},
                "cut_dir": {"type": "string", "description": "Cutout assets directory"},
                "template": {"type": "string", "enum": ["auto", "interactive_scene", "generic"], "default": "auto", "description": "Use interactive_scene when the design has a scene background, pet cutout, and mood assets"},
                "display": DISPLAY_SCHEMA,
                "lvgl_version": {"type": "string", "enum": ["v8", "v9"], "default": "v9"},
                "output_dir": {"type": "string", "default": "artifacts/generated"},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "render_ui",
        "description": "Render generated LVGL code using a fixed server-side preset. Returns render.png, object tree, and build report. Cannot accept arbitrary executables.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "spec_path": {"type": "string", "description": "Path to UI Spec JSON (required)"},
                "output_dir": {"type": "string", "default": "artifacts/render"},
                "asset_pack_path": {"type": "string", "description": "Optional asset.pack whose symbols are referenced by image node src fields"},
                "engine": {"type": "string", "enum": ["lvgl_simulator", "python_preview"], "default": "lvgl_simulator"},
                "lvgl_version": {"type": "string", "enum": ["v9"], "default": "v9", "description": "LVGL version (v9 only, v8 not yet supported)"},
                "display": {
                    "type": "object",
                    "properties": {
                        "width": {"type": "integer", "minimum": 1, "maximum": 4096, "default": 480},
                        "height": {"type": "integer", "minimum": 1, "maximum": 4096, "default": 800},
                    },
                },
                "preset": {"type": "string", "enum": ["headless-480x800", "headless-320x240"], "default": "headless-480x800"},
            },
            "required": ["spec_path"],
            "additionalProperties": False,
        },
    },
    {
        "name": "compare_ui",
        "description": "Compare rendered output with design baseline. Returns SSIM, pixel diff, region diff, text diff, control tree diff, and pass/fail.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "actual_path": {"type": "string", "description": "Path to rendered screenshot"},
                "baseline_path": {"type": "string", "description": "Path to design screenshot"},
                "spec_path": {"type": "string", "description": "Path to UI Spec for text/tree comparison"},
                "object_tree_path": {"type": "string", "description": "Path to rendered object tree JSON"},
                "threshold_profile": {"type": "string", "enum": ["preview_relaxed", "golden_strict", "hardware_tolerant"], "default": "golden_strict"},
            },
            "required": ["actual_path", "baseline_path"],
            "additionalProperties": False,
        },
    },
    {
        "name": "refine_ui",
        "description": "Iteratively improve LVGL page by generating → rendering → comparing → fixing spec. Maximum 3 rounds. Returns best result with improvement history.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "design_path": {"type": "string", "description": "Path to design screenshot"},
                "cut_dir": {"type": "string", "description": "Cutout assets directory"},
                "display": DISPLAY_SCHEMA,
                "lvgl_version": {"type": "string", "enum": ["v8", "v9"], "default": "v9"},
                "max_iterations": {"type": "integer", "minimum": 1, "maximum": 3, "default": 3},
                "output_dir": {"type": "string", "default": "artifacts/refine"},
                "baseline_evidence_path": {"type": "string", "description": "Native baseline evidence JSON required for scoring"},
                "candidate_evidence_paths": {"type": "array", "maxItems": 3, "items": {"type": "string"}, "description": "Native candidate evidence JSON files"},
            },
            "required": ["design_path"],
            "additionalProperties": False,
        },
    },
    {
        "name": "apply_patch",
        "description": "Write verified generated files to user project. Only tool with write access. Requires expected SHA256 hashes. Default is dry-run.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "source_dir": {"type": "string", "description": "Directory with verified generated files"},
                "target_dir": {"type": "string", "description": "Target directory in user project"},
                "expected_hashes": {
                    "type": "object",
                    "description": "Map of filename → SHA256 hash for verification",
                    "additionalProperties": {"type": "string"},
                },
                "mode": {"type": "string", "enum": ["dry_run", "replace_generated_files"], "default": "dry_run"},
            },
            "required": ["source_dir", "target_dir"],
            "additionalProperties": False,
        },
    },
]
