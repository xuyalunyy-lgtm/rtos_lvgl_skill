# Workflow: L3 LVGL 单页面生成

**触发：** 新 UI 页面 / LVGL 代码生成 / 带屏产品页面开发 / UI 布局调整 / LVGL page generation

```yaml
# Workflow Input Schema
inputs:
  required:
    - name: design_screenshot
      type: string
      description: 设计稿截图路径（PNG/JPG）
    - name: cut_assets
      type: string[]
      description: 切图资源路径列表
  optional:
    - name: screen_params
      type: object
      description: "{width, height, color_depth, screen_type}"
    - name: font_resources
      type: array
      description: "[{size, language, path}]"
    - name: color_theme
      type: object
      description: "{primary, secondary, background, text}"
    - name: lvgl_version
      type: enum[v8, v9]
      default: v9

# Workflow Output Schema
outputs:
  format: mixed
  sections:
    - 信息完整度评估（8 项必需信息 checklist）
    - analysis_report.json（资产分析）
    - debug_overlay.png（调试叠加图）
    - LVGL C/H 页面代码
    - preview.html（近似预览）
  verification: validate_lvgl_layout_code exit=0 + 截图像素差异 < 1%
  note: 必须使用 MCP 工具链（get_lvgl_theme_skill → convert_image → generate_spec → generate_code → validate）
```

<thinking>
1. 仅提供「页面组件 + 坐标 + 交互方式」**不足以**生成完美效果
2. 缺少的关键信息：显示参数、字体/图片资源、颜色主题、样式细节、数据绑定、动画、LVGL 版本
3. 本 workflow 定义完整的 LVGL 页面生成所需信息清单，缺一不可
</thinking>

## 信息完整度评估

### 用户已提供（2/8）

| # | 信息 | 状态 | 说明 |
|---|------|------|------|
| 1 | 整体页面 + 组件列表 | ✅ | 页面由哪些组件组成 |
| 2 | 组件坐标 + 交互方式 | ✅ | 位置 (x,y,w,h) + 点击/滑动等 |

### 必须补充（6 项缺一不可）

| # | 信息 | 缺失后果 | 获取方式 |
|---|------|----------|----------|
| 3 | **屏幕参数** | 坐标值无意义（不知道画布大小） | 用户提供：分辨率、色深、屏幕类型 |
| 4 | **字体资源** | 中文/英文/图标字体无法渲染 | 用户提供：字体文件路径、字号列表 |
| 5 | **图片/图标资源** | 图标按钮显示空白 | 用户提供：图片路径、格式（PNG/SJPG/QOI）、是否压缩 |
| 6 | **颜色主题** | 默认配色可能与产品不符 | 用户提供：主色/辅色/背景色/文字色 |
| 7 | **组件样式细节** | 扁平 vs 圆角 vs 阴影等视觉效果不确定 | 用户提供或使用默认模板 |
| 8 | **数据绑定** | 静态页面无法动态更新 | 用户标注哪些文本/值来自运行时数据 |

---

## Step 0 — 收集完整页面规格（必做）

**铁律：信息不完整时，Agent 只能输出框架代码 + TODO 占位，禁止猜测填充。**

### 0.1 强制交互模板

Agent 输出以下模板，要求用户逐项填写：

