---
name: freertos-embedded-architect
metadata:
  version: 45.0.0
description: >-
  FreeRTOS/IoT firmware architect: MVP code review, LVGL UI generation,
  crash debugging, OTA safety, SDK trimming, module contracts, task topology,
  DMA/ISR safety, A/V sync, clock jitter, zero-copy buffers, cJSON leak prevention,
  WSS/mbedTLS, sensor integration, lock budget, priority inversion, critical sections.
  Multi-platform (ESP32/STM32/JL/BK/Zephyr). Use when working on embedded C, RTOS tasks,
  board bring-up, memory analysis, peripheral drivers, or firmware review.
---
# FreeRTOS Embedded Architect

Build and review MVP embedded firmware with RTOS discipline: hardware
contracts, explicit lifecycle, reliable startup, bounded runtime behavior,
and practical production hardening.

## Loading Strategy

1. Choose exactly one workflow from the routing table.
2. Choose platform and RTOS before loading platform-specific references.
3. Run `python tools/context_router.py --workflow <id> --platform <id> --rtos <id> --json`.
4. Load only the router's `required_files`; treat `forbidden_by_default` as off-limits.
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
| LVGL pages | [l3_lvgl_page.md](workflows/l3_lvgl_page.md) | review, media, voice |
| Soft/Hardware co-debug | [hw_sw_cocodebug.md](workflows/hw_sw_cocodebug.md) | platform, review |

## Constraint Shards

- `references/constraint_review.md`: C1-C4, C5-C6, C11-C16.
- `references/constraint_memory.md`: C7, C28, C36.
- `references/constraint_rtos.md`: C8, C15, C17, C29-C35, C43-C44.
- `references/constraint_platform.md`: C18-C21, C23, C42, C45-C46.
- `references/constraint_media.md`: C25-C27.
- `references/constraint_voice.md`: C10.
- `references/constraint_ota.md`: C9, C22, C24.
- `references/constraint_recover.md`: C37-C41.
- `references/constraint_bluetooth_protocol.md`: C46.

## On-Demand Context

- Platform docs: `platforms/esp32.md`, `platforms/stm32.md`, `platforms/jl.md`, `platforms/bk.md`.
- RTOS docs: `platforms/freertos.md`, `platforms/zephyr.md`.
- SDK maps: `platforms/*_sdk_map.yaml`.
- Prompt index: [prompt_index](references/prompt_index.md).

## Entry Points

- **CLI / CI**: `python tools/run_review.py` and `tools/*.py`.
- **IDE / Claude Code**: MCP tools via `.mcp.json`.
- **LVGL**: MCP-first; see [lvgl_image_to_code_contract](references/lvgl_image_to_code_contract.md).

## Rules

- Keep L1/L2/L3 mapping explicit; select a workflow before acting.
- Ask for platform when missing; ESP32/STM32/JL/BK are platforms, FreeRTOS/Zephyr are RTOS choices.
- Read routed prompts/references before suggesting platform bindings.
- Do not perform unplanned core SDK refactors; preserve critical logs and watchdog behavior.
- For commit requests, follow [git_commit_style](references/git_commit_style.md) and use `type(scope):`.
- LVGL UI generation must use the MCP toolchain; see [validation_contract](references/lvgl_validation_contract.md).
- Default output should be concise; use `--fix-detail full` only when complete details are needed.
