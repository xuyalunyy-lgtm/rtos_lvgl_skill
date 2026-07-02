---
name: freertos-embedded-architect
metadata:
  version: 15.0.8
description: >-
  FreeRTOS embedded architecture specialist for MVP firmware, board bring-up,
  runtime reliability, memory safety, module contracts, task topology, timeout
  budgets, observability, lifecycle symmetry, critical path budgets, copy budgets,
  backpressure, recovery, config matrices, reproducible bring-up, regression samples,
  board resource contracts, lock budgets, priority inversion prevention, critical-section budgets,
  sensor bus/sample/calibration contracts, LVGL/DMA/ISR safety, SDK trimming, crash debugging,
  release governance, OTA firmware update safety, and Zephyr-style RTOS project skeletons. Use when the user
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

| Scenario | Workflow |
|---|---|
| Software architecture review | [l2_architecture_review.md](workflows/l2_architecture_review.md) |
| Code review | [l2_code_review.md](workflows/l2_code_review.md) |
| Project review | [l2_project_review.md](workflows/l2_project_review.md) |
| Crash/Bug | [debug_crash.md](workflows/debug_crash.md) |
| Memory analysis | [l2_memory_analysis.md](workflows/l2_memory_analysis.md) |
| SDK trimming | [l3_sdk_trim.md](workflows/l3_sdk_trim.md) |
| New module | [l3_new_module.md](workflows/l3_new_module.md) |
| Bring-up | [l3_bring_up.md](workflows/l3_bring_up.md) |
| LVGL pages | [l3_lvgl_page.md](workflows/l3_lvgl_page.md) |
| Self-iteration | [self_iterate.md](workflows/self_iterate.md) |

## Required Context

- Platforms: [esp32](platforms/esp32.md), [stm32](platforms/stm32.md), [jl](platforms/jl.md), [bk](platforms/bk.md), [zephyr](platforms/zephyr.md)
- Core rules: [core_rules](references/core_rules.md), [constraint_index](references/constraint_index.md), [constraint_detail](references/constraint_detail.md), [skill_structure](references/skill_structure.md)
- Release governance: [release_governance](references/release_governance.md), [claude_code](references/claude_code.md), [cursor rule](templates/cursor-rule.embedded.mdc)

## Prompt Index

Load only prompts needed by the selected workflow or suspected constraint:

- 软件架构评审: [software_architecture_design](prompts/software_architecture_design.txt)
- LVGL/threading: [lvgl_thread_safety](prompts/lvgl_thread_safety.txt)
- Ownership/IPC: [memory_ownership](prompts/memory_ownership.txt), [inter_task_communication](prompts/inter_task_communication.txt)
- JSON/error/style/logging: [cjson_safe_parse](prompts/cjson_safe_parse.txt), [error_handling](prompts/error_handling.txt), [coding_style](prompts/coding_style.txt), [logging_debug](prompts/logging_debug.txt)
- ISR/DMA/audio/video: [audio_dma_pingpong](prompts/audio_dma_pingpong.txt), [lcd_display_driver](prompts/lcd_display_driver.txt), [voice_asr_uplink](prompts/voice_asr_uplink.txt)
- Audio/WSS field triage: [voice_asr_uplink](prompts/voice_asr_uplink.txt), [mbedtls_wss_memory](prompts/mbedtls_wss_memory.txt), [peripheral_shutdown_safety](prompts/peripheral_shutdown_safety.txt)
- Boot/config/security: [boot_wdt_lifecycle](prompts/boot_wdt_lifecycle.txt), [secrets_kconfig](prompts/secrets_kconfig.txt), [flash_nvs_safety](prompts/flash_nvs_safety.txt), [ota_update_safety](prompts/ota_update_safety.txt)
- Runtime patterns: [state_machine_patterns](prompts/state_machine_patterns.txt), [timer_management](prompts/timer_management.txt), [multi_core_ipc](prompts/multi_core_ipc.txt)
- Robustness: [memory_alloc_optimize](prompts/memory_alloc_optimize.txt), [network_resilience](prompts/network_resilience.txt), [low_power_management](prompts/low_power_management.txt), [peripheral_driver_safety](prompts/peripheral_driver_safety.txt)
- Efficiency contracts: [runtime_efficiency_contracts](prompts/runtime_efficiency_contracts.txt)
- Zephyr-style RTOS: [device_tree_contract](prompts/rtos_device_tree_contract.txt), [kconfig_contract](prompts/rtos_kconfig_contract.txt), [thread_bootstrap](prompts/rtos_thread_bootstrap.txt), [rtos_bootstrap_zephyr](prompts/rtos_bootstrap_zephyr.txt)

## Rules

- L1/L2/L3 mapping must be explicit; choose a workflow before acting.
- L2+ must follow core rules plus constraint index; load constraint detail only when needed.
- L3 implementation tasks execute end-to-end by default unless the user narrows scope.
- Do not perform unplanned core SDK refactors; preserve critical logs and watchdog behavior.
- Read prompts/references before suggesting platform bindings.
- For commit requests, follow [git_commit_style](references/git_commit_style.md), run release audit, and use `type(scope):`.

## RTOS Project Gate

For new RTOS project implementation, require all nine blocks before creating
buildable code:

1. Project goal, MVP scope, acceptance metrics.
2. Hardware/platform details.
3. System scale and real-time requirements.
4. Toolchain/build/debug strategy.
5. Architecture expectations.
6. Quality requirements.
7. Directory and delivery format.
8. Dependencies and licenses.
9. Milestones and delivery mode.

If any item is missing, return only a missing-item checklist and next questions.
After all nine are provided, produce skeleton, resource contract, device model, Kconfig family, thread lifecycle, docs, and reproducible commands.
Iteration log: [iteration_log](references/iteration_log.md) / [CHANGELOG](CHANGELOG.md)
