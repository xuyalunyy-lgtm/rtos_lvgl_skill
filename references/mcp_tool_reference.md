# MCP Tool Reference

MCP server 通过 `.mcp.json` 自动加载，暴露以下 tool。所有 tool 返回统一结构：

```json
{
  "ok": true/false,
  "command": ["python", "tools/xxx.py", ...],
  "exit_code": 0,
  "stdout": "...",
  "stderr": "...",
  "data": { ... },
  "artifacts": []
}
```

## 核心工具

### list_capabilities

发现可用的 MCP tool、workflow、platform、RTOS 和 gate。

- 输入：无
- 输出：`{tools, resources, workflows, platforms, router_platforms, rtos, gates}`

### route_context

构建最小上下文加载计划。在加载 skill references 之前调用，避免 context 溢出。

| 参数 | 类型 | 必选 | 默认值 | 说明 |
|------|------|------|--------|------|
| workflow | string | ✅ | — | `code_review` / `project_review` / `crash_debug` / `memory_analysis` / `sdk_trim` / `new_module` / `bring_up` / `lvgl_page` / `hw_sw_debug` |
| platform | string | ✅ | — | `esp32` / `stm32` / `jl` / `bk` |
| rtos | string | — | `freertos` | `freertos` / `zephyr` |
| budget | string | — | `compact` | `compact` (~11k tokens) / `standard` (~25k) / `full` (~33k) |
| constraints | string[] | — | — | 指定约束 ID 缩小范围（如 `["C1", "C7"]`） |

- 输出：`{required_files, forbidden_by_default, constraint_shards, estimated_tokens, budget_mode}`
- 依赖：`tools/context_router.py`

### run_review

运行 31+ checker 的静态审查管线。用于代码审查、PR 审计、pre-commit 验证。

| 参数 | 类型 | 必选 | 默认值 | 说明 |
|------|------|------|--------|------|
| path | string | ✅ | — | C/H 文件或目录路径 |
| platform | string | — | `freertos` | `esp32` / `stm32` / `jl` / `bk` / `freertos` / `zephyr` |
| strict | boolean | — | `false` | 严格模式（P0 阻断） |
| suggest_fixes | boolean | — | `false` | 输出修复建议 FixPlan |
| fix_detail | string | — | `summary` | `summary` / `full` |

- 输出：`{ok, checkers: [{name, issues: [{severity, constraint, file, line, message}]}], summary: {total, p0, p1, p2}}`
- Exit code：0=全部通过，1=发现问题
- 依赖：`tools/run_review.py` → `checker_registry.py` → 各 checker 模块

### triage_log

分类固件 crash/log 输出。返回症状类别、根因候选和推荐 prompt。

| 参数 | 类型 | 必选 | 默认值 | 说明 |
|------|------|------|--------|------|
| log_path | string | ✅ | — | crash 日志文件路径 |
| platform | string | — | `""` | 平台（可自动推断） |
| rtos | string | — | `""` | RTOS 选择 |

- 输出：`{matched_symptoms, likely_constraints, top_hypotheses, verify_steps, missing_facts, inferred_platform, match_confidence}`
- 依赖：`tools/log_triage.py` + `references/log_symptom_routes.json`

### lookup_sdk

查询跨平台 SDK 操作映射。返回平台特定 API。

| 参数 | 类型 | 必选 | 默认值 | 说明 |
|------|------|------|--------|------|
| platform | string | ✅ | — | `esp32` / `stm32` / `jl` / `bk` / `zephyr` |
| query | string | 条件 | — | 操作名（如 `gpio_set`、`i2c_read`）。`all_ops`/`all_categories` 模式时可省略 |
| mode | string | — | `auto` | `auto` / `info` / `category` / `list` / `regex` / `all_ops` / `all_categories` |

- 输出：`{operation, platforms: {esp32: {api, header, notes}, ...}}`
- 依赖：`tools/sdk_lookup.py` + `platforms/*_sdk_map.yaml`

### run_gate

运行 skill 验证门禁（quick 或 full）。返回 pass/fail 详情。

| 参数 | 类型 | 必选 | 默认值 | 说明 |
|------|------|------|--------|------|
| level | string | — | `quick` | `quick`（15 项检查）/ `full`（skill_iterate --check） |
| strict | boolean | — | `false` | 严格模式 |

- 输出：`{ok, passed, checks: [{name, status, detail}]}`
- 依赖：`scripts/quick_gate.py` 或 `scripts/skill_iterate.py`

## LVGL 工具

LVGL 工具通过 `mcp/lvgl_ui.py` 暴露，详见 MCP server 的 LVGL tool schemas。核心工具：

| Tool | 用途 |
|------|------|
| `get_lvgl_theme_skill` | 加载 LVGL 主题规则和显示配置 |
| `convert_image_to_lvgl_source` | 将图片转为 LVGL RGB565 C-array |
| `generate_lvgl_layout_spec` | 从设计稿生成布局规格 JSON |
| `generate_lvgl_page_code` | 从规格 JSON 生成 LVGL C/H 代码 |
| `validate_lvgl_layout_code` | 静态检查布局代码（无绝对坐标等） |
| `lvgl_render` | 渲染 LVGL 代码并返回截图 |
| `run_lvgl_ui_regression` | 截图回归（像素差异 < 1%） |
| `generate_font_glyph` | 从文本提取字形生成 LVGL 字体 |
| `convert_assets_to_lvgl` | 批量转换图片资源 |

## MCP 返回结构

所有工具返回统一结构（`_mcp_result`）：

```json
{
  "content": [{"type": "text", "text": "<JSON payload>"}],
  "isError": false
}
```

错误时：

```json
{
  "ok": false,
  "error": {
    "code": "INVALID_INPUT",
    "message": "path is required",
    "tool": "run_review"
  },
  "artifacts": []
}
```

## 使用示例

```
# 1. 先路由上下文
route_context(workflow="code_review", platform="esp32", budget="compact")

# 2. 加载路由结果中的 required_files

# 3. 运行审查
run_review(path="./src", platform="esp32")

# 4. 如有 crash 日志
triage_log(log_path="./crash.log", platform="esp32")
```
