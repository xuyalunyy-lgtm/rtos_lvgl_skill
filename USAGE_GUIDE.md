# FreeRTOS Embedded Architect — 完整使用说明

> **版本:** v46.0.0 | **更新日期:** 2026-07-14

---

## 一、项目概述

**项目名称：** `freertos-embedded-architect`
**当前版本：** v45.0.0
**定位：** 一个面向 FreeRTOS 嵌入式固件开发的 AI 编码助手工具链，集成在 Cursor / Claude Code / Codex 等 AI IDE 中使用。

**核心能力：**

| 能力 | 说明 |
|------|------|
| 🔍 **静态代码审查** | 60+ Python 检查器，覆盖 45 个约束域、248 条规则 |
| 🎨 **LVGL UI 生成** | 设计截图 → LVGL C/H 代码（支持 v8/v9） |
| 🖥️ **原生渲染验证** | 内置 LVGL v9 模拟器，无头渲染 + 视觉对比 |
| 📦 **多页应用脚手架** | Manifest v2 → Router/Presenter/Model/App 全栈 C 代码 |
| 🛣️ **上下文路由** | 自然语言症状匹配 → 工作流 + 约束分片 |
| 🔧 **多平台支持** | ESP32、STM32、JL/AC79、BK7258、Zephyr |
| 📡 **嵌入式调试** | MQTT 消息调试、串口日志、OTA 固件升级 |

---

## 二、环境要求

- **Python** >= 3.10（推荐 3.11）
- **操作系统**：Windows 10/11、Linux x64、macOS（x64/arm64）
- **编码**：必须设置 UTF-8（Windows 用户需特别注意）

### 可选依赖

```bash
# 视觉分析（Pillow + numpy）
pip install "Pillow>=10,<13" "numpy>=1.26,<3"

# OCR 能力
pip install "rapidocr-onnxruntime>=1.3,<2"

# MQTT 调试（MQTT MCP）
pip install "paho-mqtt>=2.0,<3"

# 串口调试（Serial MCP）
pip install "pyserial>=3.5,<4"

# 测试
pip install "pytest>=8,<9"

# 代码规范
pip install "ruff>=0.6,<1"
```

> 核心工具链零外部依赖，仅使用 Python 标准库。

---

## 三、安装方式

### 方式一：Cursor IDE 安装

1. 将整个 `skill/` 目录复制到你的项目中
2. 在 Cursor 设置中添加为 Project Skill 或 Personal Skill
3. 可选：将 `templates/cursor-rule.*.mdc` 复制到 `.cursor/rules/`

### 方式二：Claude Code 安装

1. 将 `skill/` 目录放到合适位置
2. 配置 `.mcp.json`（项目已有）：

```json
{
  "mcpServers": {
    "freertos-embedded-architect": {
      "command": "python",
      "args": ["mcp/server.py"],
      "env": { "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8" }
    },
    "mqtt-mcp": {
      "command": "python",
      "args": ["mcp/mqtt_server.py"],
      "env": { "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8" }
    },
    "ota-mcp": {
      "command": "python",
      "args": ["mcp/ota_server.py"],
      "env": { "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8" }
    },
    "serial-mcp": {
      "command": "python",
      "args": ["mcp/serial_server.py"],
      "env": { "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8" }
    }
  }
}
```

3. 可选：将 `templates/CLAUDE.embedded.md` 复制为项目的 `CLAUDE.md`

### 方式三：Codex 安装

参考 `.codex/config.toml` 配置 MCP server，将 `templates/AGENTS.freertos-strict.md` 复制为 `AGENTS.md`。

---

## 四、目录结构总览

