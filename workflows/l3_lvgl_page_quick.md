# L3 LVGL Page Quick Workflow

Use this compact workflow for fast design/cut-image to LVGL generation. It keeps model context small and stores detailed evidence on disk.

**触发：** 快速 LVGL 页面生成 / 简单 UI 页面 / 设计稿转 LVGL / quick LVGL page

```yaml
# Workflow Input Schema
inputs:
  required:
    - name: design_screenshot
      type: string
      description: 设计稿截图路径
    - name: cut_assets
      type: string[]
      description: 切图资源路径列表
  optional:
    - name: lvgl_version
      type: enum[v8, v9]
      default: v9

# Workflow Output Schema
outputs:
  format: mixed
  sections:
    - LVGL C/H 页面代码
    - preview.html（近似预览）
  verification: validate_lvgl_layout_code exit=0
  note: 使用 MCP 工具链，比标准 l3_lvgl_page 更快但跳过信息完整度评估
```

## Load Policy

- Default to MCP/local scripts for image analysis, code generation, validation, and artifact writing.
- Load this quick workflow plus `references/lvgl_design_codegen_quick.md` for normal one-page generation.
- Do not load full platform docs or full review/media constraint shards unless the user asks for platform API details, media pipelines, or renderer-level regression work.
- Upgrade to the standard workflow when component confidence is low, custom drivers/decoders are involved, or the generated code must be reviewed against detailed platform APIs.

## Fast Pipeline

1. Classify inputs: design screenshot, background/cut assets, reference crops, and component-only images.
2. Rename/copy non-ASCII assets to English aliases under the artifact directory; keep original source paths in the report.
3. Run local visual analysis first. Prefer template/cutout matching for known assets, then residual component detection for LVGL-drawn parts.
4. Generate a compact layout tree with key bboxes only for chat/tool output. Write full `analysis_report.json`, `debug_overlay.png`, preview, spec, and source files to disk.
5. Generate LVGL C/H from local templates. Text, image sources, and fonts must use macros so later integration can replace them without regenerating the page.
6. Add root custom-event listening and async post helpers so RTOS/network threads never update LVGL objects directly.
7. Run quick validation: Python syntax/import checks for generators, LVGL layout code validator, and JSON/C bbox sanity checks. Use full render/regression only when needed.

## Hard Rules

- `preview.html` is a positioning aid only; do not treat it as visual parity proof.
- Absolute coordinates are allowed for design reconstruction, but each one needs an `LVGL_LAYOUT_EXCEPTION` comment in generated C.
- Component detection must be evidence-based: template match, cutout alpha match, residual connected components, or explicit fallback marked in the report.
- Return compact summaries by default: key bboxes, confidence/method, validation counts, and artifact paths. Full reports stay in artifacts.

## Cutout Completeness Gate

Before codegen, every input image in `ui/` must be accounted for in `cutout_audit.json`.

Required classifications:

- `used_cutout`: high-confidence image layer used directly in LVGL.
- `used_component_calibration`: high-confidence slice used to size/style a dynamic LVGL component.
- `duplicate_or_low_confidence`: overlaps a stronger match or has weak improvement.
- `unmatched_or_state_variant`: not visible in the current design state, but preserved for later state pages.

Matching rules:

1. Rank candidates by `improvement = background_error - composite_error`; do not rank by absolute composite error alone.
2. Use residual connected components and likely regions first, especially status bars, loading areas, cards, and bottom panels.
3. For top/status icons, derive candidate windows from residual bboxes before any broad search.
4. Default to `used_cutout` for high-confidence visual icons such as battery, bluetooth, loading marks, and small status glyphs. If runtime updates are needed, expose a macro switch such as `UI_*_USE_*_CUTOUT=0` to use the dynamic LVGL component.
5. `debug_overlay.png` must show all used cutouts, component-calibration regions, LVGL components, and low-confidence candidates with distinct colors. Preserve old overlays as versioned files when fixing a bad detection.
6. Glass/blur layers are first-class components. If an inner icon/cutout is matched inside a blurred circle/card, also generate the outer glass container and record the blur/shadow parameters; do not let the inner match hide the outer component.

Time guard:

- Do not run repeated full-screen brute force for all small slices. Cache alpha samples, residual components, and candidate windows.
- If matching exceeds the quick budget, stop and emit low-confidence audit entries instead of continuing silently.

---
验收标准：[acceptance_criteria.md](../references/acceptance_criteria.md#lvgl-page-generationl3_lvgl_page)
