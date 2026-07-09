# LVGL Design Codegen Quick Reference

## Token And Speed Defaults

- For chat-facing quick runs, pass `return_mode=compact`; MCP tool defaults may remain full for legacy caller compatibility.
- Compact responses include only `ok`, `page_name`, `analysis_ok`, key bboxes, analysis method, warning count, validation counts, and artifact paths.
- Full JSON trees, component lists, generated C/H, and debug metadata are written to artifacts, not returned in chat.
- Target per-page model context: 1-3k tokens before implementation and 300-800 tokens for tool/result discussion.

## Visual Analysis Rules

- Separate cut assets from LVGL components before codegen. Background/pet/product art remains image assets; simple controls, indicators, labels, panels, and buttons should be generated as LVGL widgets.
- Use template matching for small reference crops such as loading arcs and icons. Use alpha cutout matching for foreground images.
- Use residual detection only after known cut assets are subtracted. Mark fallback regions explicitly with `source=fallback_*`.
- Always write `analysis_report.json` and `debug_overlay.png`. Add dedicated debug crops for template matches when available.
- Keep compact component summaries capped to key elements; detailed connected-component output belongs only in the artifact report.


## Cutout Matching Rules

- Rank cutout candidates by `improvement = background_error - composite_error`, not by absolute composite error alone. Absolute-score ranking can select unrelated background-like regions and miss real cutouts.
- For small slices, first search residual component windows and likely status/loading regions; only fall back to full-screen search when no candidate window exists.
- Every cutout must be classified in `cutout_audit.json`: `used_cutout`, `used_component_calibration`, `duplicate_or_low_confidence`, or `unmatched_or_state_variant`. Do not silently ignore slices.
- If a slice improves a simple dynamic component such as battery/loading but runtime updates are required, use the slice as calibration evidence and generate the LVGL component unless visual parity requires the cutout.
- Keep one corrected `debug_overlay.png` and preserve older overlays as versioned files when fixing detection mistakes.

## Time Budget Rules

- One-page quick generation should finish the analysis/codegen path in seconds, not minutes.
- Avoid repeated full-screen brute force. Cache image dimensions, active-alpha samples, residual components, and candidate windows for the whole page.
- If matching exceeds the local time budget, stop and emit low-confidence entries in `cutout_audit.json` instead of continuing silently.



## Default Cutout Vs Dynamic Component Policy

Use this decision order when a detected visual element could be implemented either as a cutout or as an LVGL widget:

1. If the slice is high-confidence and the design requires exact visual parity, default to the cutout.
2. If the value must update at runtime, keep the cutout as the default visual path and add a compile-time switch for the dynamic component path, for example `UI_SUB_LOADING_USE_BATTERY_CUTOUT=0`.
3. If a slice only calibrates a simple shape and the design tolerance is loose, classify it as `used_component_calibration` and generate the LVGL component.
4. Never omit a high-confidence status icon because a component implementation is possible. Battery, bluetooth, wifi, loading marks, and small status glyphs must be either used as cutouts or explicitly documented in `cutout_audit.json`.

Overlay requirements:

- `debug_overlay.png`: corrected current overlay.
- `debug_overlay_vN.png`: versioned overlays when detection is corrected.
- `cutout_audit.json`: authoritative per-image status, bbox, score, improvement, and code macro.
- `analysis_report.json`: page-level layout tree with links to audit/overlay artifacts.

## Glass Effect Rules

- Treat translucent blur containers as independent LVGL components even when their child icon/cutout is already matched. Examples: loading glass circles, bottom glass panels, modal cards, and frosted buttons.
- Preserve design parameters in JSON and code comments/macros. For CSS-like `backdrop-filter: blur(12px)`, emit a platform hook such as `UI_*_APPLY_BACKDROP_BLUR(obj, 12)` because stock LVGL does not provide CSS backdrop-filter semantics.
- For inset left/right highlights such as `-1px 0 0 #FFFFFFB2 inset` and `1px 0 0 #FFFFFFB2 inset`, approximate with clipped child lines or document the renderer-specific style hook.
- A matched inner loading mark must be paired with the outer glass circle/card in `analysis_report.json`, `cutout_audit.json`, and generated C.

## Generated Code Rules

- Use macros for replaceable text: `UI_TEXT_*`.
- Use macros for replaceable image sources/descriptors: `UI_IMG_SRC_*`.
- Use macros for replaceable fonts: `UI_FONT_*`.
- Register a page-level custom event and provide async post helpers for server/RTOS updates.
- Keep generated source deterministic and avoid unrelated refactors.

## Upgrade Triggers

Use the standard/full workflow when the task needs platform decoder details, DMA/media buffer policy, live LVGL simulator screenshots, cross-page architecture review, or when the compact analysis confidence is low.