```
skill/
├── SKILL.md                  # L0 意图路由控制平面（入口）
├── README.md                 # 项目概述
├── INSTALL.md                # 详细安装指南
├── CHANGELOG.md              # 版本变更日志
├── pyproject.toml            # Python 项目配置
├── .mcp.json                 # MCP Server 配置
│
├── mcp/                      # 🔧 MCP Server 核心代码
│   ├── server.py             # MCP JSON-RPC 入口
│   ├── high_level_tools.py   # 6 个高层工具实现
│   ├── high_level_schemas.py # 工具 JSON Schema
│   ├── codegen.py            # LVGL 代码生成引擎
│   ├── assets.py             # 图片/字体资产转换
│   ├── lvgl_codegen.py       # UI Spec → C/H 代码
│   ├── lvgl_compare.py       # 视觉对比（SSIM/像素）
│   ├── lvgl_preview.py       # 纯 Python 预览渲染器
│   ├── lvgl_refine.py        # 迭代优化入口
│   ├── manifest_v2.py        # Manifest v2 验证/解析
│   ├── app_codegen.py        # 多页应用 C 代码生成
│   ├── app_validator.py      # 应用级验证器
│   ├── initial_loading_auto.py    # 启动页自动生成
│   ├── interactive_scene_auto.py  # 互动场景页生成
│   ├── standard_ui_package.py     # 标准 UI 包自动发现
│   ├── design_asset_policy.py     # 设计图≠运行时资产 策略
│   ├── mqtt_server.py        # MQTT MCP Server（设备消息调试）
│   ├── mqtt_client.py        # MQTT 客户端桥接
│   ├── mqtt_schemas.py       # MQTT 工具 Schema
│   ├── ota_server.py         # OTA MCP Server（固件升级管理）
│   ├── ota_firmware.py       # 固件仓库管理
│   ├── ota_device.py         # 设备注册表
│   ├── ota_protocol.py       # OTA 协议实现
│   ├── ota_http.py           # OTA HTTP 服务器
│   ├── ota_schemas.py        # OTA 工具 Schema
│   ├── serial_server.py      # Serial MCP Server（串口调试）
│   ├── serial_client.py      # 串口桥接 + Ring Buffer
│   ├── serial_schemas.py     # Serial 工具 Schema
│   └── lvgl_ir/              # 二进制协议层
│       ├── asset_pack.py     # 资产打包（.pack 二进制）
│       ├── scene_encoder.py  # 场景编码（scene.bin）
│       ├── object_tree_reader.py  # 对象树读取
│       └── spec_validator.py # UI Spec 验证
│
├── tools/                    # 🛠️ CLI 工具（60+ 脚本）
│   └── run_review.py         # 一键静态审查入口
│
├── workflows/                # 📋 工作流定义
│   ├── l2_code_review.md     # L2 代码审查
│   ├── l3_lvgl_page.md       # LVGL 页面生成
│   └── ...                   # 共 10 个工作流
│
├── references/               # 📚 约束规则参考（50+ 文件）
├── prompts/                  # 💬 场景提示词（40+ 文件）
├── platforms/                # 🔌 平台适配（ESP32/STM32/JL/BK/Zephyr）
├── frameworks/               # 📦 框架配置（LVGL/lwIP/mbedTLS 等）
├── examples/                 # ✅ 好/坏代码示例（36 个）
├── golden_pages/             # 🏆 12 个黄金页面回归测试
├── native/                   # 🔨 原生 LVGL 模拟器 C 源码
├── runtime/                  # 🖥️ 预编译模拟器二进制
├── tests/                    # 🧪 测试套件（200+ 用例）
├── scripts/                  # 📜 辅助脚本（30+）
├── schemas/                  # 📐 JSON Schema 定义
├── templates/                # 📝 项目模板
├── ui/                       # 🎨 UI 资产（背景/角色/图标/字体）
└── artifacts/                # 📤 生成输出（gitignored）
```

---

## 五、域检测路由（Domain Detection）

SKILL.md 采用 **域感知瘦路由** 架构。AI 会根据用户的第一条消息自动识别意图域，**只加载该域所需的文件**，避免跨域加载浪费 token。

### 四个域

