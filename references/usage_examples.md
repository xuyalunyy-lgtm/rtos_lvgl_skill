# Usage Examples

> Load on demand. Read this file when the user or Agent asks "how do I use this skill?"

---

## Quick Start

Enter the project directory, then trigger the skill:

```
Use the freertos-embedded-architect skill to review this ESP32 project
```

The Agent will:
1. Load `SKILL.md` routing table
2. Select `l2_code_review` workflow
3. Declare platform `esp32`
4. Run `run_review.py --dir src --platform esp32`

---

## Common Tasks

### 1. Code Review

```
Review the FreeRTOS code quality in src/main.c
```

Agent should:
- Select `l2_code_review` workflow
- Run `run_review.py --dir src`
- Output `[P0] C3.1 — file:line — problem description`
- Provide fix suggestions and verification commands

### 2. New Module Design

```
Design an audio_player module for ESP32 with I2S output
```

Agent should:
- Select `l3_new_module` workflow
- Run `module_contract_gen.py --name audio_player`
- Generate `audio_player_contract.h` + `audio_player_fsm.c`
- Reference C29 (module contract), C33 (lifecycle symmetry)

### 3. Crash Debugging

```
Device resets with watchdog 5 seconds after boot, here's the serial log
```

Agent should:
- Select `debug_crash` workflow
- Load symptom table, match WDT reset pattern
- Reference C31 (blocking wait), C15 (priority)
- Provide troubleshooting steps and verification commands

### 4. LVGL/DMA/ISR Safety Check

```
Check if LVGL is called from the correct thread
```

Agent should:
- Select `l2_code_review` workflow
- Run `lvgl_thread_checker.py`
- Reference C1 (LVGL thread safety), C4 (ISR safety)

### 5. Memory Analysis

```
The device heap keeps decreasing over time
```

Agent should:
- Select `l2_memory_analysis` workflow
- Reference C7 (memory allocation), C2 (queue ownership), C3 (cJSON leak)
- Provide heap profiling steps

### 6. Board Bring-up

```
Bring up a new ESP32-S3 board with LCD and audio
```

Agent should:
- Select `l3_bring_up` workflow
- Load `platforms/esp32.md`
- Follow the 7-phase bring-up sequence
- Reference C8 (boot order), C23 (display), C25 (A/V pipeline)


### 7. LVGL ????????

```
Use the freertos-embedded-architect skill to generate an LVGL page from ui/*.png design and cut assets
```

Agent should:
- Select `lvgl_page` workflow and read MCP `display-config` / `theme-skill` first.
- Classify inputs as design screenshot, runtime cut asset, reference crop, or component-only.
- Generate `analysis_report.json`, `debug_overlay.png`, and any template-match debug images before trusting the code.
- Treat `preview.html` only as an approximate browser preview, not as a comparison result.
- Use constrained template matching: match small icons only inside their detected button/card region, and keep residual detection as fallback only.
- Generate LVGL components for battery, loading arc, glass panel, cards, buttons, and labels; use images only for real cut assets.
- Keep text/images/fonts behind macros such as `UI_TEXT_*`, `UI_IMG_SRC_*`, and `UI_FONT_*`.
- Add custom-event listener and async post helper on the page root so worker threads do not call LVGL directly.
- Run quick validation first: Pillow analysis, code generation, `validate_lvgl_layout_code`, and JSON/C coordinate sanity checks. Use full `lvgl_render` regression only when needed.

---

## Expected Output

Agent responses should include:

| Element | Example |
|---------|---------|
| Workflow | `l2_code_review` |
| Platform | `esp32` |
| Constraints | `C1`, `C4`, `C29` |
| Issues | `[P0] C3.1 — main.c:42 — cJSON not freed` |
| Fix | `Use goto cleanup template` |
| Verify | `python tools/run_review.py --self-test` |

---

## Framework-Aware Review

```
Detect which frameworks this project uses, then check framework constraints
```

Agent should:
- Run `framework_profile.py --dir src`
- Run `framework_constraint_checker.py --auto`
- Output framework matrix and framework-specific issues
