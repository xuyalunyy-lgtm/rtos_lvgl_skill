# LVGL Interactive Delivery Contract

This contract applies to design-driven, multi-page, and SSIM-gated LVGL work.

## Ownership

- The root skill owns request routing, embedded constraints, and workflow selection.
- `lvgl-ui-mcp/` owns the MCP entry point, public tool surface, release metadata, and project-level tests.
- `mcp/` remains the compatibility engine while modules are extracted incrementally. New public entry points and release configuration belong in `lvgl-ui-mcp/`.
- `artifacts/lvgl_runs/<run_id>/` is internal evidence. It is not a firmware delivery directory.
- The final delivery directory contains only files required to compile and link the generated UI.

## Required Workflow

1. Inventory design images, source cutouts, fonts, display geometry, pages, and states.
2. Run an interaction pass and persist accepted answers in `ui_decisions.json`.
3. Build an asset matrix with page, state, layer, source canvas, bbox, scale policy, and reuse scope.
4. Build one UI Spec v2 state description for every rendered page or state.
5. Generate LVGL page code, resource arrays, font subsets, and build integration.
6. Run asset-closure, compile, native-render, and SSIM checks.
7. Ask focused questions for unresolved high-impact mismatches, persist the answers, and refine the same run.
8. Publish only after all required gates pass.

Do not create sibling result directories such as `v2`, `v3`, or `final-final`. Keep one stable run directory and record each stage in its run manifest.

## High-Interaction Mode

High-interaction mode is allowed to ask many short, page-specific questions. Questions must be derived from observed ambiguity and should cover:

- coordinate space and whether transparent source-canvas padding is part of the bbox;
- asset role, page/state ownership, layer order, bbox, native-size policy, and reuse scope;
- crop, contain, stretch, or code-drawn behavior;
- font source, weight, size, fallback, and glyph scope;
- interaction targets, transitions, state changes, and persistent state;
- whether a visible mismatch is intentional or must be refined.

When transparent padding is part of the bbox, the asset intent must persist
`preserve_source_canvas: true`; resolved dimensions must equal source dimensions
and the crop offset must be zero. A translucent overlay must not be reported as
backdrop blur. Use either a budgeted, page-specific pre-baked blur layer or an
explicit target-platform blur hook, and record which strategy was accepted.

Unresolved high-impact decisions block code generation in high-interaction mode. Accepted answers must be machine-readable and reusable so the same question is not asked again.

## Verification Gates

- Every provided cutout is classified and every used cutout has deterministic placement.
- Generated sources pass the configured compile gate and asset-symbol closure check.
- Custom fonts are used by both firmware generation and native rendering.
- Global SSIM and every critical-region SSIM are at least `0.90`, unless the user records a different acceptance threshold.
- Required interactions and page transitions are exercised.

## Minimal Final Delivery

The final directory may contain only:

- generated page/application `.c` and `.h` files;
- generated asset and font `.c`/`.h` files actually referenced by those pages;
- one build integration file such as `ui_generated.cmake`.

Do not publish screenshots, overlays, specs, JSON reports, manifests, logs, README files, temporary packs, or renderer outputs into the final directory. They remain in the run ledger as internal evidence.