| 域 | 触发关键词 | 加载内容 | 不加载 |
|----|-----------|----------|--------|
| **review** | 审查, review, audit, ISR, DMA, cJSON | tools/, references/, prompts/, platforms/ | mcp/, golden_pages/, native/ |
| **generate** | LVGL, UI, 页面, 设计截图, 新模块, bring-up | mcp/, references/lvgl_*, platforms/ | tools/*_checker, examples/bad_* |
| **debug** | crash, HardFault, 死机, 看门狗, WDT | references/log_symptom_routes.json, tools/log_triage.py | mcp/, golden_pages/ |
| **app** | manifest, 多页, Router, Presenter, Model | schemas/, mcp/ (generate_ui) | tools/*_checker, prompts/ |

### Token 节省效果

| 用户意图 | 旧方案加载 | 新方案加载 | 节省 |
|----------|-----------|-----------|------|
| "审查代码" | ~450KB 全量 | ~200KB review 域 | **56%** |
| "生成 LVGL 页面" | ~450KB 全量 | ~300KB generate 域 | **33%** |
| "分析崩溃日志" | ~450KB 全量 | ~100KB debug 域 | **78%** |
| "生成多页 App" | ~450KB 全量 | ~80KB app 域 | **82%** |

### 工作原理

1. AI 读取 `SKILL.md` 中的 **Domain Detection** 表
2. 匹配用户消息中的关键词到对应域
3. 只读取该域的 **Loading Rules** 中列出的文件
4. 遇到模糊意图时，主动询问用户确认域

---

## 六、核心使用流程

### 流程 1：固件代码审查（Review Chain）

```bash
# 一键审查（CLI/CI 方式）
python tools/run_review.py

# 指定目标目录
python tools/run_review.py --target src/

# 自测模式
python tools/run_review.py --self-test

# 验证示例代码
python tools/run_review.py --validate-examples
```

**在 AI IDE 中使用：** 直接对 AI 说 "审查这段代码" 或 "review this code"，AI 会自动调用 MCP 工具 `run_review`。

**审查覆盖的 45 个约束域包括：**

- C1-C5: 内存管理、队列载荷所有权、CJSON 泄漏
- C6-C10: ISR/DMA 安全、优先级反转、临界区
- C11-C15: WSS/mbedTLS、OTA 回滚、Flash/NVS
- C16-C20: 网络弹性、低功耗、显示驱动
- C21-C25: 语音/ASR、A/V 管道、时钟漂移
- C26-C30: DMA 缓冲区生命周期、模块边界、超时预算
- C31-C35: 日志、错误处理、启动/WDT、状态机
- C36-C40: 传感器集成、LVGL 线程安全、锁预算
- C41-C45: 测试宏、代码风格、SDK 裁剪、软件架构

### 流程 2：LVGL 页面生成（Generate Chain）

#### 2a. 从设计截图生成单页

```python
# 步骤 1: 分析设计（只读，不生成代码）
inspect_design(design_path="path/to/design.png", display={"width": 480, "height": 800})

# 可选：填写首次检查生成的 page_input.json 后重新确认
inspect_design(
    design_path="path/to/design.png",
    page_input_path="artifacts/inspect/page_input.json",
    display={"width": 480, "height": 800},
)

# 步骤 2: 生成 LVGL C/H 代码
generate_ui(design_path="path/to/design.png", output_dir="artifacts/generated")

# 步骤 3: 渲染验证
render_ui(spec_path="artifacts/generated/ui_spec.json")

# 步骤 4: 视觉对比
compare_ui(actual_path="artifacts/render/render.png", baseline_path="path/to/design.png")

# 步骤 5: 迭代优化（最多 3 轮）
refine_ui(design_path="path/to/design.png")

# 步骤 6: 写入项目（SHA256 校验）
apply_patch(source_dir="artifacts/generated", target_dir="src/ui", mode="replace_generated_files")
```

首次检查会生成一个便于人工确认的 `page_input.json`。推荐在生成代码前填写它：

```json
{
  "schema_version": "1.0",
  "status": "confirmed",
  "page_id": "schedule",
  "display": [480, 800],
  "design": "schedule.png",
  "coordinate_space": {
    "design_width": 480,
    "design_height": 800,
    "display_mapping": "1:1"
  },
  "bbox_policy": {"include_transparent_padding": true},
  "screen": {"bg_color": "#FFFFFF", "full_screen_tap": false},
  "assets": [{
    "symbol": "schedule_card",
    "type": "decorative_image",
    "source": "daily_recommendation_02.png",
    "bbox": [8, 218, 464, 564],
    "scale": "original",
    "preserve_canvas": true,
    "page": "schedule",
    "state": "default",
    "layer": "content",
    "reuse_scope": "page"
  }],
  "fonts": [{
    "role": "title",
    "source": "InriaSerif-Bold.ttf",
    "size": 40
  }],
  "elements": [{
    "id": "page_title",
    "type": "label",
    "text": "Schedule",
    "bbox": [0, 73, 480, 52],
    "font_role": "title",
    "styles": {"text_color": "#6B5137", "text_align": "center"}
  }],
  "interactions": {
    "transition": "none",
    "targets": [],
    "persistent_state": []
  }
}
```

确认后直接从该文件生成。`assets` 数组顺序即从后到前的绘制顺序，所有 bbox
都会原样写入 UI Spec v2，不会再次执行视觉分析：

```text
generate_ui(
  page_input_path="ui/page_input.json",
  cut_dir="ui/assets",
  output_dir="artifacts/generated/schedule"
)
```

默认 `final_only` 仅交付页面 C/H、图片与字体 C、头文件和
`ui_generated.cmake`。需要渲染或 SSIM 排查时，使用
`delivery_mode="full_evidence"` 保留 UI Spec 和 asset pack。

`status` 未改为 `confirmed`、bbox 不完整或资产字段缺失时，工具返回
`manual_required`，不会进入代码生成。

#### 2b. 从标准 UI 包生成（自动发现）

如果你的项目有标准的 `ui/` 目录结构：

```
ui/
├── assets/
│   ├── backgrounds/     # 背景图
│   ├── characters/      # 宠物角色图
│   └── icons/
│       ├── mood/        # 心情图标 (calmness/good/down/stressed)
│       └── system/      # 系统图标 (wifi/bluetooth/battery)
└── fonts/
    └── lvgl/            # LVGL 字体 C 文件
```

直接调用：

```python
generate_ui(ui_dir="ui/", output_dir="artifacts/generated")
```

系统会自动发现资产、打包、生成互动场景页。

默认使用 `delivery_mode="final_only"` 和 `cleanup_intermediates=true`：资源闭环通过并发布最终目录后，分析报告、`asset.pack`、调试图、编译缓存和其他中间证据会自动删除。最终目录只保留可编译的 C/H、实际使用的图片与字体 C 文件、CMake 清单和 `delivery_manifest.json`。

只有需要排查生成器或保存完整验收证据时才使用：

```text
generate_ui(
  ui_dir="ui/",
  output_dir="artifacts/generated",
  delivery_mode="full_evidence",
  cleanup_intermediates=false
)
```

编译、渲染和 pytest 缓存统一放在 `.cache/lvgl_ui/`，不属于最终产物，也不得提交。

##### 状态栏图标尺寸规则（重要）

`assets/icons/system/` 中的 `wifi`、`bluetooth`、`battery` 等 `status_icon` 必须以**原始贴图画布尺寸**生成，不能用设计检测框的宽高再次缩放。

例如三张 PNG 均为 `48×48`，即使实际可见图形只占其中一部分，生成结果也必须满足：

| 项目 | 要求 |
|------|------|
| `lv_image_dsc_t.header.w/h` | `48×48`，与原始 PNG 一致 |
| LVGL 图片对象尺寸 | `48×48`，与描述符一致 |
| 透明 padding | 必须保留，不执行 Alpha 自动裁边 |
| 图片对齐 | 使用 `LV_IMAGE_ALIGN_CENTER`，禁止 `LV_IMAGE_ALIGN_STRETCH` |
| 运行时缩放 | 禁止；状态栏图标按贴图原尺寸显示 |

透明 padding 是贴图定位合同的一部分，也能避免抗锯齿边缘紧贴对象边界后被 LVGL 裁掉。设计分析得到的 `estimated_bbox` 表示**可见图形区域**，只用于回推贴图画布坐标，不能覆盖贴图宽高：

```text
object_x = estimated_visible_x - alpha_bbox.x0
object_y = estimated_visible_y - alpha_bbox.y0
object_w = source_image_width
object_h = source_image_height
```

以当前 48×48 系统图标为例：

| 图标 | Alpha 有效区域 | LVGL 画布坐标与尺寸 |
|------|----------------|---------------------|
| Wi-Fi | `[8, 12, 42, 37]` | `(289, 8, 48, 48)` |
| Bluetooth | `[15, 10, 31, 38]` | `(348, 8, 48, 48)` |
| Battery | `[4, 14, 44, 34]` | `(409, 9, 48, 48)` |

生成代码应采用以下形式：

```c
lv_obj_t *system_wifi = lv_image_create(page);
lv_image_set_src(system_wifi, &icon_wifi);
lv_image_set_inner_align(system_wifi, LV_IMAGE_ALIGN_CENTER);
/* LVGL_LAYOUT_EXCEPTION: status icon uses its source texture canvas without scaling. */
lv_obj_set_pos(system_wifi, 289, 8);
lv_obj_set_size(system_wifi, 48, 48);
```

禁止生成以下组合：

```c
/* 错误：描述符已裁边，又被压入更小的设计检测框。 */
lv_image_set_inner_align(system_wifi, LV_IMAGE_ALIGN_STRETCH);
lv_obj_set_size(system_wifi, 31, 23);
```

验收时必须同时核对：原始 PNG 尺寸、resolved manifest 的 `original_size/converted_size/crop_offset`、C 描述符尺寸和 LVGL 对象尺寸。对于 `status_icon`，应满足 `original_size == converted_size == object_size` 且 `crop_offset == [0, 0]`。

#### 2c. 多页应用生成（Manifest v2）

创建 `manifest.json` 定义多页应用：

```json
{
  "schema_version": "2.0",
  "app": {
    "id": "my_app",
    "entry_page": "home"
  },
  "display": { "width": 480, "height": 800 },
  "pages": [
    {
      "id": "home",
      "design": "designs/home.png",
      "states": ["default", "loading"],
      "events": [
        { "trigger": { "type": "click", "target": "btn_start" },
          "actions": [{ "type": "route", "route": "home_to_detail" }] }
      ]
    },
    {
      "id": "detail",
      "design": "designs/detail.png",
      "states": ["default"]
    }
  ],
  "routes": [
    { "id": "home_to_detail", "from": "home", "to": "detail", "mode": "push" }
  ],
  "models": [
    { "name": "app_state", "fields": [
      { "name": "is_loaded", "type": "bool", "default": false }
    ]}
  ]
}
```

然后：

```python
generate_ui(manifest_path="manifest.json", output_dir="artifacts/ui_app/my_app")
```

生成的文件结构：

```
artifacts/ui_app/my_app/
├── ui_router.c / .h        # 页面栈管理（push/back/replace）
├── ui_app.c / .h           # 应用生命周期
├── ui_page_home.c / .h     # 首页
├── ui_page_detail.c / .h   # 详情页
├── ui_presenter_home.c / .h  # 首页事件绑定
├── ui_presenter_detail.c / .h
├── ui_model_app.c / .h     # 数据模型（Mock）
└── ui_assets.c / .h        # 资产注册
```

### 流程 3：崩溃日志分析（Debug Chain）

```bash
# 在 AI IDE 中直接说：
"分析这段崩溃日志"
"这个 watchdog reset 是什么原因？"
```

AI 会调用 `triage_log` 工具，匹配症状路由表（`references/log_symptom_routes.json`），定位根因。

### 流程 4：快速门禁检查

```bash
# 快速检查（适合 pre-commit）
python scripts/quick_gate.py

