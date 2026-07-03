---
name: freertos-embedded-architect
metadata:
  version: 30.0.0
description: >-
  FreeRTOS embedded architecture specialist for MVP firmware, board bring-up,
  runtime reliability, memory safety, module contracts, task topology, timeout
  budgets, observability, lifecycle symmetry, critical path budgets, copy budgets,
  backpressure, recovery, config matrices, reproducible bring-up, regression samples,
  board resource contracts, lock budgets, priority inversion prevention, critical-section budgets,
  sensor bus/sample/calibration contracts, LVGL/DMA/ISR safety, SDK trimming, crash debugging,
  release governance, OTA firmware update safety, and Zephyr-style RTOS project skeletons.
  SDK abstraction layer: all checkers use sdk_lookup.py for platform-agnostic API matching
  across ESP32/STM32/JL/BK/Zephyr. Use when the user
  asks for FreeRTOS, embedded C, GPIO, LCD/OLED, camera, audio/video, A/V sync,
  zero-copy, DMA cache, logging, WDT, HardFault, code review, OTA update,
  firmware upgrade, rollback, or git commit audit help.
mentions: >
  assertion, HardFault, stack overflow, Guru Meditation, code review,
  SDK trimming, driver bring-up, debugging, FreeRTOS, GPIO, LCD/OLED,
  frame buffer, camera, video, A/V sync, lip-sync, PTS, jitter, codec,
  sample rate, module contract, task topology, timeout budget, observability,
  lifecycle, hot path, critical path, copy budget, backpressure, recovery,
  config matrix, reproduce, regression sample, board resource, lock budget, priority inversion,
  critical section, irq mask, interrupt latency, sensor, i2c, spi, data-ready,
  sample metadata, calibration lifecycle, zero-copy, DMA cache, frame pool, git commit, release audit,
  OTA, firmware update, rollback, partition, secure boot.
---

# FreeRTOS Embedded Architect

Goal: build and review MVP embedded firmware with RTOS discipline:
hardware contracts, explicit lifecycle, reliable startup, bounded runtime
behavior, and practical production hardening.

## Routing

Choose one workflow first, then load only required references, platform docs, and scene prompts.

### User Workflows (default context)

| Scenario | Workflow |
|---|---|
| Code review | [l2_code_review.md](workflows/l2_code_review.md) |
| Project review | [l2_project_review.md](workflows/l2_project_review.md) |
| Crash/Bug | [debug_crash.md](workflows/debug_crash.md) |
| Memory analysis | [l2_memory_analysis.md](workflows/l2_memory_analysis.md) |
| SDK trimming | [l3_sdk_trim.md](workflows/l3_sdk_trim.md) |
| New module | [l3_new_module.md](workflows/l3_new_module.md) |
| Bring-up | [l3_bring_up.md](workflows/l3_bring_up.md) |
| LVGL pages | [l3_lvgl_page.md](workflows/l3_lvgl_page.md) |
| Software architecture review | [l2_architecture_review.md](workflows/l2_architecture_review.md) |
| RTOS system review | [l2_rtos_system_review.md](workflows/l2_rtos_system_review.md) |
| Soft/Hardware co-debug | [hw_sw_cocodebug.md](workflows/hw_sw_cocodebug.md) |

### Maintainer / Optional (not loaded by default)

| Scenario | Workflow |
|---|---|
| Self-iteration | [self_iterate.md](workflows/self_iterate.md) |
| Learning candidate | [l2_learning_candidate.md](workflows/l2_learning_candidate.md) |
| Session strict mode | [session_strict_mode.txt](prompts/session_strict_mode.txt) |
| Release governance | [release_governance](references/release_governance.md) |
| Auto repair | [l2_auto_repair.md](workflows/l2_auto_repair.md) |

## Required Context

- Core rules: [core_rules](references/core_rules.md), [constraint_index](references/constraint_index.md), [constraint_detail](references/constraint_detail.md), [skill_structure](references/skill_structure.md)
- SDK abstraction: [sdk_abstraction](references/sdk_abstraction.yaml) — 标准操作注册表，checker 通过 `sdk_lookup.py` 查询平台 API
- Release governance (maintainer): [release_governance](references/release_governance.md), [claude_code](references/claude_code.md), [cursor rule](templates/cursor-rule.embedded.mdc)

## On-Demand (workflow Step 1 loads)

- Platforms: [esp32](platforms/esp32.md), [stm32](platforms/stm32.md), [jl](platforms/jl.md), [bk](platforms/bk.md), [zephyr](platforms/zephyr.md)
- Platform SDK maps: [esp32_map](platforms/esp32_sdk_map.yaml), [stm32_map](platforms/stm32_sdk_map.yaml), [jl_map](platforms/jl_sdk_map.yaml), [bk_map](platforms/bk_sdk_map.yaml), [zephyr_map](platforms/zephyr_sdk_map.yaml)
- Usage examples: [usage_examples](references/usage_examples.md)
- Codegen contract: [codegen_contract](references/codegen_contract.md)

## Prompt Index

Load only prompts needed by the selected workflow: [prompt_index](references/prompt_index.md)

## Rules

- L1/L2/L3 mapping must be explicit; choose a workflow before acting.
- L2+ must follow core rules plus constraint index; load constraint detail only when needed.
- L3 implementation tasks execute end-to-end by default unless the user narrows scope.
- Do not perform unplanned core SDK refactors; preserve critical logs and watchdog behavior.
- Read prompts/references before suggesting platform bindings.
- For commit requests, follow [git_commit_style](references/git_commit_style.md) and use `type(scope):`.
- **Session strict mode** (maintainer): when activated, every RTOS/firmware task must: (1) choose workflow, (2) declare platform/framework, (3) cite constraints, (4) provide verification plan. See [session_strict_mode.txt](prompts/session_strict_mode.txt). Guard: `python tools/session_guard.py --self-test`.

## RTOS Project Gate

New RTOS project requires 9 blocks: goal, platform, scale, toolchain, architecture, quality, directory, dependencies, milestones. If missing, return checklist only. After all 9: produce skeleton, contract, device model, Kconfig, lifecycle, docs.
Log: [iteration_log](references/iteration_log.md) / [CHANGELOG](CHANGELOG.md)
