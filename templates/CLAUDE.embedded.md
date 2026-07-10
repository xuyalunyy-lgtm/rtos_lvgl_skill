# 嵌入式固件 — Claude Code 索引（<500 token，勿膨胀）

## Skill
FreeRTOS/LVGL/IoT 架构与审查：invoke **`/freertos-embedded-architect`** 或说明芯片平台。
Skill 路径：`~/.claude/skills/freertos-embedded-architect/`（安装见 skill 仓库 `scripts/install_claude_code.*`）。

## 本平台（必填 — 改下面占位）
- **芯片/SDK：** <!-- JL AC79 / BK7258 Armino / ESP32 / STM32 -->
- **编译：** <!-- make bk7258 / idf.py build / make ac791n_xxx -->
- **源码根：** <!-- src/ 或 projects/xxx/ap/ -->

## Token 规则（每次会话）
1. **禁止** Read/Glob 整个 skill；只读当前 workflow 列出的文件
2. L2 用 `references/constraint_index.md`，非 `constraint_detail.md` 全文
3. **1** 个 `platforms/*.md` + **最多 3** 个 `prompts/*.txt`
4. 范例用 Grep/Read **单文件**；审查用 `python <skill>/tools/run_review.py --dir <src> --platform <x>`

## L3 自主实施
实现/修 Bug：**全权改代码**，无需逐步确认，直至功能完成且 **编译 0 error**。铁律 C1–C8 仍遵守。

## LVGL UI 生成
**必须**使用 MCP 工具链（`get_lvgl_theme_skill` → `convert_image` → `generate_spec` → `generate_code` → `validate`）。禁止绕过 MCP 直接手写 LVGL 页面代码。详见 skill `workflows/l3_lvgl_page.md`。

## 忽略大目录
见同目录 `.claudeignore`（SDK/build 勿进 context）。