# 完整迭代验证（21 项检查）
python scripts/skill_iterate.py --check

# 发布级验证
python scripts/skill_iterate.py --release
```

---

## 七、MCP 工具详解（6 个高层工具）

这些是 AI 模型可以直接调用的工具：

| 工具 | 功能 | 关键参数 |
|------|------|----------|
| `inspect_design` | 分析设计截图（只读） | `design_path`, `display`, `cut_dir` |
| `generate_ui` | 生成 LVGL C/H 代码 | `design_path` 或 `spec_path` 或 `manifest_path` 或 `ui_dir` |
| `render_ui` | 渲染 UI Spec | `spec_path`, `engine` (lvgl_simulator/python_preview) |
| `compare_ui` | 视觉对比 | `actual_path`, `baseline_path`, `threshold_profile` |
| `refine_ui` | 迭代优化（最多 3 轮） | `design_path`, `max_iterations` |
| `apply_patch` | 写入项目（SHA256 校验） | `source_dir`, `target_dir`, `mode` |

### 对比阈值配置

| 配置 | SSIM 阈值 | 像素阈值 | 用途 |
|------|-----------|----------|------|
| `preview_relaxed` | 0.75 | 30% | 快速预览 |
| `hardware_tolerant` | 0.82 | 20% | 硬件容差 |
| `golden_strict` | 0.90 | 10% | 黄金回归 |

---

## 八、嵌入式调试 MCP 工具

除了 LVGL UI 生成工具，项目还提供 3 个嵌入式设备调试 MCP 服务器。

### MQTT MCP（设备消息调试）

连接 MQTT Broker，进行设备消息的发布/订阅/历史查看。

| 工具 | 功能 |
|------|------|
| `mqtt_connect` | 连接 MQTT Broker（支持 TLS/认证） |
| `mqtt_disconnect` | 断开连接 |
| `mqtt_publish` | 发布消息到主题 |
| `mqtt_subscribe` | 订阅主题（支持通配符 +/#） |
| `mqtt_unsubscribe` | 取消订阅 |
| `mqtt_list_topics` | 列出已订阅主题 |
| `mqtt_get_messages` | 读取消息历史（Ring Buffer） |
| `mqtt_clear_messages` | 清空消息历史 |

**使用场景：** 设备日志收集、远程指令下发、传感器数据监控。

### OTA MCP（固件升级管理）

本地固件仓库 + HTTP 服务器 + 设备升级推送。

| 工具 | 功能 |
|------|------|
| `ota_start` | 启动 OTA HTTP 服务器 |
| `ota_stop` | 停止服务器 |
| `ota_server_status` | 查看服务器状态 |
| `ota_upload` | 上传固件到仓库 |
| `ota_list` | 列出固件版本 |
| `ota_delete` | 删除固件版本 |
| `ota_info` | 查看固件详情 |
| `ota_push` | 推送升级通知到指定设备 |
| `ota_push_all` | 推送到所有在线设备 |
| `ota_device_status` | 查看设备状态 |

**使用场景：** 固件版本管理、OTA 升级测试、设备状态监控。

### Serial MCP（串口调试）

串口读写 + 本地 Ring Buffer，AI 按需拉取日志（零 token 浪费）。

| 工具 | 功能 |
|------|------|
| `serial_list` | 列出可用串口 |
| `serial_connect` | 连接串口（自动启动后台读取） |
| `serial_disconnect` | 断开连接 |
| `serial_write` | 发送数据 |
| `serial_get_lines` | 取最近 N 行日志 |
| `serial_search` | 关键词搜索 |
| `serial_get_stats` | 统计信息 |

**设计原则：** 全量本地存储，AI 按需拉取。持续串口输入不消耗 token。

**使用场景：** 串口日志分析、AT 指令调试、设备启动流程诊断。

### 依赖安装

```bash
# MQTT MCP 需要 paho-mqtt
pip install paho-mqtt