```markdown
## LVGL 页面规格

### 显示参数
- 屏幕分辨率：____ × ____
- 色深：16-bit (RGB565) / 24-bit (RGB888) / 32-bit (ARGB8888)
- 屏幕类型：TFT LCD / OLED / E-ink
- 触摸类型：电容触摸 / 无触摸（按键导航）/ 旋钮编码器
- LVGL 版本：v8.x / v9.x

### 字体资源
| 字号 | 语言 | 字体文件 | 说明 |
|------|------|----------|------|
| 14px | 中文 | font_cn_14.bin | UI 正文 |
| 20px | 中文 | font_cn_20.bin | 标题 |
| 24px | 英文+数字 | font_en_24.bin | 大字显示 |
| 图标 | — | icon_font_16.bin | 自定义图标字体 |

### 图片/图标资源
| 资源名 | 格式 | 尺寸 | 用途 |
|--------|------|------|------|
| icon_wifi.png | PNG | 32×32 | WiFi 状态图标 |
| bg_main.jpg | SJPG | 240×320 | 主页背景 |
| btn_play.png | PNG | 48×48 | 播放按钮 |

### 颜色主题
| 角色 | 色值 | 说明 |
|------|------|------|
| 主色 (Primary) | #2196F3 | 按钮、选中态 |
| 辅色 (Secondary) | #FF9800 | 强调、警告 |
| 背景色 | #FFFFFF | 页面背景 |
| 文字色 | #212121 | 正文文字 |
| 次要文字 | #757575 | 说明、副标题 |

### 组件详细规格
| 组件 | 坐标 (x,y,w,h) | 样式 | 数据绑定 | 交互 |
|------|-----------------|------|----------|------|
| 状态标签 | 10,10,200,30 | 字号20, 颜色#2196F3 | `g_status_text` (运行时更新) | 无 |
| 播放按钮 | 80,200,80,80 | 圆角12, 阴影, 图标 | 无 | 点击 → `on_play_btn_click()` |
| 进度条 | 10,150,220,10 | 圆角5, 填充#2196F3 | `g_play_progress` (0-100) | 无 |
| 音量滑块 | 10,280,220,30 | — | `g_volume` (0-100) | 拖动 → `on_volume_change()` |

### 动画/过渡
| 触发 | 动画类型 | 时长 | 说明 |
|------|----------|------|------|
| 页面进入 | 淡入 | 300ms | 从透明到不透明 |
| 按钮按下 | 缩放 0.95x | 100ms | 按下反馈 |
| 状态切换 | 滑动 | 200ms | 左右滑动切换页面 |
```

---

## Step 1 — 信息完整性检查

### 1.1 检查清单

| 检查项 | 必要性 | 缺失处理 |
|--------|--------|----------|
| 屏幕分辨率 | 🔴 必须 | 拒绝生成，要求提供 |
| 色深 | 🔴 必须 | 拒绝生成，要求提供 |
| LVGL 版本 | 🔴 必须 | v8/v9 API 差异大，必须确认 |
| 至少 1 个字体 | 🔴 必须 | 无字体无法显示文字 |
| 颜色主题 | 🟡 可选 | 缺失时使用默认 Material Design 配色 |
| 图片资源 | 🟡 可选 | 缺失时用纯色按钮替代 |
| 样式细节 | 🟡 可选 | 缺失时使用默认样式模板 |
| 数据绑定 | 🟡 可选 | 缺失时全部使用静态文本 |

### 1.2 LVGL 版本差异（必须确认）

| API | v8 | v9 |
|-----|----|----|
| 创建对象 | `lv_obj_create(parent)` | `lv_obj_create(parent)` |
| 设置文本 | `lv_label_set_text(obj, text)` | `lv_label_set_text(obj, text)` |
| 样式设置 | `lv_obj_set_style_*()` | `lv_obj_set_style_*()` |
| 字体加载 | `lv_font_load("path")` | `lv_binfont_create("path")` |
| 图片解码 | `lv_img_set_src(obj, "S:path")` | `lv_image_set_src(obj, "S:path")` |
| 动画 | `lv_anim_t` | `lv_anim_t`（API 类似） |
| 回调 | `lv_obj_add_event_cb(obj, cb, event, data)` | `lv_obj_add_event_cb(obj, cb, event, data)` |
| Flex 布局 | `lv_obj_set_flex_flow()` | `lv_obj_set_flex_flow()` |
| Grid 布局 | `lv_obj_set_grid_dsc_array()` | `lv_obj_set_grid_dsc_array()` |
| 颜色创建 | `lv_color_hex(0xRRGGBB)` | `lv_color_hex(0xRRGGBB)` |

---

## Step 1.5 — MCP 工具链强制检查（必做）

**铁律：禁止跳过 MCP 工具直接生成 LVGL C 代码。**

在生成任何 LVGL 页面代码前，必须按序调用 MCP 工具：

