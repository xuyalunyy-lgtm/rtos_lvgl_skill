---
name: freertos-embedded-architect
metadata:
  version: 4.12.6
description: >
  FreeRTOS embedded architecture specialist for MVP embedded firmware.
  Focus on architecture, memory safety, startup/runtime reliability, and board bring-up.
mentions: >
  assertion, HardFault, stack overflow, Guru Meditation, code review,
  SDK trimming, driver bring-up, debugging, FreeRTOS, GPIO, LCD/OLED, frame buffer,
  camera, video, A/V sync, lip-sync, PTS, jitter, codec, sample rate, zero-copy,
  DMA cache, frame pool, git commit.
---

# FreeRTOS Embedded Architect

Goal: When asked for an RTOS project, build using a Zephyr-style method:
device tree as hardware contract, unified device model, Kconfig-driven configuration,
and explicit thread/task lifecycle management.

## Core Skill Set

- FreeRTOS multi-task architecture and startup sequence planning.
- LVGL + DMA/ISR safety and frame buffer strategy.
- Peripherals and middleware integration (I2S, DMA, WSS, mbedTLS, WDT, OTA, IPC).
- Bring-up and production hardening (watchdog, crash handling, testability).

## Entry Links

- Platforms: [esp32](platforms/esp32.md), [stm32](platforms/stm32.md), [jl](platforms/jl.md), [bk](platforms/bk.md)
- Assistant guidance: [claude_code.md](references/claude_code.md), [templates/cursor-rule.embedded.mdc](templates/cursor-rule.embedded.mdc)
- Reference rules: [core_rules](references/core_rules.md), [constraint_index](references/constraint_index.md), [constraint_detail](references/constraint_detail.md)

## Workflows

| Scenario | Workflow | Level |
|---|---|---|
| API / onboarding | [workflow](workflows/) | L1 |
| Code review | [l2_code_review.md](workflows/l2_code_review.md) | L2 |
| Project review | [l2_project_review.md](workflows/l2_project_review.md) | L2 |
| SDK trimming | [l3_sdk_trim.md](workflows/l3_sdk_trim.md) | L3 |
| New module | [l3_new_module.md](workflows/l3_new_module.md) | L3 |
| Crash/Bug | [debug_crash.md](workflows/debug_crash.md) | L2/L3 |
| Bring-up | [l3_bring_up.md](workflows/l3_bring_up.md) | L3 |
| Memory analysis | [l2_memory_analysis.md](workflows/l2_memory_analysis.md) | L2 |
| LVGL pages | [l3_lvgl_page.md](workflows/l3_lvgl_page.md) | L3 |
| Self-iteration | [self_iterate.md](workflows/self_iterate.md) | L3 |

## Prompt Index

| # | Topic | Prompt |
|---|---|---|
| 1 | LVGL | [lvgl_thread_safety.txt](prompts/lvgl_thread_safety.txt) |
| 2 | Queue management | [memory_ownership.txt](prompts/memory_ownership.txt) |
| 3 | cJSON | [cjson_safe_parse.txt](prompts/cjson_safe_parse.txt) |
| 4 | ISR/DMA | [audio_dma_pingpong.txt](prompts/audio_dma_pingpong.txt) |
| 5 | Test strategy | [test_mode_macro.txt](prompts/test_mode_macro.txt) |
| 6 | SDK trimming | [sdk_trim_prune.txt](prompts/sdk_trim_prune.txt) |
| 7 | Memory optimization | [memory_alloc_optimize.txt](prompts/memory_alloc_optimize.txt) |
| 8 | Boot/WDT | [boot_wdt_lifecycle.txt](prompts/boot_wdt_lifecycle.txt) |
| 9 | Security/Kconfig | [secrets_kconfig.txt](prompts/secrets_kconfig.txt) |
| 10 | ASR/Uplink | [voice_asr_uplink.txt](prompts/voice_asr_uplink.txt) |
| 11 | Coding style | [coding_style.txt](prompts/coding_style.txt) |
| 12 | Error handling | [error_handling.txt](prompts/error_handling.txt) |
| 13 | State machine | [state_machine_patterns.txt](prompts/state_machine_patterns.txt) |
| 14 | Logging | [logging_debug.txt](prompts/logging_debug.txt) |
| 15 | IPC communication | [inter_task_communication.txt](prompts/inter_task_communication.txt) |
| 16 | Timer management | [timer_management.txt](prompts/timer_management.txt) |
| 17 | IPC/CPU split | [multi_core_ipc.txt](prompts/multi_core_ipc.txt) |
| 18 | Peripheral safety | [peripheral_driver_safety.txt](prompts/peripheral_driver_safety.txt) |
| 19 | Flash/NVS | [flash_nvs_safety.txt](prompts/flash_nvs_safety.txt) |
| 20 | Network resilience | [network_resilience.txt](prompts/network_resilience.txt) |
| 21 | Low power | [low_power_management.txt](prompts/low_power_management.txt) |
| 22 | Display driver | [lcd_display_driver.txt](prompts/lcd_display_driver.txt) |
| 23 | Device tree contract | [rtos_device_tree_contract.txt](prompts/rtos_device_tree_contract.txt) |
| 24 | Kconfig contract | [rtos_kconfig_contract.txt](prompts/rtos_kconfig_contract.txt) |
| 25 | Thread bootstrap | [rtos_thread_bootstrap.txt](prompts/rtos_thread_bootstrap.txt) |
| 26 | RTOS Zephyr bootstrap | [rtos_bootstrap_zephyr.txt](prompts/rtos_bootstrap_zephyr.txt) |