# Serial MCP 需要 pyserial
pip install pyserial

# OTA MCP 无额外依赖（使用 Python 标准库）
```

---

## 九、工作流系统

项目定义了 10 个工作流，分为两个层级：

### L2 级（审查/分析）

| 工作流 | 文件 | 用途 |
|--------|------|------|
| `l2_code_review` | `workflows/l2_code_review.md` | 完整代码审查 |
| `l2_code_review_lite` | `workflows/l2_code_review_lite.md` | 轻量审查 |
| `l2_project_review` | `workflows/l2_project_review.md` | 项目级审查 |
| `l2_memory_analysis` | `workflows/l2_memory_analysis.md` | 内存分析 |
| `debug_crash` | `workflows/debug_crash.md` | 崩溃调试 |
| `hw_sw_cocodebug` | `workflows/hw_sw_cocodebug.md` | 软硬件协同调试 |

### L3 级（生成/实现）

| 工作流 | 文件 | 用途 |
|--------|------|------|
| `l3_lvgl_page` | `workflows/l3_lvgl_page.md` | LVGL 页面生成 |
| `l3_lvgl_page_quick` | `workflows/l3_lvgl_page_quick.md` | 快速 LVGL 页面 |
| `l3_new_module` | `workflows/l3_new_module.md` | 新模块生成 |
| `l3_bring_up` | `workflows/l3_bring_up.md` | 板级 Bring-up |
| `l3_sdk_trim` | `workflows/l3_sdk_trim.md` | SDK 裁剪 |

---

## 十、测试与验证

### 运行测试

```bash
# 运行全部测试
pytest

