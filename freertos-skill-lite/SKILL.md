---
name: freertos-embedded-architect
version: 2.5.0
description: >-
  Use when reviewing or designing FreeRTOS IoT firmware: MVP layering, LVGL
  thread safety, I2S DMA, cJSON leaks, WSS/mbedTLS, JL/BK SDK trimming.
  Trigger on: HardFault, Guru Meditation, stack overflow, WSS reconnect,
  lv_async_call, code review, sdk trim, skill update, skill iterate,
  AC79, BK7258, embedded C.
  用于 ESP32/STM32/JL/BK 带屏音箱/语音网关的架构设计、Code Review、SDK 裁剪、Skill 自我迭代。
---

# FreeRTOS 嵌入式架构专家（Lite 版）

> **Lite**：无 `examples/`、`tools/`。L2 → [l2_code_review_lite.md](workflows/l2_code_review_lite.md) + [lite_manual_checklist.md](references/lite_manual_checklist.md)。

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
| 新增模块 | [l3_new_module.md](workflows/l3_new_module.md) | L3 |
| Bug / Crash | [debug_crash.md](workflows/debug_crash.md) | L2–L3 |
| **Skill 自我迭代** | [self_iterate.md](workflows/self_iterate.md) | L3 |

**平台**：[esp32](platforms/esp32.md) | [stm32](platforms/stm32.md) | [jl](platforms/jl.md)（AC79/WL82/AC791N）| [bk](platforms/bk.md)

## 铁律索引

细则 → [references/core_rules.md](references/core_rules.md)（范例见完整版 `examples/`，共享类型 `examples/app_mvp.h`）

1. LVGL 后台禁止 `lv_obj_*` → [lvgl_thread_safety.txt](prompts/lvgl_thread_safety.txt)
2. Queue 禁止 cJSON* / 栈指针 → [memory_ownership.txt](prompts/memory_ownership.txt)
3. cJSON 同函数 Delete → [cjson_safe_parse.txt](prompts/cjson_safe_parse.txt)
4. ISR 仅 `*FromISR` → [audio_dma_pingpong.txt](prompts/audio_dma_pingpong.txt)
5. `APP_TEST_MODE_*` 每模块 → [test_mode_macro.txt](prompts/test_mode_macro.txt)
6. SDK 先问卷再裁剪 → [sdk_trim_prune.txt](prompts/sdk_trim_prune.txt)

<thinking>
1. 选定 1 个 workflow
2. 读 1 个 platform 专档
3. 按需 1–3 个 prompt，禁止全加载
4. L2 完成 lite_manual_checklist
</thinking>

<rules>
- L2 必须标注「Lite 人工审查已完成」
- 禁止未问卷直接给 SDK 删除清单
</rules>

## 场景 Prompt 索引（按需加载）

| 场景 | 文件 |
|------|------|
| SDK 裁剪 | [sdk_trim_prune.txt](prompts/sdk_trim_prune.txt) |
| LVGL 线程 / v8v9 | [lvgl_thread_safety.txt](prompts/lvgl_thread_safety.txt) · [lvgl_v8_v9_diff.txt](prompts/lvgl_v8_v9_diff.txt) |
| 音频 DMA | [audio_dma_pingpong.txt](prompts/audio_dma_pingpong.txt) |
| cJSON / WSS | [cjson_safe_parse.txt](prompts/cjson_safe_parse.txt) · [mbedtls_wss_memory.txt](prompts/mbedtls_wss_memory.txt) |
| Crash | [crash_log_decode.txt](prompts/crash_log_decode.txt) |
| Queue / 同步 / 死锁 | [queue_event_bus.txt](prompts/queue_event_bus.txt) · [freertos_sync_primitives.txt](prompts/freertos_sync_primitives.txt) · [deadlock_lock_order.txt](prompts/deadlock_lock_order.txt) |

## 自我迭代

维护 skill 时读 [self_iterate.md](workflows/self_iterate.md)，更新 [iteration_log.md](references/iteration_log.md) 与 [CHANGELOG.md](CHANGELOG.md)，运行 `sync_lite.py`（完整版仓库）。

## L3 输出模板

见 [core_rules.md](references/core_rules.md) 文末。
