# LVGL Validation Contract

定义什么情况下允许返回 `ok=true`。所有 MCP 工具和 CLI 脚本必须遵守。

## ok=true 的必要条件

一个 LVGL 生成/验证工具返回 `ok=true` 必须同时满足：

### 1. Schema 验证通过

- UI Spec 符合 `schemas/lvgl_ui_spec_v2.schema.json`
- Analysis Report 符合 `schemas/lvgl_analysis_report_v1.schema.json`
- Asset Manifest 符合 `schemas/lvgl_asset_manifest_v1.schema.json`
- Validation Report 符合 `schemas/lvgl_validation_report_v1.schema.json`

### 2. 编译通过

- 生成的 C/H 文件在目标 LVGL 版本下编译 0 error
- 无未声明的函数/变量/宏
- 无 v8/v9 API 混用

### 3. 资源完整性

- 所有 `UI_IMG_*` 宏在资产文件中有对应定义
- 所有 `UI_FONT_*` 宏在字体文件中有对应定义
- 所有 `UI_TEXT_*` 宏在头文件中有对应定义
- 资源路径可解析（文件存在）

### 4. 控件树完整性

- 每个节点的 `parent_id` 指向已声明的节点
- 无循环引用
- 根节点类型为 `screen`
- 节点 ID 唯一（清洗后无冲突）

### 5. 视觉比较（如有 baseline）

- 全局 SSIM ≥ 0.90（建议目标 0.92）
- 关键控件 bbox 中位 IoU ≥ 0.90
- 主要文本内容准确率 100%
- 无占位图/缺失资产

## ok=false 的充分条件

以下任一情况必须返回 `ok=false`：

### 编译失败

- C 语法错误
- 未声明的符号
- 链接错误

### 资源缺失

- 引用了不存在的图片或字体
- 占位图被使用
- glyph 缺失

### ID/宏问题

- 清洗后的 ID 冲突
- 无效的宏名（不符合 C 标识符规则）
- 无效的宏值（包含 raw C 注入）

### API 混用

- v8 代码中使用了 v9 API
- v9 代码中使用了 v8 API

### 尺寸/配置问题

- display config 缺失
- width/height 超出合理范围
- 未知的 LVGL 版本

### Schema 违反

- 必填字段缺失
- 字段类型错误
- 值超出允许范围

## render_only 状态

当没有 baseline 可比较时（首次生成），返回 `status: "render_only"` 而非 `passed`。

这表示：
- 编译通过
- 渲染成功
- 但无法判断视觉是否正确

用户需要：
1. 查看 render.png
2. 与 design.png 对比
3. 确认后将 render.png 作为 baseline

## 警告（不影响 ok=true）

以下情况返回 `ok=true` 但附带警告：

- 置信度 < 0.8 的节点
- 使用了 absolute 布局（需 `LVGL_LAYOUT_EXCEPTION` 注释）
- 字体 fallback 被使用
- 资源预算接近上限（>80%）
- 非关键区域 SSIM < 0.90 但 ≥ 0.80

## MCP 工具返回结构

```json
{
  "ok": true/false,
  "status": "passed|passed_with_warnings|failed|incomplete|render_only",
  "validation": { ... },
  "artifacts": { ... },
  "errors": [],
  "warnings": []
}
```

- `ok`：布尔值，严格按上述规则判断
- `status`：详细状态
- `validation`：完整验证报告
- `artifacts`：生成的文件路径
- `errors`：致命错误列表
- `warnings`：警告列表（不影响 ok）