# 只运行 LVGL 测试
pytest tests/lvgl/

# 运行特定测试
pytest tests/test_manifest_v2.py -v

# 运行集成测试
pytest tests/test_mvp_integration.py -v
```

### 测试覆盖范围

- **Manifest v2 验证**：加载、校验、解析、路由、模型、事件
- **App 代码生成**：Router/Presenter/Model/App 的 C/H 生成
- **App 验证器**：路由图、代码结构、线程边界、资源去重
- **LVGL 二进制协议**：资产打包、场景编码、对象树
- **视觉对比**：SSIM 阈值配置、像素对比
- **设计资产安全策略**：设计图 ≠ 运行时资产

### CI/CD

项目配置了 3 个 GitHub Actions 工作流：

1. **`skill-tools.yml`**：核心测试（Python 3.10/3.11/3.12）、MCP 测试、元数据测试、Windows 测试、LVGL 测试
2. **`build-lvgl-simulator.yml`**：构建原生 LVGL 模拟器（Windows + Linux）
3. **`freertos-review-pr.yml`**：PR 触发的 FreeRTOS 代码审查

---

## 十一、平台支持

| 平台 | 配置文件 | 说明 |
|------|----------|------|
| ESP32 | `platforms/esp32.md` + `esp32_quick.md` | ESP-IDF 框架 |
| STM32 | `platforms/stm32.md` + `stm32_quick.md` | STM32 HAL |
| JL/AC79 | `platforms/jl.md` + `jl_quick.md` | 杰理芯片 |
| BK7258 | `platforms/bk.md` + `bk_quick.md` | 博通集成芯片 |
| Zephyr | `platforms/zephyr.md` + `zephyr_quick.md` | Zephyr RTOS |

每个平台都有 `*_sdk_map.yaml` 定义 SDK 路径映射。

---

## 十二、安全与策略

### 设计资产隔离策略

项目强制执行 **设计图 ≠ 运行时资产** 策略（`design_asset_policy.py`）：

- 设计截图仅用于分析和对比，绝不会被打包为运行时资产
- `generate_interactive_scene_page()` 会拒绝将设计图路径作为背景
- `_write_preview_crops()` 已硬禁用

### 路径安全

- `resolve_path()` 阻止路径遍历攻击
- 写操作限制在 `artifacts/` 目录内
- 图片转换器仅接受白名单预设（防止命令注入）

### 原子写入

所有文件写入使用 **临时文件 + `os.replace()`** 模式，确保崩溃安全。

---

## 十三、LVGL 页面生成管线详解

### 管线架构

```
设计截图 (PNG)
    │
    ▼
