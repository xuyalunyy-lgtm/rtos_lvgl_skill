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
Routing — match the user's first message to ONE workflow:
| Keywords | Workflow |
|----------|----------|
| review, audit, ISR, DMA, cJSON, check, 审查 | l2_code_review |
| memory, leak, 内存, 堆栈 | l2_memory_analysis |
| project, workspace, 项目审查 | l2_project_review |
| co-debug, GPIO conflict, 硬件协同 | hw_sw_cocodebug |
| LVGL, UI, page, manifest, 多页, 脚手架 | l3_lvgl_page |
| new module, 新模块, task, 任务 | l3_new_module |
| bring-up, 板级, 最小系统 | l3_bring_up |
| SDK trim, 裁剪, driver prune | l3_sdk_trim |
| crash, HardFault, WDT, deadlock, frozen, 死机 | debug_crash |
Composite requests: pick the workflow matching the user's primary deliverable first.
Load supplementary material only when that workflow explicitly requires it.
If the primary task is unclear, ask one clarifying question before proceeding.
---
## Review Domain
**Trigger:** code review / audit / memory analysis / project review / HW-SW co-debug
**Output:** risk level + verification results + actionable recommendations
| Workflow | Trigger |
|----------|---------|
| l2_code_review.md | code review / audit |
| l2_code_review_lite.md | lite manual review |
| l2_project_review.md | project/workspace review |
| l2_memory_analysis.md | memory analysis / leak |
| hw_sw_cocodebug.md | HW/SW co-debug / GPIO conflict |
- **必读:** `references/core_rules.md`, `references/constraint_index.md`
- **按需:** `platforms/{platform}.md`, workflow 指定的 `prompts/{scene}.txt`
- **工具:** `python tools/run_review.py`, `python tools/context_router.py`
- **禁止:** `mcp/`, `golden_pages/`, `native/`, `runtime/`, `ui/`, `schemas/`
---
## Generate Domain
**Trigger:** LVGL page / manifest / new module / bring-up / SDK trim
**Output:** compilable C/H artifacts + verification evidence + asset dependency list
| Workflow | Trigger |
|----------|---------|
| l3_lvgl_page.md | LVGL page / manifest generation |
| l3_new_module.md | new module / multitask MVP |
| l3_bring_up.md | board bring-up |
| l3_sdk_trim.md | SDK trimming |
- **必读:** `references/core_rules.md`
- **LVGL 必读:** `references/lvgl_image_to_code_contract.md`
- **按需:** `platforms/{platform}.md`, `references/lvgl_*`
- **工具:** MCP tools (inspect_design, generate_ui, render_ui, compare_ui, refine_ui, apply_patch)
- **禁止:** `tools/*_checker.py`, `examples/bad_*.c`
---
## Debug Domain
**Trigger:** crash / HardFault / 死机 / WDT / 崩溃日志 / frozen / deadlock
**Output:** root-cause hypothesis + minimal verify steps + next-action plan
| Workflow | Trigger |
|----------|---------|
| debug_crash.md | HardFault / WDT / crash dump |
- **必读:** `references/core_rules.md`, `references/log_symptom_routes.json`
- **按需:** `platforms/{platform}.md`, 症状匹配的 `prompts/{scene}.txt`
- **工具:** `python tools/log_triage.py`, `python tools/context_router.py`
- **禁止:** `mcp/`, `golden_pages/`, `native/`, `runtime/`
---
## Shared Rules (All Domains)
- Ask for platform when missing; ESP32/STM32/JL/BK are platforms, FreeRTOS/Zephyr are RTOS.
- Select a workflow before acting; load ONLY files in your domain's Loading Rules.
- Commit requests: follow `references/git_commit_style.md`, use `type(scope):`.
- LVGL UI generation must use the MCP toolchain; see `references/lvgl_validation_contract.md`.
## Constraint Shards Index
Load only the shard(s) referenced by your selected workflow:
| Shard | Constraints |
|-------|-------------|
| constraint_review.md | C1-C6, C11-C16 |
| constraint_memory.md | C7, C28, C36 |
| constraint_rtos.md | C8, C15, C17, C29-C35, C43-C44 |
| constraint_platform.md | C18-C21, C23, C42, C45-C46 |
| constraint_media.md | C25-C27 |
| constraint_voice.md | C10 |
| constraint_ota.md | C9, C22, C24 |
| constraint_recover.md | C37-C41 |
| constraint_bluetooth_protocol.md | C46 |
