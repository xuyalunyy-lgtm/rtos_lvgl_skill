---
name: freertos-embedded-architect
version: 2.14.0
description: >-
  审查与设计 FreeRTOS 物联网固件：MVP 分层、LVGL 线程安全、I2S/DMA、cJSON 泄漏、
  WSS/mbedTLS、内存优化、启动/WDT、JL/BK SDK 裁剪。
  Use when user mentions: 死机, 崩溃, 花屏, 卡顿, HardFault, 栈溢出, stack overflow,
  Guru Meditation, lv_async_call, xQueueSend, code review, 审查, 审查代码, SDK裁剪,
  裁SDK, 新增模块, 修Bug, WSS, cJSON, DMA, I2S, AC79, BK7258, 杰理, 博流, Armino,
  ESP32, STM32, 带屏音箱, 语音网关, embedded C, freertos, skill迭代, skill update.
  Reviews FreeRTOS IoT firmware with C1-C8 constraints; lazy-load constraint_index
  + 1 platform + 1-3 prompts.
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

**Claude Code：** [references/claude_code.md](references/claude_code.md) · 安装 `scripts/install_claude_code.*` · 项目 [templates/CLAUDE.embedded.md](templates/CLAUDE.embedded.md)

**Cursor 命中率：** 固件仓安装 [templates/cursor-rule.embedded.mdc](templates/cursor-rule.embedded.mdc) → `.cursor/rules/`（见 [INSTALL.md](INSTALL.md)）

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

细则 → [core_rules.md](references/core_rules.md) · **C#.#** 速查 → [constraint_index.md](references/constraint_index.md) · 完整 → [constraint_detail.md](references/constraint_detail.md)

| # | 主题 | Prompt |
|---|------|--------|
| 1 | LVGL（C1） | [lvgl_thread_safety.txt](prompts/lvgl_thread_safety.txt) |
| 2 | Queue 所有权（C2） | [memory_ownership.txt](prompts/memory_ownership.txt) |
| 3 | cJSON（C3） | [cjson_safe_parse.txt](prompts/cjson_safe_parse.txt) |
| 4 | ISR/DMA（C4） | [audio_dma_pingpong.txt](prompts/audio_dma_pingpong.txt) |
| 5 | 测试宏（C5） | [test_mode_macro.txt](prompts/test_mode_macro.txt) |
| 6 | SDK 裁剪（C6） | [sdk_trim_prune.txt](prompts/sdk_trim_prune.txt) |
| 7 | 内存优化（C7） | [memory_alloc_optimize.txt](prompts/memory_alloc_optimize.txt) |
| 8 | 启动/WDT（C8） | [boot_wdt_lifecycle.txt](prompts/boot_wdt_lifecycle.txt) |

Prompt / 工具 / 范例全表 → [skill_structure.md](references/skill_structure.md)

<thinking>
1. L1/L2/L3 → 选定唯一 workflow（见 workflows/README.md）
2. L2+ 读 core_rules + **constraint_index.md**（非 constraint_detail 全文，除非要正例列）
3. 1 个 platform + 1–3 个 scene prompt（**禁止** Glob/Read 整个 prompts/）
4. L2+ 完整版跑 run_review；用 Grep/Read 单文件读 examples
5. Claude Code：见 claude_code.md；项目 CLAUDE.md 保持 <500 token
</thinking>

<rules>
- **L3 实现类任务：全权改代码、无需逐步确认，直至功能完成且编译通过**（见 core_rules 自主实施模式）
- L2+ 违规报告须引用 `C#.#`，P0 须附修复范例
- 禁止跨平台照搬优先级数值；禁止未问卷给 SDK 删除清单（C6.1）
- Checker 为启发式辅助；Shell 仅 `python tools/*.py` / `scripts/*.py|cmd`
</rules>

迭代 → [iteration_log.md](references/iteration_log.md) · [CHANGELOG.md](CHANGELOG.md)