┌─────────────────┐
│  inspect_design  │  ← 只读分析
│  (preflight +    │     检测区域、颜色、文字、布局
│   analysis)      │     输出: analysis_report.json + debug_overlay.png
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  generate_ui     │  ← 代码生成
│  (codegen +      │     UI Spec → LVGL C/H
│   asset pack)    │     输出: ui_page_*.c/.h + ui_spec.json + asset.pack
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  render_ui       │  ← 渲染验证
│  (scene encode + │     scene.bin → 原生 LVGL 渲染
│   native runner) │     输出: render.png + object_tree.bin
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  compare_ui      │  ← 视觉对比
│  (SSIM + pixel + │     渲染结果 vs 设计基准
│   tree diff)     │     输出: visual_diff.json + diff_overlay.png
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  refine_ui       │  ← 迭代优化（最多 3 轮）
│  (guard +        │     单调递增评分，无临界区回退
│   evidence)      │     输出: best result + improvement history
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  apply_patch     │  ← 写入项目
│  (SHA256 verify +│     原子写入，哈希校验
│   atomic write)  │     输出: 目标目录中的 C/H 文件
└─────────────────┘
```

### 二进制协议格式

#### Asset Pack (.pack)

```
┌──────────────────────────────────────┐
│ Header (16 bytes)                    │
│  magic: "APK\0" (4 bytes)           │
│  version: uint32                     │
│  asset_count: uint32                 │
│  reserved: uint32                    │
├──────────────────────────────────────┤
│ Entry Table (64 bytes × count)       │
│  symbol: char[32]                    │
│  offset: uint32                      │
│  size: uint32                        │
│  width: uint16                       │
│  height: uint16                      │
│  format: uint8 (1=RGB565, 2=RGB565A8,│
│          3=ARGB8888, 4=A8)           │
│  reserved: [padding to 64 bytes]     │
├──────────────────────────────────────┤
│ Pixel Data (contiguous)              │
│  [asset 0 pixels]                    │
│  [asset 1 pixels]                    │
│  ...                                 │
└──────────────────────────────────────┘
```

#### Scene Binary (scene.bin)

```
┌──────────────────────────────────────┐
│ Header (32 bytes)                    │
│  magic: "SCN\0" (4 bytes)           │
│  version: uint32 (=2)               │
│  node_count: uint32                  │
│  string_table_offset: uint32        │
│  string_table_size: uint32          │
│  command_offset: uint32             │
│  command_size: uint32               │
│  reserved: uint32                   │
├──────────────────────────────────────┤
│ String Table (null-terminated UTF-8) │
│  "text1\0text2\0..."                 │
├──────────────────────────────────────┤
│ Command Buffer (packed structs)      │
│  Opcode + payload per command        │
│  CREATE_WIDGET, SET_PARENT, SET_SIZE │
│  SET_TEXT, SET_IMAGE_SOURCE, ...     │
│  END                                 │
└──────────────────────────────────────┘
```

#### Object Tree (object_tree.bin)

```
┌──────────────────────────────────────┐
│ Header (24 bytes)                    │
│  magic: "TEE\0" (4 bytes)           │
│  version: uint32                     │
│  display_width: uint16              │
│  display_height: uint16             │
│  node_count: uint32                 │
│  reserved: [8 bytes]                │
├──────────────────────────────────────┤
│ String Table                         │
├──────────────────────────────────────┤
│ Nodes (44 bytes × count)            │
│  type: uint8                         │
│  x, y, w, h: int16                  │
│  flags: uint8 (clickable, invisible) │
│  child_count: uint16                │
│  text_offset: uint32                │
│  value: int32                        │
│  reserved: [padding]                │
└──────────────────────────────────────┘
```

---

## 十四、典型使用场景

### 场景 1：新项目快速审查

```bash
cd your-firmware-project
python /path/to/skill/tools/run_review.py --target src/
```

### 场景 2：设计稿转 LVGL 页面

在 AI IDE 中：
> "把这个设计截图转成 LVGL v9 页面代码，目标 480x800 RGB565 屏幕"

### 场景 3：多页 App 生成

在 AI IDE 中：
> "根据这个 manifest.json 生成完整的多页 LVGL 应用，包含 Router、Presenter 和 Model"

### 场景 4：崩溃日志诊断

在 AI IDE 中：
> "分析这段 crash log，找出 watchdog reset 的原因：[粘贴日志]"

### 场景 5：LVGL 代码回归测试

```bash
# 运行 12 个黄金页面回归测试
pytest tests/lvgl/test_render_e2e.py -v
```

### 场景 6：标准 UI 包自动生成

在 AI IDE 中：
> "基于 ui/ 目录下的资产，自动生成互动场景页面"

### 场景 7：SDK 裁剪

在 AI IDE 中：
> "帮我裁剪 ESP-IDF SDK，只保留 WiFi + BLE + LVGL 所需组件"

### 场景 8：MQTT 设备调试

在 AI IDE 中：
> "连接本地 MQTT Broker，订阅 device/# 主题，看看设备发了什么消息"

### 场景 9：串口日志分析

在 AI IDE 中：
> "连接 COM3 串口（115200），看看设备启动日志有没有错误"

### 场景 10：OTA 固件升级

在 AI IDE 中：
> "上传 v1.2.0 固件到 ESP32 平台，推送到所有在线设备"

---

## 十五、配置参考

### 显示器默认配置

```python
DISPLAY_CONFIG = {
    "width": 480,
    "height": 800,
    "color_format": "RGB565",  # 16-bit
    "dpi": 160,
    "layout_policy": "flex_grid_first"  # Flex/Grid 优先，禁止绝对定位
}
```

### 资源预算

- **Flash**: 2MB
- **RAM**: 512KB
- 字体 flash 估算：每字形 ≈ `size*size*bpp/8 + 16` 字节

### LVGL 布局硬规则

1. **禁止裸绝对定位** — 必须使用 Flex/Grid 布局，除非标记 `LVGL_LAYOUT_EXCEPTION`
2. **复用 `lv_style_t`** — 不要在循环中重复创建样式
3. **异步 LVGL 操作** — 跨线程调用必须使用 `lv_async_call`
4. **线程安全** — Presenter 中禁止直接创建 `lv_timer_create` / `lv_async_call`

### Manifest v2 路由模式

| 模式 | 行为 |
|------|------|
| `push` | 压栈导航，保留前一页状态 |
| `replace` | 替换当前页，不增加栈深度 |
| `back` | 弹栈返回，销毁当前页 |

### Manifest v2 模型字段类型

| 类型 | 默认值 | 说明 |
|------|--------|------|
| `bool` | `false` | 布尔开关 |
| `int32` | `0` | 32 位整数 |
| `string` | `""` | 字符串（需指定 `max_length`） |

### 事件动作类型

| 动作 | 参数 | 说明 |
|------|------|------|
| `route` | `route: "route_id"` | 触发路由导航 |
| `model_set` | `model: "name", field: "name", value: ...` | 设置模型字段 |
| `model_toggle` | `model: "name", field: "name"` | 切换布尔字段 |
| `set_state` | `page: "id", state: "name"` | 切换页面状态 |

---

## 十六、MCP Server 内部工具

除了 6 个高层工具，MCP Server 还提供以下内部工具（供 AI 路由使用）：

| 工具 | 功能 |
|------|------|
| `list_capabilities` | 列出所有可用能力 |
| `route_context` | 上下文路由（症状 → 工作流/约束） |
| `run_review` | 运行静态审查 |
| `triage_log` | 崩溃日志分诊 |
| `lookup_sdk` | 查询 SDK 信息 |
| `run_gate` | 运行门禁检查 |

### MCP Resources

| URI | 内容 |
|-----|------|
| `lvgl://display-config` | 显示器配置 JSON |
| `lvgl://theme-skill` | LVGL 布局主题规则 Markdown |
| `lvgl://regression-sandbox-config` | 回归测试沙箱配置 |
| `lvgl://regression-sandbox-readme` | 回归测试沙箱说明 |