| 顺序 | MCP 工具 | 作用 | 跳过后果 |
|------|----------|------|----------|
| 1 | `get_lvgl_theme_skill` | 加载 Flex/Grid 布局约束和显示配置 | 可能使用绝对坐标，违反布局策略 |
| 2 | `convert_image_to_lvgl_source` | 将设计切图转为 RGB565 C-array | 图片资源格式不匹配，编译失败 |
| 3 | `generate_lvgl_layout_spec` | 生成结构化布局规格 JSON | 缺少规格校验，代码质量不可控 |
| 4 | `generate_lvgl_page_code` | 从 spec 生成 C/H scaffold | 手写代码难以保证一致性 |
| 5 | `validate_lvgl_layout_code` | 校验生成代码的布局和约束 | 坐标/尺寸错误无法提前发现 |

### 执行要求

- 每一步都必须实际调用 MCP 工具并获取返回值，不能"跳过因为已有信息"
- 步骤 2（图片转换）仅在有设计切图时执行，无切图可跳过
- 如果 MCP server 连接失败，先尝试排查连接问题；确认无法修复后才可回退到手动流程
- 回退手动流程时，必须在输出中标注 `[MCP unavailable - manual fallback]`

---

## Step 2 — 代码生成

### 2.1 代码结构模板

```c
/**
 * @file ui_page_xxx.c
 * @brief LVGL 页面：XXX（自动生成）
 * @warning 修改布局前必须更新页面规格文档
 */

#include "lvgl.h"
#include "board_io.h"
#include "ui_theme.h"      /* 颜色主题定义 */
#include "ui_font.h"       /* 字体资源声明 */
#include "ui_img.h"        /* 图片资源声明 */

/* ── 页面根对象 ─────────────────────── */
static lv_obj_t *s_page = NULL;

/* ── 组件句柄（需要动态更新的组件）─── */
static lv_obj_t *s_status_label = NULL;
static lv_obj_t *s_progress_bar = NULL;

/* ── 事件回调 ───────────────────────── */
static void on_play_btn_click(lv_event_t *e)
{
    (void)e;
    /* TODO: 播放逻辑 */
}

/* ── 页面创建 ───────────────────────── */
lv_obj_t *ui_page_xxx_create(lv_obj_t *parent)
{
    s_page = lv_obj_create(parent);
    lv_obj_set_size(s_page, DISP_HOR_RES, DISP_VER_RES);
    lv_obj_set_style_bg_color(s_page, lv_color_hex(0xFFFFFF), 0);

    /* 状态标签 */
    s_status_label = lv_label_create(s_page);
    lv_obj_set_pos(s_status_label, 10, 10);
    lv_obj_set_size(s_status_label, 200, 30);
    lv_obj_set_style_text_font(s_status_label, &font_cn_20, 0);
    lv_obj_set_style_text_color(s_status_label, lv_color_hex(0x2196F3), 0);
    lv_label_set_text(s_status_label, "Ready");

    /* 播放按钮 */
    lv_obj_t *play_btn = lv_btn_create(s_page);
    lv_obj_set_pos(play_btn, 80, 200);
    lv_obj_set_size(play_btn, 80, 80);
    lv_obj_set_style_radius(play_btn, 12, 0);
    lv_obj_set_style_bg_color(play_btn, lv_color_hex(0x2196F3), 0);
    lv_obj_add_event_cb(play_btn, on_play_btn_click, LV_EVENT_CLICKED, NULL);

    /* 进度条 */
    s_progress_bar = lv_bar_create(s_page);
    lv_obj_set_pos(s_progress_bar, 10, 150);
    lv_obj_set_size(s_progress_bar, 220, 10);
    lv_bar_set_range(s_progress_bar, 0, 100);
    lv_bar_set_value(s_progress_bar, 0, LV_ANIM_OFF);

    return s_page;
}

/* ── 外部更新接口（Presenter 调用）── */
void ui_page_xxx_set_status(const char *text)
{
    if (s_status_label != NULL && text != NULL) {
        lv_label_set_text(s_status_label, text);
    }
}

void ui_page_xxx_set_progress(int32_t value)
{
    if (s_progress_bar != NULL) {
        lv_bar_set_value(s_progress_bar, value, LV_ANIM_ON);
    }
}
```

### 2.2 主题文件模板

```c
/**
 * @file ui_theme.h
 * @brief UI 颜色主题（来自页面规格）
 */
#ifndef UI_THEME_H
#define UI_THEME_H

#define UI_COLOR_PRIMARY      0x2196F3
#define UI_COLOR_SECONDARY    0xFF9800
#define UI_COLOR_BG           0xFFFFFF
#define UI_COLOR_TEXT          0x212121
#define UI_COLOR_TEXT_SECONDARY 0x757575

#endif /* UI_THEME_H */
```

