---
name: freertos-embedded-architect
metadata:
  version: 4.13.3
description: >-
  FreeRTOS embedded architecture specialist for MVP firmware, board bring-up,
  runtime reliability, memory safety, LVGL/DMA/ISR safety, SDK trimming, crash
  debugging, and Zephyr-style RTOS project skeletons. Use when the user asks
  for FreeRTOS, embedded C, GPIO, LCD/OLED, frame buffer, camera, audio/video,
  A/V sync, codec/sample-rate, zero-copy, DMA cache, frame pool, WDT, OTA,
  HardFault, stack overflow, Guru Meditation, code review, or git commit help.
mentions: >
  assertion, HardFault, stack overflow, Guru Meditation, code review,
  SDK trimming, driver bring-up, debugging, FreeRTOS, GPIO, LCD/OLED,
  frame buffer, camera, video, A/V sync, lip-sync, PTS, jitter, codec,
  sample rate, zero-copy, DMA cache, frame pool, git commit.
---

# FreeRTOS 嵌入式架构专家（Lite 版）

> **Lite**：无 `examples/`、`tools/`。L2 → [l2_code_review_lite.md](workflows/l2_code_review_lite.md) + [lite_manual_checklist.md](references/lite_manual_checklist.md)。**结构** → [skill_structure.md](references/skill_structure.md)

## 职责边界

| ✅ Skill 负责 | ❌ 不纳入 Skill |
|--------------|----------------|
| FreeRTOS 多任务 / MVP 架构设计与审查 | 字库、图片、OTA、CI |
| LVGL / I2S / WSS / cJSON / SDK 裁剪 | 低功耗设计（仅审查/校验用户方案，不主动设计 sleep 策略） |
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

**平台**：[esp32](platforms/esp32.md) | [stm32](platforms/stm32.md) | [jl](platforms/jl.md) | [bk](platforms/bk.md)

## 铁律索引

细则 → [core_rules.md](references/core_rules.md) · **C#.#** → [constraint_detail.md](references/constraint_detail.md)

| # | 主题 | Prompt |
|---|------|--------|
| 1 | LVGL（C1） | [lvgl_thread_safety.txt](prompts/lvgl_thread_safety.txt) |
| 2 | Queue（C2） | [memory_ownership.txt](prompts/memory_ownership.txt) |
| 3 | cJSON（C3） | [cjson_safe_parse.txt](prompts/cjson_safe_parse.txt) |
| 4 | ISR（C4） | [audio_dma_pingpong.txt](prompts/audio_dma_pingpong.txt) |
| 5 | 测试宏（C5） | [test_mode_macro.txt](prompts/test_mode_macro.txt) |
| 6 | SDK（C6） | [sdk_trim_prune.txt](prompts/sdk_trim_prune.txt) |
| 7 | 内存（C7） | [memory_alloc_optimize.txt](prompts/memory_alloc_optimize.txt) |
| 8 | 启动/WDT（C8） | [boot_wdt_lifecycle.txt](prompts/boot_wdt_lifecycle.txt) |

Prompt 全表 → [skill_structure.md](references/skill_structure.md)

Audio/WSS 现场联调 → [voice_asr_uplink.txt](prompts/voice_asr_uplink.txt) + [mbedtls_wss_memory.txt](prompts/mbedtls_wss_memory.txt) + [peripheral_shutdown_safety.txt](prompts/peripheral_shutdown_safety.txt)

<thinking>
1. 选定 1 个 workflow（见 workflows/README.md）
2. L2+ 读 core_rules + constraint_index（detail 按需）
3. 1 个 platform + 1–3 prompt，禁止全加载
4. L2 完成 lite_manual_checklist
</thinking>

<rules>
- **L3 实现/修 Bug：全权改代码、无需逐步确认，直至功能完成且编译通过**（见 core_rules）
- L2+ 违规报告须引用 `C#.#`
- L2 必须标注「Lite 人工审查已完成」
- 禁止未问卷直接给 SDK 删除清单（C6.1）
</rules>

## 自我迭代

[self_iterate.md](workflows/self_iterate.md) · [iteration_log.md](references/iteration_log.md) · [CHANGELOG.md](CHANGELOG.md) · 完整版跑 `sync_lite.cmd`

## L3 输出模板

见 [core_rules.md](references/core_rules.md) 文末。
