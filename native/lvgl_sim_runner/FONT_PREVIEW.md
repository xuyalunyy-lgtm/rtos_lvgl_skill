# Native Font Preview Contract

The generated firmware page uses the LVGL C font sources declared in
`ui/manifest.json`.  Native preview uses the same font identity, but LVGL
loads the official runtime `.bin` representation so the runner remains a
self-contained binary.

Declare a preview sidecar for every font used by a page:

```json
"fonts": {
  "title": {
    "source": "fonts/lvgl/40_bold.c",
    "preview_bin": "fonts/preview/40_bold.bin"
  }
}
```

`source` is copied into the generated firmware bundle and compiled by the
target project. `preview_bin` is passed to the runner as `--font
font_40_bold=.../40_bold.bin`, then loaded with LVGL's `lv_binfont_create()`.

When a UI Spec references a declared font but its `preview_bin` is absent,
`render_ui` returns `font_preview_unavailable`. It never renders with
LVGL's default font as a substitute. The runner writes `font_load_report.json`
with the loaded font IDs; the MCP verifies it before returning a successful
native render.