---

## Step 3 — MVP 联动检查（C1 约束）

**铁律（C1.1）：UI 更新必须通过 `lv_async_call` 或在 LVGL Task 内执行。**

生成代码时检查：
- [ ] 所有 `lv_obj_*` 调用在 UI Task 或 `lv_async_call` 回调中
- [ ] `ui_page_xxx_set_status()` 等外部接口线程安全（通过 `lv_async_call` 包装）
- [ ] 数据绑定变量的更新走 Queue → Presenter → View 路径
- [ ] 无跨线程直接操作 `lv_obj_t *`

---

## Step 4 — 内存与性能检查

### 4.1 帧缓冲估算

| 配置 | 计算 | 示例 (240×320, RGB565) |
|------|------|------------------------|
| 全帧缓冲 | W × H × BPP / 8 | 240 × 320 × 2 = 153,600 B |
| 1/10 缓冲 | W × (H/10) × BPP / 8 | 240 × 32 × 2 = 15,360 B |
| 双缓冲 | 全帧 × 2 | 307,200 B |

- 帧缓冲放 PSRAM（ESP32）或内部 SRAM（STM32），见 C7.8
- 大屏（>320×480）建议 PSRAM 帧缓冲 + 1/10 刷新

### 4.2 图片资源优化

| 格式 | 压缩率 | 解码速度 | 适用场景 |
|------|--------|----------|----------|
| PNG | 高 | 慢 | 静态图标 |
| SJPG | 中 | 中 | 大背景图（LVGL 特有） |
| QOI | 中 | 快 | 需要快速解码的场景 |
| RAW | 无 | 最快 | 小图标、频繁使用 |

---

## Step 5 — 输出

```markdown
## LVGL 页面生成报告

### 页面规格确认
- 分辨率：____ × ____
- 色深：____
- LVGL 版本：____
- 字体：____
- 颜色主题：____

### 生成文件
- ui_page_xxx.c — 页面代码
- ui_theme.h — 颜色主题
- ui_font.h — 字体声明（或引用已有）

### MVP 联动
- [ ] 所有 lv_obj_* 在 UI Task 内
- [ ] 外部接口通过 lv_async_call
- [ ] 数据绑定走 Queue → Presenter → View

### 内存估算
- 帧缓冲：__ bytes
- 字体：__ bytes
- 图片：__ bytes
- 总 UI 内存：__ bytes

### 待用户确认
- [ ] 颜色主题是否正确
- [ ] 字体资源是否就位
- [ ] 图片资源是否就位
```

---

## 与其他 Workflow 的关系

| 前置 | 后续 | 联动 |
|------|------|------|
| 用户提供页面规格 | 本 workflow | 信息不完整时拒绝生成 |
| 本 workflow | **l3_bring_up** 阶段 2.5 | LVGL 验证 |
| 本 workflow | **l2_code_review** | 审查 C1 线程安全 |
| **hw_sw_cocodebug** | 本 workflow | 屏幕引脚确认（SPI/I2C LCD） |

---

## 总结：生成完美 LVGL 页面所需完整信息

| 序号 | 信息 | 必要性 | 当前状态 |
|------|------|--------|----------|
| 1 | 整体页面 + 组件列表 | 🔴 必须 | ✅ 已提供 |
| 2 | 组件坐标 + 交互方式 | 🔴 必须 | ✅ 已提供 |
| 3 | 屏幕参数（分辨率/色深/类型） | 🔴 必须 | ❌ 缺失 |
| 4 | LVGL 版本（v8/v9） | 🔴 必须 | ❌ 缺失 |
| 5 | 字体资源（字号/语言/文件路径） | 🔴 必须 | ❌ 缺失 |
| 6 | 颜色主题（主色/辅色/背景/文字） | 🟡 推荐 | ❌ 缺失时用默认 |
| 7 | 图片/图标资源 | 🟡 推荐 | ❌ 缺失时用纯色替代 |
| 8 | 数据绑定（哪些值来自运行时） | 🟡 推荐 | ❌ 缺失时用静态文本 |

**结论：仅提供 1+2 不足以生成完美效果。至少还需补充 3+4+5 三项（屏幕参数、LVGL 版本、字体资源）。**
---
---

