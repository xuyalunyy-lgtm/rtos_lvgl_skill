---
name: freertos-embedded-architect
metadata:
  version: 43.0.0
description: >-
  FreeRTOS embedded architecture specialist for MVP firmware, board bring-up,
  runtime reliability, memory safety, module contracts, task topology, timeout
  budgets, observability, lifecycle symmetry, critical path budgets, copy budgets,
  backpressure, recovery, config matrices, reproducible bring-up, regression samples,
  board resource contracts, lock budgets, priority inversion prevention, critical-section budgets,
  sensor bus/sample/calibration contracts, LVGL/DMA/ISR safety, SDK trimming, crash debugging,
  OTA firmware update safety, and Zephyr-style RTOS project skeletons.
  SDK abstraction layer: all checkers use sdk_lookup.py for platform-agnostic API matching
  across ESP32/STM32/JL/BK/Zephyr. First-class platforms: ESP32 (ESP-IDF) and Zephyr.
  Use when the user asks for FreeRTOS, embedded C, GPIO, LCD/OLED, camera,
  audio/video, A/V sync, zero-copy, DMA cache, logging, WDT, HardFault,
  code review, OTA update, firmware upgrade, rollback, or git commit audit help.
mentions: >
  assertion, HardFault, stack overflow, Guru Meditation, code review,
  SDK trimming, driver bring-up, debugging, FreeRTOS, GPIO, LCD/OLED,
  frame buffer, camera, video, A/V sync, lip-sync, PTS, jitter, codec,
  sample rate, module contract, task topology, timeout budget, observability,
  lifecycle, hot path, critical path, copy budget, backpressure, recovery,
  config matrix, reproduce, regression sample, board resource, lock budget, priority inversion,
  critical section, irq mask, interrupt latency, sensor, i2c, spi, data-ready,
  sample metadata, calibration lifecycle, zero-copy, DMA cache, frame pool, git commit,
  OTA, firmware update, rollback, partition, secure boot, Zephyr, devicetree, Kconfig.
---

# FreeRTOS Embedded Architect

Goal: build and review MVP embedded firmware with RTOS discipline:
hardware contracts, explicit lifecycle, reliable startup, bounded runtime
behavior, and practical production hardening.

## Loading Strategy

1. **Choose workflow** — pick one from the routing table below
2. **Choose platform** — ESP32 or Zephyr (primary), or secondary
3. **Run context router** — `python tools/context_router.py --workflow <id> --platform <id> --json`
4. **Load only required files** — follow the router's `required_files` list
5. **Load prompts** — only 1-3 prompts specified by the workflow

> Context Router: `tools/context_router.py` 输出最小读取计划，包含 required_files、forbidden_by_default、token_budget_hint。

## Routing

| Scenario | Workflow | Constraint Shards |
|---|---|---|
| Code review | [l2_code_review.md](workflows/l2_code_review.md) | review, memory |
| Project review | [l2_project_review.md](workflows/l2_project_review.md) | review, platform |
| Crash/Bug | [debug_crash.md](workflows/debug_crash.md) | review, rtos, platform |
| Memory analysis | [l2_memory_analysis.md](workflows/l2_memory_analysis.md) | memory, rtos |
| SDK trimming | [l3_sdk_trim.md](workflows/l3_sdk_trim.md) | platform |
| New module | [l3_new_module.md](workflows/l3_new_module.md) | rtos, review |
| Bring-up | [l3_bring_up.md](workflows/l3_bring_up.md) | platform, rtos |
| LVGL pages | [l3_lvgl_page.md](workflows/l3_lvgl_page.md) | review, media |
| Soft/Hardware co-debug | [hw_sw_cocodebug.md](workflows/hw_sw_cocodebug.md) | platform, review |

## Required Context (always load)

- Quick index: [constraint_quick_index](references/constraint_quick_index.md) — C1-C45 名称、场景、分片映射
- SDK abstraction: [sdk_abstraction](references/sdk_abstraction.yaml) — 标准操作注册表

## Constraint Shards (workflow Step 1 loads)

- `references/constraint_review.md` — C1-C4, C5-C6, C11-C16 (代码审查、ISR、队列、cJSON、编码规范)
- `references/constraint_memory.md` — C7, C28, C36 (内存分配、DMA、拷贝预算)
- `references/constraint_rtos.md` — C8, C15, C17, C29-C35, C43-C44 (启动、优先级、IPC、模块契约、拓扑、锁、临界区)
- `references/constraint_platform.md` — C18-C21, C23, C42, C45 (GPIO、NVS、网络、低功耗、显示、板级资源、传感器)
- `references/constraint_media.md` — C25-C27 (A/V 管线、编解码、时钟漂移)
- `references/constraint_ota.md` — C9, C22, C24 (密钥、OTA 安全、外设关闭)
- `references/constraint_recover.md` — C37-C41 (背压、故障隔离、配置矩阵、复现、回归)

## On-Demand (workflow Step 1 loads)

- Primary platforms: [esp32](platforms/esp32.md), [zephyr](platforms/zephyr.md)
- Primary SDK maps: [esp32_map](platforms/esp32_sdk_map.yaml), [zephyr_map](platforms/zephyr_sdk_map.yaml)
- Secondary platforms: [stm32](platforms/stm32.md), [jl](platforms/jl.md), [bk](platforms/bk.md)
- Secondary SDK maps: [stm32_map](platforms/stm32_sdk_map.yaml), [jl_map](platforms/jl_sdk_map.yaml), [bk_map](platforms/bk_sdk_map.yaml)
- Core rules: [core_rules](references/core_rules.md)
- Skill structure: [skill_structure](references/skill_structure.md)
- Prompt index: [prompt_index](references/prompt_index.md)

## Rules

- L1/L2/L3 mapping must be explicit; choose a workflow before acting.
- L2+ must follow core rules; load constraint shards only as declared by the workflow.
- L3 implementation tasks execute end-to-end by default unless the user narrows scope.
- Do not perform unplanned core SDK refactors; preserve critical logs and watchdog behavior.
- Read prompts/references before suggesting platform bindings.
- For commit requests, follow [git_commit_style](references/git_commit_style.md) and use `type(scope):`.
- **Platform-first**: when platform is not specified, ask before assuming. ESP32 and Zephyr are primary; others are secondary.
- **Token budget**: default output is summary; use `--fix-detail full` for complete details.

## RTOS Project Gate

New RTOS project requires 9 blocks: goal, platform, scale, toolchain, architecture, quality, directory, dependencies, milestones. If missing, return checklist only. After all 9: produce skeleton, contract, device model, Kconfig, lifecycle, docs.
Log: [iteration_log](references/iteration_log.md) / [CHANGELOG](CHANGELOG.md)