---

## 十七、常见问题

**Q: Windows 上出现编码错误？**
A: 确保设置环境变量 `PYTHONUTF8=1` 和 `PYTHONIOENCODING=utf-8`（`.mcp.json` 已配置）。

**Q: 没有 Pillow 也能用吗？**
A: 可以。核心代码生成和审查工具零依赖。Pillow 仅用于视觉分析（`inspect_design`）和 OCR。

**Q: 如何添加新的检查器？**
A: 在 `tools/` 下创建 `*_checker.py`，在 `tools/checker_registry.py` 中注册。

**Q: 如何添加新平台支持？**
A: 在 `platforms/` 下添加 `new_platform.md` 和 `new_platform_sdk_map.yaml`，在 `SKILL.md` 路由表中注册。

**Q: golden_pages 是什么？**
A: 12 个黄金页面的回归测试基准。每个页面包含设计图、分析报告、期望输出（C 代码、UI Spec、渲染结果、视觉对比），用于确保代码生成的稳定性。

**Q: forward_tests 是什么？**
A: 前向测试框架，定义了 5 个端到端测试场景（代码审查、崩溃分析、模块生成、项目生成、自动修复），用于验证整个工具链的正确性。

**Q: 如何在 CI 中集成？**
A: 参考 `.github/workflows/freertos-review-pr.yml`，在 PR 触发时运行 `python tools/run_review.py`。

**Q: scene_presets/ 目录是什么？**
A: 预定义的场景配置（audio_video、low_power_sensor、ota_network、pure_controller、voice_screen），用于快速启动特定类型的固件审查。

---

## 十八、版本历史（最近 3 版）

### v46.0.0
- 新增 MQTT MCP Server（设备消息调试，8 个工具）
- 新增 OTA MCP Server（固件升级管理，10 个工具）
- 新增 Serial MCP Server（串口调试，7 个工具，Ring Buffer 本地存储）

### v45.0.0
- 新增设计资产隔离策略（`design_asset_policy.py`）
- 新增标准 UI 包自动发现（`standard_ui_package.py`）
- 新增互动场景页自动生成（`interactive_scene_auto.py`）
- 新增启动页自动生成（`initial_loading_auto.py`）

### v44.0.0
- Manifest v2.1 支持（state designs、resource blocks、bindings、quality regions）
- App v2.1 代码生成器（`app_v21_codegen.py`）
- 原生 LVGL 模拟器构建 CI

### v43.0.0
- Manifest v2.0 多页应用框架
- App 级代码生成（Router/Presenter/Model/App）
- 12 个黄金页面回归测试

完整历史见 `archive/CHANGELOG_FULL.md`。

---

## 十九、相关文档索引

| 文档 | 路径 | 说明 |
|------|------|------|
| 项目概述 | `README.md` | 快速入门 |
| 安装指南 | `INSTALL.md` | 详细安装步骤 |
| 变更日志 | `CHANGELOG.md` | 版本变更 |
| 技能结构 | `references/skill_structure.md` | 架构维护参考 |
| 多页 MVP 计划 | `docs/multi_page_mvp_plan.md` | 多页应用架构设计 |
| 工作流索引 | `workflows/README.md` | 工作流列表 |
| 示例索引 | `examples/README.md` | 约束 → 示例映射 |
| 前向测试 | `forward_tests/README.md` | 端到端测试框架 |
| 约束矩阵 | `references/constraint_*.md` | 45 个约束域详细规则 |
| 平台指南 | `platforms/*.md` | 各平台适配说明 |
