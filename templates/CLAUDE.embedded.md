# Embedded Firmware — Claude Code Index (<500 tokens, do not inflate)

## Skill
FreeRTOS/LVGL/IoT architecture and review: invoke **`/freertos-embedded-architect`** or specify the chip platform.
Skill path: `~/.claude/skills/freertos-embedded-architect/` (see skill repository `scripts/install_claude_code.*` for installation).

## This Platform (required — change placeholders below)
- **Chip/SDK:** <!-- JL AC79 / BK7258 Armino / ESP32 / STM32 -->
- **Build:** <!-- make bk7258 / idf.py build / make ac791n_xxx -->
- **Source root:** <!-- src/ or projects/xxx/ap/ -->

## Token Rules (every session)
1. **Forbidden** to Read/Glob the entire skill; only read files listed in the current workflow
2. L2 uses `references/constraint_index.md`, not the full `constraint_detail.md`
3. **1** `platforms/*.md` + **at most 3** `prompts/*.txt`
4. Examples use Grep/Read **single file**; review uses `python <skill>/tools/run_review.py --dir <src> --platform <x>`

## L3 Autonomous Implementation
Implementation/Bug fix: **full authority to modify code**, no step-by-step confirmation needed, until functionality is complete and **build has 0 errors**. Iron rules C1-C8 still apply.

## LVGL UI Generation
For LVGL work, follow `workflows/l3_lvgl_page.md`, use the target project's build and verification flow, and keep all LVGL updates in the GUI context.

## Ignore Large Directories
See `.claudeignore` in the same directory (SDK/build should not enter context).
