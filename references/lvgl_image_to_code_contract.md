# LVGL Image-to-Code Contract

唯一端到端流程定义。所有 MCP 工具、CLI 脚本和 Skill workflow 必须遵守此契约。

## 流程概览

```
输入预检 → 视觉分析 → UI Spec → 资产编译 → 代码生成 → 编译渲染 → 视觉比较 → 交付
```

## 阶段定义

### 1. 输入预检 (design_preflight)

**输入：** 设计截图、切图目录、屏幕参数、LVGL 版本

**检查项：**
- 图片真实尺寸、色彩模式、透明通道
- 设计图比例与目标屏幕是否一致
- 自动检测 2x/3x 设计缩放
- 切图 hash、尺寸、透明边界、重复资产
- 最大图片尺寸限制（防内存耗尽）
- 缺失字体、切图或屏幕参数

**输出：** `input_manifest.json`

**阻断条件：** 缺少显示分辨率或 LVGL 版本时，只允许生成分析报告

### 2. 视觉分析 (visual_analysis)

**输入：** 预检后的设计图和切图

**确定性算法：**
- 连通区域检测
- 边缘和矩形检测
- 颜色聚类与主题提取
- 对齐线检测
- 重复卡片/按钮/列表项检测
- 切图模板匹配
- OCR 与文本 bbox

**推理增强（可选）：**
- 区域语义判断
- Flex row/column 推断
- header/content/footer 分组
- 装饰图片 vs 交互控件区分

**每个节点必须包含：** id、type、bbox、confidence、evidence

**输出：** `analysis_report.json` + `debug_overlay.png`

### 3. UI Spec 生成 (spec_generation)

**输入：** 分析报告

**输出：** `ui_spec_v2.json`（严格 JSON Schema 验证）

**必须包含：**
- display、rotation、color format
- LVGL version
- theme/palette
- fonts/glyphs
- asset manifest
- 控件树（节点 + 父子关系）
- visual bbox
- Flex/Grid layout contract
- styles
- source image provenance
- node confidence

**必须区分：**
- `source_bbox`：设计图像素位置
- `layout`：Flex/Grid 约束
- `render_bbox`：渲染后实际位置

### 4. 资产编译 (asset_compilation)

**输入：** UI Spec 中的 assets 和 fonts

**图片转换支持：**
- RGB565、RGB565A8、RGB888、ARGB8888、A8
- byte swap、alpha 分离
- Floyd-Steinberg / ordered dithering
- binary/C-array 输出
- 资产去重、自动裁剪透明边缘

**字体处理：**
- 从 OCR 和 Spec 收集实际字符
- 自动生成 glyph 集合
- 检测缺字
- 输出字体 flash 大小

**输出：** `assets/` + `fonts/` + `asset_manifest.json`

### 5. 代码生成 (code_generation)

**输入：** UI Spec + 编译后的资产

**分为两个后端：** `codegen_v8.py` / `codegen_v9.py`

**必须完成：**
- 控件树和父子关系
- Flex/Grid 布局
- style 去重
- 图片和字体引用
- 页面 create/destroy 生命周期
- event handler
- presenter/data binding 接口
- UI 线程异步更新

**生成失败条件：**
- ID 冲突
- 未知组件类型
- 未声明的资产或字体
- 无效宏名/C 标识符
- raw C 注入
- v8/v9 API 混用

**输出：** `src/` (C/H 文件)

### 6. 编译验证 (compile_validation)

**输入：** 生成的 C/H + LVGL 头文件

**检查项：**
- JSON Schema 验证
- C 语法检查（编译）
- 符号检查（未声明函数/变量）

**输出：** 编译结果

### 7. 渲染验证 (render_validation)

**输入：** 编译通过的代码

**输出：** `render.png` + `object_tree.json`

### 8. 视觉比较 (visual_comparison)

**输入：** render.png vs design.png

**比较维度：**
- 全局 SSIM
- changed pixel ratio
- 区域级 SSIM
- 控件 bbox IoU
- 文本内容和位置
- 控件类型、层级、顺序

**输出：** `visual_diff.json`

**迭代条件：** 差异超过阈值时，自动修正 Spec 并重新生成（最多 3 轮）

## 最终产物

```
output/
├── analysis_report.json    # 视觉分析结果
├── debug_overlay.png       # 调试叠加图
├── ui_spec.json            # 结构化 UI IR
├── assets/                 # 编译后的资产
├── fonts/                  # 编译后的字体
├── src/                    # 生成的 C/H 代码
├── render.png              # 渲染结果
├── object_tree.json        # 控件树
├── visual_diff.json        # 视觉比较结果
├── asset_manifest.json     # 资源预算
└── validation_report.json  # 验证报告
```

## 安全约束

- MCP 工具不直接从图片拼接 C 代码
- 图片分析结果必须先进入严格的 `ui_spec.json`
- 所有生成结果必须经过 schema、编译和渲染验证
- 不确定内容必须输出置信度和待确认项
- 无效 C、缺失资产、错误字体、错误尺寸都不能返回成功