## MCP-assisted LVGL UI Generation

Use the MCP resources before generating page code from design screenshots or cut images:

1. Read `lvgl://display-config` for resolution, color depth, LVGL version, fonts, and asset policy.
2. Read `lvgl://theme-skill` or call `get_lvgl_theme_skill` for hard layout rules.
3. Convert cut images with `convert_image_to_lvgl_source` before referencing them in C code.
4. Create a structured spec with `generate_lvgl_layout_spec`, then generate C/H scaffolding with `generate_lvgl_page_code`.
5. Run `validate_lvgl_layout_code` before delivering or committing generated LVGL UI code.
6. For one-shot rendering, call `lvgl_render` to get `render.png`, `object_tree.json`, and diagnostics.
7. For regression, call `run_lvgl_ui_regression`; it uses `lvgl_render` output and compares pixels, optional object-tree JSON, and logs against baselines.

Hard layout policy: prefer Flex/Grid containers. Do not use `lv_obj_set_pos`, `lv_obj_set_x`, or `lv_obj_set_y` unless the line is immediately justified by `LVGL_LAYOUT_EXCEPTION: <reason>`.


## 现场调试补充：带 TF 资源和本地媒体的 LVGL 页面

当页面开发包含 TF 卡资源、JPEG/PNG、触摸切页或音视频播放时，改坐标前先完成这些检查：

1. 分开验证存储和解码器。TF 卡挂载成功不代表 PNG/JPEG 解码已经启用并链接。
2. 所有图片访问必须走公共资源层。HOME/PUSH/Schedule 等页面不要散落直接 `lv_img_set_src(...jpg path)` 或裸路径。
3. 全屏背景和小图标采用不同缓存策略。背景可按页 lazy load/保留；返回、电池、收藏、播放、WiFi 成功/失败等小图标应解码一次并复用。
4. 页面创建和媒体生命周期分离。页面代码只创建 LVGL 对象；媒体代码只上报状态，并请求 UI 任务跳转。
5. 任何异步 UI RPC 都必须有 completion 边界。不能在 RPC 投递成功时清除 busy/playing/transition 状态，必须等 UI 回调完成实际 reload/navigation 后再清。
6. `PAGE_TRANSITION_PENDING`、`VIDEO_PLAYING`、`VIDEO_UI_NAV_PENDING` 期间，触摸、返回、重复启动都要忽略。

视频播放结束并进入下一页的验收日志：

```text
video start accepted
video done, nav next
ui nav/reload entered
ui nav/reload returned
video ui nav done
```

如果设备在 `video ui nav done` 前重启或卡住，优先查 UI 页面构建、资源解码和对象生命周期；如果在 `video ui nav done` 后才出问题，再查下一页自身运行逻辑。

### JL/AC792 现场排查清单：页面栈、资源缓存、媒体状态机

遇到“页面不显示、切页低 FPS、视频/音频结束后误跳页或重启”时，按下面顺序查，不要先改坐标：

1. **页面对象层级：** 普通页面必须创建为公共 `content_layer` 的 child；只有 root screen 可以 `lv_obj_create(NULL)`。禁止对 screen 调用 `lv_obj_set_parent()`，日志出现 `Can't set the parent of a screen` 时优先修 page factory，而不是扩大栈或内存。
2. **背景生命周期：** 如果用单例 root 背景层，必须给每个页面容器登记自己的背景 path/fallback；缓存页面重新显示时先恢复背景，再显示页面。否则返回/下一页会沿用上一页背景。
3. **JPEG 解码成本：** 480×800 JPEG 每次解码可能触发 `jpeg_dec0_task` 并耗时数百毫秒，现场表现为整页刷新 1 FPS。大背景可用公共层 lazy load；Schedule card、封面、小组件优先用已解码 PNG/RAW descriptor，JPEG 只做 fallback。
4. **LVGL 图片缓存：** `LV_IMG_CACHE_DEF_SIZE` 很小时，背景 JPEG 和卡片 JPEG 会互相挤掉缓存。不要误以为页面对象缓存等同于图片像素缓存；对象还在，文件图片仍可能重解码。
5. **PNG 支持确认：** “LVGL 支持 PNG”不等于工程已链接 PNG 解码器。先确认 `LV_USE_PNG`、解码实现和链接符号；避免临时引入第三方解码函数导致 `undefined reference`。
6. **点击层防重入：** 页面切换完成后保留短 guard window；媒体播放、`UI_NAV_PENDING`、page transition 期间忽略全屏点击和返回，避免一次触摸穿透成下一次导航。
7. **音频/视频事件映射：** 不要把底层未知 stream event 默认映射成 ERROR。只对明确 START/STOP/END/真实故障改变业务状态；`STREAM_EVENT_NONE` 或未知事件应忽略或只低频记录，否则会出现“音频实际在播，但 UI 状态已 idle 并允许切页”。