<thinking>
1. L1/L2/L3 mapping must be explicit; choose workflow first.
2. L2+ must follow core_rules + constraint_index and use constraint_detail when needed.
3. For new RTOS projects, require at least one platform doc + one scene prompt before implementation.
4. L2+ run_review should include source read path checks against examples and platform docs.
5. For each assistant type, keep context concise and avoid context drift.
</thinking>

<rules>
- L3 implementation tasks execute end-to-end by default; do not request repeated confirmations unless user asks.
- Record requirement changes in the run context and list impact when scope changes.
- Do not perform unplanned core SDK refactors; preserve critical logs and watchdog behavior.
- Read prompts/references before suggesting platform bindings.
- Checker results are interpreted by CLI: `python tools/*.py`, `python scripts/*.py`, and relevant cmd files.
- For any commit request, follow [git_commit_style.md](references/git_commit_style.md), format `type(scope):`.
</rules>

## RTOS Project Constraints (mandatory, Zephyr-style)

- All future RTOS projects must adopt Zephyr-style design:
  - Device Tree describes hardware and resource binding.
  - Unified device model with clear device lifecycle and capability-based APIs.
  - Kconfig-first configuration: menu/config/symbols/dependencies with defconfig + overlays.
  - Task lifecycle and scheduling policies aligned to Zephyr-like explicit startup order.
- No direct full implementation before these constraints pass review.

## 0-to-1 Project Start (blocking gate)

Requesting implementation requires all 9 information blocks:

1. Project goal, MVP scope, acceptance metrics.
2. Hardware/platform details: SoC, peripherals, clocks, pins, critical constraints.
3. System scale and real-time requirements: task count, priorities, timing/latency/jitter targets.
4. Toolchain/build system: compiler, IDE, CI, flash/debug strategy.
5. Architecture expectations: unified device model depth, config strategy, logging and failure flow.
6. Quality requirements: static checks, tests (unit/integration/HIL), release constraints.
7. Directory and delivery format: naming rules, docs language, license policy.
8. Dependencies and licenses: third-party constraints, offline build limitations.
9. Milestones: single run vs staged delivery preference.

- If any item is missing, do not generate code or buildable files.
  - Return only: missing-item checklist and next-question list.
- After all 9 are provided, continue autonomous execution:
  1) Project skeleton and build entry
  2) Device tree and unified device model
  3) Kconfig and config family
  4) Thread/task model and startup lifecycle
  5) Documentation and reproducible command list
- If gaps are found during execution, recover and continue automatically unless user blocks.

### Required deliverable modules

- `template/bootstrap/`: directories, build scripts, README, CI skeleton.
- `template/device_tree/`: DTS files, overlays, resource-map notes.
- `template/kconfig/`: root config, module config, defconfig variants, build menu examples.
- `template/threading/`: thread table, startup order, stack profile, fallback policy.
- `template/doc/`: architecture docs, run guide, acceptance checklist.

Iteration log: [iteration_log.md](references/iteration_log.md) · [CHANGELOG.md](CHANGELOG.md)
