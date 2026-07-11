# Workflow: L3 LVGL 单页面生成

**触发：** 新 UI 页面 / LVGL 代码生成 / 带屏产品页面开发 / UI 布局调整 / LVGL page generation

```yaml
# Workflow Input Schema
inputs:
  required:
    - name: design_screenshot
      type: string
      description: 设计稿截图路径（PNG/JPG）
  optional:
    - name: cut_assets_dir
      type: string
      description: 切图资源目录
    - name: width
      type: integer
      default: 480
      description: 目标屏幕宽度
    - name: height
      type: integer
      default: 800
      description: 目标屏幕高度
    - name: lvgl_version
      type: enum[v8, v9]
      default: v9
      description: LVGL 版本

# Workflow Output Schema
outputs:
  format: mixed
  sections:
    - analysis_report.json（视觉分析结果）
    - debug_overlay.png（调试叠加图）
    - ui_spec.json（结构化 UI IR）
    - LVGL C/H 页面代码
    - render.png（渲染结果）
    - visual_diff.json（视觉比较）
    - validation_report.json（验证报告）
  verification: compile gate + visual SSIM >= 0.90
```

## 流程概览

```
输入预检 → 视觉分析 → UI Spec → 资产编译 → 代码生成 → 编译验证 → 视觉比较 → 交付
```

## Step 0 — 输入预检

```bash
python mcp/lvgl_preflight.py --design <path> --width <w> --height <h> --lvgl-version <v8|v9> --json
```

检查项：
- 图片尺寸、色彩模式、透明通道
- 设计图比例与目标屏幕是否一致
- 自动检测 2x/3x 设计缩放
- 切图 hash、尺寸、去重

**阻断条件：** 缺少显示分辨率或 LVGL 版本时，只允许生成分析报告。

## Step 1 — 视觉分析

```bash
python mcp/lvgl_analysis.py --design <path> --width <w> --height <h> --json
```

输出：
- `analysis_report.json` — 检测区域、文本、颜色、布局候选、置信度
- `debug_overlay.png` — 可视化调试叠加图

## Step 2 — 生成 UI Spec

从分析报告生成 `ui_spec.json`（严格 JSON Schema 验证）。

```bash
python mcp/lvgl_refine.py --design <path> --width <w> --height <h> --max-iterations 1 --json
```

## Step 3 — 资产编译

```bash
python mcp/assets.py convert_image_to_lvgl_source --input_path <path> --output_dir artifacts/assets --color_format RGB565
```

支持：RGB565、RGB565A8、RGB888、ARGB8888、A8、Floyd-Steinberg 抖动、byte swap、自动裁剪。

## Step 4 — 代码生成

```bash
python mcp/lvgl_codegen.py --spec ui_spec.json --output-dir artifacts/lvgl_ui --lvgl-version <v8|v9> --json
```

生成：
- `ui_page_<name>.c` — 页面代码
- `ui_page_<name>.h` — 页面头文件

## Step 5 — 编译验证

```bash
python mcp/lvgl_compile_gate.py --dir artifacts/lvgl_ui --lvgl-version <v8|v9> --json
```

检查项：
- 括号平衡
- v8/v9 API 混用检测
- C 注入检测
- 未声明符号检测

## Step 6 — 视觉比较

```bash
python mcp/lvgl_compare.py --actual render.png --baseline design.png --spec ui_spec.json --json
```

比较维度：
- 全局 SSIM
- 区域级像素差异
- 文本内容
- 控件树结构

## Step 7 — 自动 Refinement（可选）

如果视觉比较不达标，自动修正 Spec 并重新生成：

```bash
python mcp/lvgl_refine.py --design <path> --width <w> --height <h> --max-iterations 3 --json
```

最多 3 轮迭代，自动停止当：
- 编译通过且置信度 >= 0.8
- 达到最大迭代次数

## 信息完整度

| 信息 | 必要性 | 缺失处理 |
|------|--------|----------|
| 设计截图 | 🔴 必须 | 拒绝生成 |
| 屏幕分辨率 | 🔴 必须 | 使用默认 480x800 |
| LVGL 版本 | 🔴 必须 | 默认 v9 |
| 切图资源 | 🟡 可选 | 分析阶段自动检测 |
| 颜色主题 | 🟡 可选 | 从分析报告提取 |
| 字体资源 | 🟡 可选 | 使用默认字体 |

## MCP 工具链

MCP 工具对应本 workflow 的各步骤：

| 步骤 | MCP 工具 | 说明 |
|------|----------|------|
| 预检 | `inspect_lvgl_design` | 只读分析设计图 |
| 分析 | `inspect_lvgl_design` | 包含预检和分析 |
| 生成 | `generate_lvgl_ui` | 从 UI Spec 生成代码 |
| 渲染 | `render_lvgl_ui` | 使用固定 preset 渲染 |
| 比较 | `compare_lvgl_ui` | 渲染结果与设计图比较 |
| 修正 | `refine_lvgl_ui` | 根据差异修改 Spec |
| 写入 | `apply_lvgl_patch` | 将已验证结果写入项目 |

## 安全约束

- MCP 工具不直接从图片拼接 C 代码
- 图片分析结果必须先进入严格的 `ui_spec.json`
- 所有生成结果必须经过 schema、编译和渲染验证
- 不确定内容必须输出置信度和待确认项
- 无效 C、缺失资产、错误字体、错误尺寸都不能返回成功

---
验收标准：[acceptance_criteria.md](../references/acceptance_criteria.md#lvgl-page-generationl3_lvgl_page)
