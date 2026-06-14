---
name: freertos-embedded-architect
version: 2.19.0
description: >-
  审查与设计 FreeRTOS 物联网固件：MVP 分层、LVGL 线程安全、I2S/DMA、cJSON 泄漏、
  WSS/mbedTLS、内存优化、启动/WDT、SDK 裁剪、密钥安全、共享引擎语音 uplink/ASR 时序。
  Use when user mentions: 死机, 崩溃, 花屏, 卡顿, HardFault, 栈溢出, stack overflow,
  Guru Meditation, lv_async_call, xQueueSend, code review, 审查, 审查代码, SDK裁剪,
  裁SDK, 多余代码, 死代码, 裁剪, 新增模块, 修Bug, WSS, cJSON, DMA, I2S,
  录音, 录音失效, ASR, 识别不到, 没听清, uplink, prompt tone, 唤醒, AEC, mic peak,
  use-after-free, ESP32, STM32, JL, AC79, BK, Armino, 带屏音箱, 语音网关,
  embedded C, freertos, skill迭代, skill update,
  git commit, 提交, 提交说明, commit message.
  Reviews FreeRTOS IoT firmware with C1-C10 constraints; lazy-load constraint_index
  + 1 platform + 1-3 prompts.
---

# FreeRTOS 嵌入式架构专家（Lite 版）

> **Lite**：无 `examples/`、`tools/`。L2 → [l2_code_review_lite.md](workflows/l2_code_review_lite.md) + [lite_manual_checklist.md](references/lite_manual_checklist.md)。**结构** → [skill_structure.md](references/skill_structure.md)

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
