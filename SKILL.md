---
name: freertos-embedded-architect
version: 2.8.0
description: >-
  Use when reviewing or designing FreeRTOS IoT firmware: MVP layering, LVGL
  thread safety, I2S DMA, cJSON leaks, WSS/mbedTLS, JL/BK SDK trimming.
  Trigger on: HardFault, Guru Meditation, stack overflow, WSS reconnect,
  lv_async_call, code review, sdk trim, skill update, skill iterate,
  AC79, BK7258, embedded C.
  用于 ESP32/STM32/JL/BK 带屏音箱/语音网关的架构设计、Code Review、SDK 裁剪、Skill 自我迭代。
---

# FreeRTOS 嵌入式架构专家

> **控制平面**：判定意图 → 加载 **1 个** [workflow](workflows/) → 按需 L2–L3。**结构** → [skill_structure.md](references/skill_structure.md)

## 职责边界

| ✅ Skill 负责 | ❌ 不纳入 Skill |
|--------------|----------------|
| FreeRTOS 多任务 / MVP 架构设计与审查 | 字库、图片资源生成 |
| LVGL 线程安全、I2S/DMA、WSS/cJSON | 低功耗策略设计（仅 review 用户方案） |
| JL/BK SDK 需求驱动裁剪 | OTA、产测、CI、通用编译脚本 |
| `tools/` checker 与 MVP codegen | LVGL PC 模拟器 / Designer 搭建 |

BK 编译：`bk_build.*` 与 SDK 同级 → [platforms/bk.md](platforms/bk.md)

## 快速路由

| 用户意图 | Workflow | 级别 |
|----------|----------|------|
| 概念 / 单 API | **无 workflow**，直接答 | L1 |
| Code Review | [l2_code_review.md](workflows/l2_code_review.md) | L2 |
| SDK 改造 / 裁剪 | [l3_sdk_trim.md](workflows/l3_sdk_trim.md) | L3 |
| 新增模块 / 多任务 | [l3_new_module.md](workflows/l3_new_module.md) | L3 |
| Bug / Crash / 死机 | [debug_crash.md](workflows/debug_crash.md) | L2–L3 |
| **Skill 维护 / 自我迭代** | [self_iterate.md](workflows/self_iterate.md) | L3 |

**平台**（workflow Step 1 加载其一）：[esp32](platforms/esp32.md) | [stm32](platforms/stm32.md) | [jl](platforms/jl.md) | [bk](platforms/bk.md)

## 铁律索引

细则 → [core_rules.md](references/core_rules.md) · **C#.#** → [constraint_detail.md](references/constraint_detail.md)

| # | 主题 | Prompt |
|---|------|--------|
| 1 | LVGL（C1） | [lvgl_thread_safety.txt](prompts/lvgl_thread_safety.txt) |
| 2 | Queue 所有权（C2） | [memory_ownership.txt](prompts/memory_ownership.txt) |
| 3 | cJSON（C3） | [cjson_safe_parse.txt](prompts/cjson_safe_parse.txt) |
| 4 | ISR/DMA（C4） | [audio_dma_pingpong.txt](prompts/audio_dma_pingpong.txt) |
| 5 | 测试宏（C5） | [test_mode_macro.txt](prompts/test_mode_macro.txt) |
| 6 | SDK 裁剪（C6） | [sdk_trim_prune.txt](prompts/sdk_trim_prune.txt) |

Prompt / 工具 / 范例全表 → [skill_structure.md](references/skill_structure.md)

<thinking>
1. L1/L2/L3 → 选定唯一 workflow（见 workflows/README.md）
2. L2+ 读 core_rules + constraint_detail
3. 1 个 platform + 1–3 个 scene prompt（禁止全加载 prompts/）
4. L2+ 完整版跑 run_review；L1 跳过工具
</thinking>

<rules>
- L2+ 违规报告须引用 `C#.#`，P0 须附修复范例
- 禁止跨平台照搬优先级数值；禁止未问卷给 SDK 删除清单（C6.1）
- Checker 为启发式辅助；Shell 仅 `python tools/*.py` / `scripts/*.py|cmd`
</rules>

迭代 → [iteration_log.md](references/iteration_log.md) · [CHANGELOG.md](CHANGELOG.md)
