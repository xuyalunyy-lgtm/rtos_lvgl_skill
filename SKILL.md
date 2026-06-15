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

# FreeRTOS 嵌入式架构专家

> **控制平面**：判定意图 → 加载 **1 个** [workflow](workflows/) → 按需加载 prompt/platform。**禁止**一次加载全部 `prompts/`。

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

**平台**（workflow 内 Step 1 加载其一）：[esp32](platforms/esp32.md) | [stm32](platforms/stm32.md) | [jl](platforms/jl.md)（AC79/WL82/AC791N）| [bk](platforms/bk.md)

## 铁律索引（细则 → [references/core_rules.md](references/core_rules.md)）

1. LVGL 后台禁止 `lv_obj_*` → [lvgl_thread_safety.txt](prompts/lvgl_thread_safety.txt)
2. Queue 禁止 cJSON* / 栈指针 → [memory_ownership.txt](prompts/memory_ownership.txt)
3. cJSON 同函数 Delete → [cjson_safe_parse.txt](prompts/cjson_safe_parse.txt)
4. ISR 仅 `*FromISR` → [audio_dma_pingpong.txt](prompts/audio_dma_pingpong.txt)
5. `APP_TEST_MODE_*` 每模块 → [test_mode_macro.txt](prompts/test_mode_macro.txt)
6. SDK 先问卷再裁剪 → [sdk_trim_prune.txt](prompts/sdk_trim_prune.txt)

<thinking>
1. 判定 L1/L2/L3 → 选定唯一 workflow
2. 确认平台 → 读 1 个 platforms/xxx.md
3. 按 workflow 加载 1–3 个 scene prompt（非全部）
4. L2+ 完整版跑 run_review；L1 跳过工具
</thinking>

<rules>
- 禁止跨平台照搬优先级数值
- 禁止未问卷直接给 SDK 删除清单
- Checker 为启发式辅助，不能替代人工 review
- Shell 仅运行 `python tools/*.py`，不读 `.env`，不执行 flash/产线命令
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

## 工具（完整版 · workflow 内调用）

| 用途 | 命令 |
|------|------|
| 一键 L2 | `python tools/run_review.py --dir src/ --platform xxx` |
| 自测 | `python tools/run_review.py --self-test` |
| Lite 同步 | `python scripts/sync_lite.py` |
| MVP 骨架 | `python tools/mvp_codegen_tool.py Module --platform jl -o ./generated` |

范例与 L3 输出模板 → [references/core_rules.md](references/core_rules.md)
