# Archive

This directory contains **deprecated and experimental** files that are no longer part of the active skill runtime.

## Structure

| Directory | Contents | Status |
|---|---|---|
| `tools/` | 18 deprecated Python tools (scheduler_analyzer, rtos_sim, etc.) | Replaced by active `tools/` checkers. Safe to delete after verifying no references remain. |
| `workflows/` | 5 deprecated workflow definitions | Replaced by current `workflows/` files. |
| `codex/` | Experimental Codex/agent orchestration artifacts | Internal experiment, not part of release. |

## Why Archived

- **tools/**: Early prototypes for scheduler analysis, RTOS simulation, IPC contract checking, etc. Superseded by the constraint-based checker system in `tools/checker_registry.py`.
- **workflows/**: Earlier versions of architecture review, auto-repair, and self-iteration flows. Replaced by L2/L3 workflow structure.
- **codex/**: Experimental agent orchestration hooks and job definitions. Not part of the published skill.

## Guidelines

- **Do not load** these files during normal skill operation.
- **Do not search** here when looking for active tool entry points.
- `check_links.py` and `check_runtime_distribution.py` exclude this directory.
- Files here may be deleted without notice if they cause confusion.
