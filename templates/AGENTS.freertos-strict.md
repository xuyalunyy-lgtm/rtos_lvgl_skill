# AGENTS.md — FreeRTOS Embedded Architect (Strict Mode)

> Place this file in the project root as `AGENTS.md` so that Codex/Claude automatically follows FreeRTOS skill discipline in this project.

## Project Constraints

This project uses the `freertos-embedded-architect` skill to manage all RTOS/firmware/embedded-related tasks.

### Default Platform

- Platform: `esp32` (can be changed in project configuration)
- Framework: `ESP-IDF`, `LVGL`, `mbedTLS`

### Mandatory Rules

1. **Code Review**: Must use the `l2_code_review` workflow, run `run_review.py`
2. **New Module**: Must use the `l3_new_module` workflow, generate `*_contract.h` + `*_fsm.c`
3. **Crash Analysis**: Must use the `debug_crash` workflow
4. **Auto Repair**: Must use the `l2_auto_repair` workflow, output `--plan` without directly modifying code
5. **Release**: Must use the `l2_release_qualification` workflow

### Constraint System

- RTOS core constraints: C1-C48
- Framework constraints: LVGL-1~5, ESP-IDF-1~7, MBEDTLS-1~4, LWIP-1~4
- Every response must reference relevant constraint domains

### Verification Commands

```bash
# Code Review
python tools/run_review.py --dir src --platform esp32

# RTOS System Review (integrated via run_review.py)
python tools/run_review.py --dir src --platform esp32

# Framework Check
python tools/framework_constraint_checker.py --dir src --auto

# Release Gate
python scripts/skill_iterate.py --check
python scripts/commit_audit.py --strict-release
```

### Strict Mode Activation

Say in the conversation: "Enable freertos-embedded-architect strict mode"

In strict mode:
- Must select a workflow every round
- Must declare platform/framework
- Must reference constraints
- Must have a verification plan
