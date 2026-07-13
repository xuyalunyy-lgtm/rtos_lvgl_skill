# LVGL Generate Domain Workflow

Detailed loading rules and workflow reference for the Generate Domain.
SKILL.md contains only the entry-point table; full rules live here.

## Workflows

| Workflow | Trigger |
|----------|---------|
| [l3_lvgl_page.md](../workflows/l3_lvgl_page.md) | LVGL page generation |
| [l3_new_module.md](../workflows/l3_new_module.md) | new module / multitask MVP |
| [l3_bring_up.md](../workflows/l3_bring_up.md) | board bring-up |
| [l3_sdk_trim.md](../workflows/l3_sdk_trim.md) | SDK trimming |

## Loading Rules

- **必读:** `references/core_rules.md`, [lvgl_image_to_code_contract](lvgl_image_to_code_contract.md)（仅 LVGL 时）
- **按需:** 1 个 `platforms/{platform}.md`, `references/lvgl_*`（LVGL 相关）
- **工具:** MCP tools（inspect_design, generate_ui, render_ui, compare_ui, refine_ui, apply_patch）
- **入口:** MCP-first; see `.mcp.json`
- **禁止加载:** `tools/*_checker.py`, `examples/bad_*.c`（审查域内容）

## MCP Tools (6)

| Tool | Purpose |
|------|---------|
| `inspect_design` | 分析设计截图，输出 analysis_report + debug_overlay |
| `generate_ui` | 从 UI Spec 或 Manifest 生成 C/H 页面代码 |
| `render_ui` | 原生 LVGL 编译渲染，输出截图 + 对象树 |
| `compare_ui` | 视觉对比（SSIM / pixel diff / text diff） |
| `refine_ui` | 三轮自愈：生成→渲染→对比→修正 spec |
| `apply_patch` | 写入验证通过的生成文件到用户工程 |

## LVGL Version

当前仅支持 LVGL v9。Schema 中不暴露 v8 选项。

## Validation Contract

详见 [lvgl_validation_contract](lvgl_validation_contract.md)。