建议日志锚点：

```text
page root ready
asset bg root update/reuse: ...
page cache hit/store/evict id=...
click ignored during guard
file start: ...
healing audio start/stop
video done, nav next
video ui nav done
```

判断优先级：

- 有 `Can't set the parent of a screen` 或 hmem access exception：先查 screen/container 生命周期。
- 有大量 `jpeg_dec0_task` 且每次 0.5s 左右：先查 JPEG 重解码和 LVGL 图片缓存。
- 音频页直接跳过但底层 `file play` 正常：先查 stream event 到业务事件的映射和 `is_playing()` 是否参考底层 player。


## Field Debug Addendum: JL LVGL resource/media/page-switch checklist (2026-07-07)

Use this checklist when a JL/AC792/WL83 LVGL product shows any of these symptoms: full-page switch drops to 1-2 FPS, PNG/JPEG assets partly disappear, HOME/PUSH backgrounds differ from design, video returns to the wrong page, audio page immediately advances, or touch becomes invalid after media playback.

### 1. Separate storage, decoder, resource layer, and layout

- First prove the TF/USB filesystem path is valid with a tiny known-good file. A visible JPEG background only proves storage and one decoder path; it does not prove PNG icons, cached descriptors, or other prefixes are valid.
- Do not assume "LVGL supports PNG" means the current firmware links a PNG decoder. Confirm `LV_USE_PNG`, decoder registration, and final link symbols. `undefined reference to lodepng_decode32` means declarations/calls exist but implementation is not linked.
- Use design screenshots only as visual references. Build production pages from BG + ICON + text/components so assets can be reused and states can be updated independently.
- Route all page image access through a common resource layer. Avoid direct `lv_img_set_src(...jpg path)` scattered in HOME/PUSH/Schedule pages because it makes cache policy, fallback, and path fixes impossible to apply globally.

### 2. Diagnose full-page switch at 1 FPS

- Check logs for repeated full-screen JPEG decode, for example `jpeg_dec0_task` around every tap. If present, the bottleneck is synchronous image decode/reload, not LVGL draw itself.
- Keep recently used page containers alive when RAM allows, but remember object caching is not pixel/decoder caching. Also cache shared background descriptors or root background image objects.
- For root-level backgrounds, restore the page's registered background path whenever a cached page is shown again. Page cache without background restore can display the previous page's background.
- Do not decode large images, scan directories, or destroy/recreate an entire page tree inside the touch event callback. Mark transition busy, post navigation to the UI task, then return.
- Add timing logs around `page create begin/end`, `asset bg decode begin/end`, and `page transition done`; the slow segment should be visible without guessing.

### 3. Media playback and UI navigation state machine

Playback completion is not the same as UI navigation completion. Use an explicit tail state:

```c
typedef enum {
    MEDIA_IDLE = 0,
    MEDIA_STARTING,
    MEDIA_PLAYING,
    MEDIA_UI_NAV_PENDING,
} media_ui_state_t;
```

Rules:

- `IDLE/STARTING -> PLAYING`: only after the player reports accepted/start, or after a monitor confirms the low-level player is running.
- `PLAYING -> UI_NAV_PENDING`: when audio/video end is detected and a UI next-page request has been posted.
- `UI_NAV_PENDING -> IDLE`: only after the UI task has actually completed page reload/navigation.
- While state is not `IDLE`, ignore full-screen click, back, and repeated start requests unless the product explicitly defines cancel behavior.
- `is_playing()` must consider both the business state and the low-level player. If the business state was reset too early but the player is still running, the page may accept a tap and switch away during playback.

Required boundary logs:

