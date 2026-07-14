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
  internal_evidence:
    - analysis_report.json（视觉分析结果）
    - debug_overlay.png（调试叠加图）
    - ui_spec.json（结构化 UI IR）
    - render.png（渲染结果）
    - visual_diff.json（视觉比较）
    - validation_report.json（验证报告）
  final_delivery:
    - LVGL C/H 页面代码
    - 实际引用的资产与字体 C/H
    - ui_generated.cmake
  verification: compile gate + visual SSIM >= 0.90
```

## 流程概览

```
输入预检 → 高交互澄清 → 资产矩阵 → UI Spec v2 → 资产编译 → 代码生成 → 编译验证 → 视觉比较 → 最小交付
```

完整交互、证据和交付边界见 [LVGL Interactive Delivery Contract](../references/lvgl_interactive_delivery_contract.md)。

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

资产矩阵若把透明留白定义为 bbox 的一部分，Initial Manifest 必须为该资产设置
`preserve_source_canvas: true`。解析结果必须满足 `converted_size == original_size`
且 `crop_offset == [0, 0]`；不能一边用完整画布坐标，一边让转换器自动裁透明边缘。

半透明卡片不等于 backdrop blur。标准 LVGL 没有跨平台一致的背景模糊时，按页面已知层级
预合成背景和前景，生成卡片 bbox 大小的 Gaussian blur 派生层，再按
`background/foreground -> blur layer -> supplied translucent cutout -> text/controls`
顺序渲染。派生层必须进入资产闭包和 Flash 预算，原始切图保持不变；若选择平台 blur hook，
必须由目标平台原生渲染证据验收。

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

项目具备稳定语义验证脚本时，应提供一次性执行构建、静态编译、原生渲染和严格 SSIM 的入口，
避免各阶段由临时命令拼接。本项目的四页验证入口为：

```bash
python tools/build_semantic_ui_validation.py --output-dir artifacts/lvgl_runs/<run_id>/semantic --verify --render-dir artifacts/lvgl_runs/<run_id>/render
```

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
| 预检/分析/澄清 | `inspect_design` | 分析设计图，持久化高交互问题与答案 |
| 生成 | `generate_ui` | 从已确认的 UI Spec v2/manifest 生成代码 |
| 渲染 | `render_ui` | 使用固定 preset 原生渲染 |
| 比较 | `compare_ui` | 渲染结果与设计图比较 |
| 修正 | `refine_ui` | 根据差异证据选择候选修正 |
| 写入 | `apply_patch` | 只将已验证、编译必需的文件写入项目 |

## 安全约束

- MCP 工具不直接从图片拼接 C 代码
- 图片分析结果必须先进入严格的 `ui_spec.json`
- 所有生成结果必须经过 schema、编译和渲染验证
- 高影响不确定项必须进入持久化澄清契约；高交互模式下未解决前禁止生成
- 无效 C、缺失资产、错误字体、错误尺寸都不能返回成功
- 证据只保留在 `artifacts/lvgl_runs/<run_id>/`，最终目录禁止包含 JSON、截图、日志和临时资源包

---
验收标准：[acceptance_criteria.md](../references/acceptance_criteria.md#lvgl-page-generationl3_lvgl_page)
