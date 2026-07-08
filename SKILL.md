---
name: freertos-embedded-architect
metadata:
  version: 44.0.0
description: >-
  Embedded architecture specialist for MVP firmware and production hardening.
  Covers runtime reliability, memory safety, module contracts, task topology,
  timeout budgets, observability, lifecycle symmetry, recovery, board bring-up,
  LVGL/DMA/ISR safety, LVGL UI generation from design/cut images, SDK trimming, crash debugging, and OTA firmware update safety.
  SDK abstraction layer: checkers use sdk_lookup.py across ESP32/STM32/JL/BK/Zephyr.
  First-class platforms: ESP32 (ESP-IDF), STM32, JL, BK. First-class RTOS: FreeRTOS, Zephyr.
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

Build and review MVP embedded firmware with RTOS discipline: hardware
contracts, explicit lifecycle, reliable startup, bounded runtime behavior,
and practical production hardening.

## Loading Strategy

1. Choose exactly one workflow from the routing table.
2. Choose platform and RTOS before loading platform-specific references.
3. Run `python tools/context_router.py --workflow <router_id> --platform <id> --rtos <id> --json`.
4. Load only the router's `required_files`; treat `forbidden_by_default` as off-limits unless the user asks.
5. Load only the 1-3 prompts selected by the workflow or by a specific symptom.

Router IDs: `code_review`, `project_review`, `crash_debug`,
`memory_analysis`, `sdk_trim`, `new_module`, `bring_up`, `lvgl_page`,
`hw_sw_debug`.

## Routing

| Scenario | Workflow | Constraint shards |
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

## Required Context

- Quick index: [constraint_quick_index](references/constraint_quick_index.md) lists C1-C46 names, scenarios, and shard mapping.
- SDK abstraction: [sdk_abstraction](references/sdk_abstraction.yaml) defines normalized API categories for platform-agnostic checkers.
- Core rules: [core_rules](references/core_rules.md) is mandatory for L2+ review or implementation work.

## Constraint Shards

- `references/constraint_review.md`: C1-C4, C5-C6, C11-C16.
- `references/constraint_memory.md`: C7, C28, C36.
- `references/constraint_rtos.md`: C8, C15, C17, C29-C35, C43-C44.
- `references/constraint_platform.md`: C18-C21, C23, C42, C45-C46.
- `references/constraint_media.md`: C25-C27.
- `references/constraint_ota.md`: C9, C22, C24.
- `references/constraint_recover.md`: C37-C41.

## On-Demand Context

- Platform docs: [esp32](platforms/esp32.md), [stm32](platforms/stm32.md), [jl](platforms/jl.md), [bk](platforms/bk.md).
- RTOS docs: [freertos](platforms/freertos.md), [zephyr](platforms/zephyr.md).
- SDK maps: `platforms/*_sdk_map.yaml`, including FreeRTOS and Zephyr RTOS maps.
- Prompt index: [prompt_index](references/prompt_index.md); load prompts only after workflow and symptom selection. MCP adapter: [server](mcp/server.py) plus [lvgl_ui](mcp/lvgl_ui.py) expose resources/tools; scripts remain authoritative.

## Resource Layers

| Layer | Contents | Runtime policy |
|---|---|---|
| Runtime | `SKILL.md`, `agents/`, `workflows/`, routed `references/`, `prompts/`, `platforms/`, active `tools/`, `mcp/` | Keep installed and load by router only. |
| Test | `tools/fixtures/`, `examples/`, `scene_presets/`, selected `scripts/check_*` | Keep in source and full runtime when required by gates; do not load by default. |
| Maintenance | root `README.md`, `INSTALL.md`, `CHANGELOG.md`, `archive/`, `forward_tests/`, local caches | Keep out of installed runtime payload unless explicitly maintaining the skill. |

## Rules

- Keep L1/L2/L3 mapping explicit; select a workflow before acting.
- Ask for platform when missing; ESP32/STM32/JL/BK are platforms, FreeRTOS/Zephyr are RTOS choices.
- Read routed prompts/references before suggesting platform bindings or protocol adaptation.
- Do not perform unplanned core SDK refactors; preserve critical logs and watchdog behavior.
- For commit requests, follow [git_commit_style](references/git_commit_style.md) and use `type(scope):`.
- For self-iteration, run `python scripts/skill_iterate.py --check` before release or commit review.
- For LVGL design/cut-image UI work, read MCP `lvgl://display-config` then `lvgl://theme-skill`; use `convert_image_to_lvgl_source`, `generate_lvgl_layout_spec`, `generate_lvgl_page_code`, and `validate_lvgl_layout_code`. Prefer Flex/Grid; absolute coordinates require `LVGL_LAYOUT_EXCEPTION`.
- Default output should be concise; use `--fix-detail full` only when complete details are needed.