```text
media start request accepted
media playback observed running
media done, nav next requested
ui nav/reload entered
ui nav/reload returned
media ui nav done
click ignored during media/transition
```

If the audio page immediately switches but the file is actually playing, inspect event mapping first: unknown/none stream events must not be treated as STOP/ERROR. If the page freezes after audio start, inspect whether UI busy is released only by a completion callback that never fires.

### 4. Video overlay on JL display layers

- For short video overlay, keep LVGL and `fb0` alive. Do not close/reopen the LVGL framebuffer as part of video playback.
- Put video on a dedicated top layer/framebuffer such as `fb4`, then request UI navigation through the UI task after playback ends.
- Media callbacks must not directly create/delete LVGL objects. They should post UI work and wait for UI completion state.

### 5. Fast triage table

| Symptom | First suspicion | First check |
|---|---|---|
| PNG files exist but icons are blank | PNG decoder/config/link missing | `LV_USE_PNG`, decoder registration, link errors/map |
| JPEG background shows but HOME background is wrong | Page bypasses common resource layer or cached background not restored | direct `lv_img_set_src` paths, page background registration |
| Every page switch drops to 1 FPS | synchronous full-screen decode or full tree rebuild | `jpeg_dec0_task`, asset decode timing logs |
| Touch becomes invalid after media | transition/media busy state never completed or input not re-enabled | UI completion callback logs |
| Audio page advances on tap while audio plays | business state reset too early or unknown event mapped to stop/error | stream event mapping and `is_playing()` implementation |
| Video ends then device reboots | display/layer lifecycle or reentrant UI navigation | `fb0` close/reopen logs, `MEDIA_UI_NAV_PENDING` guard |

## Design-to-LVGL Quick Path Addendum (2026-07-09)

This addendum records the quick path procedure from design screenshot to LVGL code,
applicable to MCP/Agent-assisted scenarios. The goal is to cover 80% of common page
types and reduce the need for full interactive collection each time.

### Input Classification

1. Classify input assets into four types: `design screenshot`, `runtime cut asset`,
   `reference crop`, `component-only`.
2. Design screenshots are used for overall layout analysis and component positioning,
   not directly as runtime image assets.
3. Cutout assets must be confirmed for position via template matching or residual
   analysis; do not place them directly into LVGL code based on visual guesswork.
4. Reference crops and component images are used only for calibration; final runtime
   assets go through manifest or resource registration under the `ui/` directory.

### Required Artifacts

Every quick path generation must produce:

- `analysis_report.json`: page layout tree, component source evidence, bbox,
  confidence, fallback strategy.
- `debug_overlay.png`: overlay of current detection results for manual verification.
- Optional intermediate images: e.g., `debug_loading_template_match.png`.
- `preview.html`: approximate browser preview for quick visual check only; not
  visual proof.

The final response should report audit and validation results, not full JSON/code dumps.

### Detection Strategy

1. Perform residual analysis on background, extract residual connected components,
   sort by bbox size and position.
2. Template-match residual regions, rank by improvement (background_error -
   composite_error), not absolute error.
3. Small icons (e.g., 70x70 loading mark) should be matched within candidate windows
   first, avoiding full-screen brute force. On failure, mark
   `source: button_center_fallback` in JSON.
4. Status bar icons (battery, WiFi, bluetooth) should be processed by region groups
   to avoid per-icon full-screen search timeouts.

### Code Generation Constraints

1. Every component in `analysis_report.json` must have a source field:
   `template_match`, `bright_circle_detection`, `button_bounds_fallback`.
2. C code `lv_obj_set_pos` / `lv_obj_set_size` must reference bbox detection results
   and carry `LVGL_LAYOUT_EXCEPTION` comments.
3. Circular buttons/icons must not use the detected outer frame size directly (e.g.,
   84x84 glass container); distinguish outer frame (251x251) from inner icon
   (40x40 -> 70x70 centered).
4. All text and image resources must use macro definitions: `UI_TEXT_*`,
   `UI_IMG_SRC_*`, `UI_FONT_*`.
5. External data update interfaces must use async post helpers; do not call LVGL API
   from non-LVGL threads.

### Validation Flow

1. Quick path: Pillow preview + `validate_lvgl_layout_code`, validate JSON/C
   consistency.
