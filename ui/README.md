# UI Input Package

This directory is the source package for design-to-LVGL generation.  Keep the
design baseline separate from runtime assets so the generator can distinguish
what to compare from what to package.

## Layout

- `design/`: reference screenshots; never packaged as a runtime asset.
- `assets/backgrounds/`: full-screen scene backgrounds, grouped by visual state.
- `assets/characters/`: transparent foreground characters or products.
- `assets/icons/mood/`: interactive mood-state icons.
- `assets/icons/system/`: status-bar and navigation icons.
- `fonts/lvgl/`: pre-generated LVGL font C sources.  Add original TTF/OTF files
  under `fonts/source/` when available; do not overwrite the generated C files.
- `manifest.json`: the authoritative semantic mapping from a page state to its
  design reference, assets, and fonts.

When calling the MCP, pass `cut_dir: "ui"`; the interactive-scene adapter
recursively resolves both this organized hierarchy and the old flat layout.
