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

## Domain Detection

Read the user's first message and classify into ONE domain:

| Domain | Keywords / Signals | Load Section |
|--------|-------------------|--------------|
| **review** | 审查, review, audit, check, 代码质量, code quality, ISR, DMA, cJSON, 优先级, priority | → Review Domain |
| **generate** | LVGL, UI, 页面, page, 设计截图, design, 新模块, new module, bring-up, SDK裁剪, sdk_trim | → Generate Domain |
| **debug** | crash, HardFault, 死机, 看门狗, WDT, 崩溃, backtrace, Guru Meditation, frozen, deadlock | → Debug Domain |
| **app** | manifest, 多页, multi-page, Router, Presenter, Model, 脚手架, scaffold | → App Domain |

If ambiguous, ask the user to clarify. Never load multiple domains simultaneously.

---

## Review Domain

**Trigger:** code review / audit / 审查 / 嵌入式 C 代码质量检查 / 内存分析 / 硬件协同调试

### Workflows
| Workflow | Trigger |
|----------|---------|
| [l2_code_review.md](workflows/l2_code_review.md) | code review / audit |
| [l2_code_review_lite.md](workflows/l2_code_review_lite.md) | lite manual review |
| [l2_project_review.md](workflows/l2_project_review.md) | project/workspace review |
| [l2_memory_analysis.md](workflows/l2_memory_analysis.md) | memory analysis / leak |
| [hw_sw_cocodebug.md](workflows/hw_sw_cocodebug.md) | HW/SW co-debug / GPIO conflict |

### Loading Rules
- **必读:** `references/core_rules.md`, `references/constraint_index.md`
- **按需:** 1 个 `platforms/{platform}.md` + 1-3 个 `prompts/{scene}.txt`（由 workflow 指定）
- **工具:** `python tools/run_review.py`, `python tools/context_router.py`
- **禁止加载:** `mcp/`, `golden_pages/`, `native/`, `runtime/`, `ui/`, `schemas/`

---

## Generate Domain

**Trigger:** LVGL page / UI generation / 新模块 / bring-up / SDK trimming

### Workflows
| Workflow | Trigger |
|----------|---------|
| [l3_lvgl_page.md](workflows/l3_lvgl_page.md) | LVGL page generation |
| [l3_new_module.md](workflows/l3_new_module.md) | new module / multitask MVP |
| [l3_bring_up.md](workflows/l3_bring_up.md) | board bring-up |
| [l3_sdk_trim.md](workflows/l3_sdk_trim.md) | SDK trimming |

### Loading Rules
- **必读:** `references/core_rules.md`, [lvgl_image_to_code_contract](references/lvgl_image_to_code_contract.md)（仅 LVGL 时）
- **按需:** 1 个 `platforms/{platform}.md`, `references/lvgl_*`（LVGL 相关）
- **工具:** MCP tools（inspect_design, generate_ui, render_ui, compare_ui, refine_ui, apply_patch）
- **入口:** MCP-first; see `.mcp.json`
- **禁止加载:** `tools/*_checker.py`, `examples/bad_*.c`（审查域内容）

---

## Debug Domain

**Trigger:** crash / HardFault / 死机 / 看门狗 / WDT / 崩溃日志 / frozen / deadlock

### Workflows
| Workflow | Trigger |
|----------|---------|
| [debug_crash.md](workflows/debug_crash.md) | HardFault / WDT / crash dump |

### Loading Rules
- **必读:** `references/core_rules.md`, `references/log_symptom_routes.json`
- **按需:** 1 个 `platforms/{platform}.md`, 症状匹配的 `prompts/{scene}.txt`
- **工具:** `python tools/log_triage.py`, `python tools/context_router.py`
- **禁止加载:** `mcp/`, `golden_pages/`, `native/`, `runtime/`

---

## App Domain

**Trigger:** manifest / 多页应用 / multi-page / Router / Presenter / Model / 脚手架

### Entry
- 通过 MCP `generate_ui(manifest_path=...)` 触发
- 无需独立 workflow，由 Generate Domain 的 MCP 工具链覆盖

### Loading Rules
- **必读:** `schemas/lvgl_ui_spec_v2.schema.json`, `tests/fixtures/manifest_v2_mvp.json`（参考）
- **按需:** `references/lvgl_*`
- **工具:** MCP `generate_ui` with `manifest_path`
- **禁止加载:** `tools/*_checker.py`, `prompts/`（审查域内容）

---

## Shared Rules (All Domains)

- Keep L1/L2/L3 mapping explicit; select a workflow before acting.
- Ask for platform when missing; ESP32/STM32/JL/BK are platforms, FreeRTOS/Zephyr are RTOS choices.
- Read routed prompts/references before suggesting platform bindings.
- Do not perform unplanned core SDK refactors; preserve critical logs and watchdog behavior.
- For commit requests, follow [git_commit_style](references/git_commit_style.md) and use `type(scope):`.
- LVGL UI generation must use the MCP toolchain; see [validation_contract](references/lvgl_validation_contract.md).
- Default output should be concise; use `--fix-detail full` only when complete details are needed.
- **Token rule:** Load ONLY the files listed in your domain's Loading Rules. Never load files from other domains.

## Constraint Shards (Reference Index)

Load only the shard(s) referenced by your selected workflow:

- `references/constraint_review.md`: C1-C4, C5-C6, C11-C16.
- `references/constraint_memory.md`: C7, C28, C36.
- `references/constraint_rtos.md`: C8, C15, C17, C29-C35, C43-C44.
- `references/constraint_platform.md`: C18-C21, C23, C42, C45-C46.
- `references/constraint_media.md`: C25-C27.
- `references/constraint_voice.md`: C10.
- `references/constraint_ota.md`: C9, C22, C24.
- `references/constraint_recover.md`: C37-C41.
- `references/constraint_bluetooth_protocol.md`: C46.