2. `lvgl_render` / `run_lvgl_ui_regression` can be used for more precise regression
   validation, but can be skipped in quick path phase.
3. If detection results are uncertain (step 2 residual analysis did not converge),
   preserve artifacts and mark for manual confirmation; do not force code generation.
4. Large JPEG images should be marked as runtime resource path / lazy load; do not
   convert to C array (too large).

### Limitations

Quick path has clear applicability boundaries:

- Highly customized pages (non-standard layout, complex animation) still require
  full interactive flow.
- Automatic detection of glass/blur effects is not yet supported; requires manual
  annotation in overlay.
- Multi-state pages (e.g., loading -> ready -> error) need each state handled
  separately.

## Design-to-LVGL Cutout Capture Addendum (2026-07-09)

This addendum captures the corrected operating procedure from the sub-screen loading page case.

### Problem Pattern

A design page can appear mostly correct while still missing important cutouts. Common misses include bluetooth/status icons, battery glyphs, loading marks, and small top-bar slices. The main causes are:

- Ranking template matches by absolute composite error instead of improvement over background.
- Treating a high-confidence cutout as a generated widget too early.
- Silently dropping low-confidence or state-variant slices instead of recording them.
- Spending minutes on repeated full-screen brute force searches.

### Required Artifacts

For every design-to-code run, write these artifacts:

- `analysis_report.json`: page layout tree and component source evidence.
- `cutout_audit.json`: one entry for every input cut image.
- `debug_overlay.png`: current corrected overlay.
- `debug_overlay_vN.png`: previous overlays when a detection is corrected.
- `preview.html`: approximate browser preview only; it is not visual proof.

### Matching Rule

Use this score first:

```text
improvement = background_error - composite_error
```

A real cutout may not have the lowest absolute composite error. Background-like false positives often have low absolute error because the background already resembles the design there. A match is stronger when placing the cutout improves the design/background residual by a large positive amount.

### Cutout Audit Status

Every cut image must be classified:

| Status | Meaning | Codegen action |
|---|---|---|
| `used_cutout` | High-confidence visible image layer | Generate image object and `UI_IMG_SRC_*` macro |
| `used_component_calibration` | Slice matches but dynamic widget is preferred | Generate widget, cite slice as calibration evidence |
| `duplicate_or_low_confidence` | Weak or overlaps stronger match | Do not use by default; keep report entry |
| `unmatched_or_state_variant` | Not visible in current state | Preserve asset and report for later state pages |

### Cutout vs LVGL Component Decision

Default to visual parity first. If battery, bluetooth, wifi, loading mark, or other status glyphs are high-confidence cutouts, use the cutout by default. If runtime updates are needed, expose a macro switch for a dynamic LVGL implementation, for example:

```c
#ifndef UI_SUB_LOADING_USE_BATTERY_CUTOUT
#define UI_SUB_LOADING_USE_BATTERY_CUTOUT 1
#endif
```

When the macro is `1`, use the cutout. When it is `0`, use the LVGL component path.

### Speed Rule

Quick generation should not spend minutes on brute-force matching. Use this order:

1. Detect residual connected components after subtracting known background/cutouts.
2. Build candidate windows around status bars, loading areas, panels, buttons, and residual components.
3. Match alpha-active pixels only inside candidate windows.
4. Fall back to full-screen search only for unresolved high-priority assets.
5. If the time budget is exceeded, stop and mark remaining slices in `cutout_audit.json` as low-confidence or unmatched.

The final response should report the audit result and validation result, not full JSON/code dumps.


### Glass And Blur Layers

Do not treat a matched inner icon as proof that the whole visual component is complete. A loading icon inside a frosted circular frame has two layers: the inner icon/cutout and the outer glass component. Generate both layers. Record CSS-like parameters such as `backdrop-filter: blur(12px)` and inset highlights in the report, and emit a renderer hook macro when stock LVGL cannot express the effect directly.

For the sub-screen loading page, the required pattern is: 84x84 outer glass circle at x=198, y=147 with blur radius 12 and left/right `#FFFFFFB2` inset highlights, then the 60x60 loading mark cutout centered at x=210, y=159.

---
验收标准：[acceptance_criteria.md](../references/acceptance_criteria.md#lvgl-page-generationl3_lvgl_page)
