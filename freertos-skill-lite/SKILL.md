---
name: freertos-embedded-architect
version: 2.2.0
description: >-
  Use when reviewing or designing FreeRTOS IoT firmware: MVP layering, LVGL
  thread safety, I2S DMA, cJSON leaks, WSS/mbedTLS, JL/BK SDK trimming.
  Trigger on: HardFault, Guru Meditation, stack overflow, WSS reconnect,
  lv_async_call, code review, sdk trim, AC79, BK7258, embedded C.
  用于 ESP32/STM32/JL/BK 带屏音箱/语音网关的架构设计、Code Review、SDK 裁剪。
---

# FreeRTOS 嵌入式架构专家（Lite 版）

> **Lite**：无 `examples/`、`tools/`。L2 用 [l2_code_review_lite.md](workflows/l2_code_review_lite.md) + [lite_manual_checklist.md](references/lite_manual_checklist.md)。

## 职责边界

| ✅ Skill 负责 | ❌ 不纳入 Skill |
|--------------|----------------|
| FreeRTOS 多任务 / MVP 架构设计与审查 | 字库、图片、OTA、CI |
| LVGL / I2S / WSS / cJSON / SDK 裁剪 | 低功耗设计（仅 review） |
| 人工审查清单 | checker / codegen 脚本 |

## 快速路由

| 用户意图 | Workflow | 级别 |
|----------|----------|------|
| 概念 / 单 API | 无 workflow | L1 |
| Code Review | [l2_code_review_lite.md](workflows/l2_code_review_lite.md) | L2 |
| SDK 改造 / 裁剪 | [l3_sdk_trim.md](workflows/l3_sdk_trim.md) | L3 |
| 新增模块 | [l3_new_module.md](workflows/l3_new_module.md)（跳过 codegen 步骤） | L3 |
| Bug / Crash | [debug_crash.md](workflows/debug_crash.md)（跳过 run_review） | L2–L3 |

**平台**：[esp32](platforms/esp32.md) | [stm32](platforms/stm32.md) | [jl](platforms/jl.md) | [bk](platforms/bk.md)

## 铁律索引

细则 → [references/core_rules.md](references/core_rules.md)（范例路径为完整版 `examples/`）

<thinking>
1. 选定 1 个 workflow
2. 读 1 个 platform 专档
3. 按需 1–3 个 prompt，禁止全加载
</thinking>

<rules>
- L2 必须完成 lite_manual_checklist 并标注「Lite 人工审查已完成」
- 禁止未问卷直接给 SDK 删除清单
</rules>

## 场景 Prompt 索引

同完整版 → `prompts/` 目录（见完整版 SKILL.md 索引表）

## L3 输出模板

见 [core_rules.md](references/core_rules.md) 文末。
