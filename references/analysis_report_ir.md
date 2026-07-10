# Analysis Report IR (Intermediate Representation)

The `analysis_report.json` is the de facto intermediate representation for the
design-to-LVGL pipeline. All tools (codegen, regression, visual_diff) consume
or produce this format.

## Required Top-Level Keys

```json
{
  "screen": {},
  "assets": [],
  "components": [],
  "layout_policy": {},
  "warnings": []
}
```

## screen

Display parameters. `width` and `height` are required; others optional.

```json
{
  "width": 480,
  "height": 800,
  "lvgl_version": "v9",
  "color_depth": 16
}
```

## components

Each component represents a detected or generated UI element.

**Required fields:**

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique identifier |
| `type` | string | Widget type: `label`, `button`, `container`, `bar`, `card`, `image`, etc. |
| `bbox` | [x, y, w, h] | Bounding box in pixels |
| `source` | string | Detection method: `template_match`, `bright_circle_detection`, `button_bounds_fallback`, `layout_root`, `manual` |
| `confidence` | float | 0.0 - 1.0 |

**Optional fields:**

| Field | Type | Description |
|-------|------|-------------|
| `text` | string | Label text content |
| `style` | object | Visual properties (bg_color, radius, text_color, etc.) |
| `runtime_binding` | string | Variable name for dynamic updates |
| `children` | list | Nested components |

## assets

List of image/font assets referenced by components.

```json
[
  {
    "id": "bg_main",
    "type": "image",
    "path": "cutouts/bg.jpg",
    "format": "SJPG",
    "bbox": [0, 0, 480, 800]
  }
]
```

## layout_policy

How the layout was generated.

| Field | Type | Description |
|-------|------|-------------|
| `mode` | string | `pixel_exact` or `responsive_lvgl` |
| `exception_count` | int | Number of `LVGL_LAYOUT_EXCEPTION` annotations |
| `notes` | string | Free-text explanation |

## warnings

List of non-fatal issues detected during generation.

```json
[
  {
    "level": "warning",
    "rule": "low_confidence_component",
    "message": "Component 'icon_battery' has confidence 0.45"
  }
]
```

## Validation

Run `python tools/validate_cutout_audit.py <page_dir>` to validate both
`analysis_report.json` IR fields and `cutout_audit.json` completeness.
