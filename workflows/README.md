# Workflow Index

Control entry: [SKILL.md](../SKILL.md) | Structure notes: [skill_structure.md](../references/skill_structure.md)

Load one workflow first, then only the referenced prompts, references, and platform notes.

| File | Level | Trigger |
|------|------|---------|
| [l2_code_review.md](l2_code_review.md) | L2 | code review / audit / checker-guided review |
| [l2_code_review_lite.md](l2_code_review_lite.md) | L2 | manual Lite-style review checklist |
| [l2_project_review.md](l2_project_review.md) | L2 | project/workspace review before production |
| [debug_crash.md](debug_crash.md) | L2-L3 | HardFault / deadlock / WDT / frozen system |
| [l3_sdk_trim.md](l3_sdk_trim.md) | L3 | SDK trimming / demand-driven driver pruning |
| [l3_new_module.md](l3_new_module.md) | L3 | new module / multitask MVP design |
| [hw_sw_cocodebug.md](hw_sw_cocodebug.md) | L2 | hardware-software co-debug / IO planning / GPIO conflict / bring-up |
| [l3_bring_up.md](l3_bring_up.md) | L3 | board bring-up / minimum system / peripheral validation |
| [l2_memory_analysis.md](l2_memory_analysis.md) | L2 | memory analysis / baseline / leak and pool investigation |
| [l3_lvgl_page.md](l3_lvgl_page.md) | L3 | LVGL page generation and MVP integration |

Archived maintainer workflows:

| File | Status |
|------|--------|
| [l2_architecture_review.md](../archive/workflows/l2_architecture_review.md) | archived in v31 |
| [l2_auto_repair.md](../archive/workflows/l2_auto_repair.md) | archived in v31 |
| [self_iterate.md](../archive/workflows/self_iterate.md) | archived in v31 |

Standard load order:

1. `references/core_rules.md`
2. `references/constraint_index.md`; load `constraint_detail.md` only when needed
3. one relevant `platforms/xxx.md`
4. the prompts referenced by the selected workflow
5. `tools/run_review.py` and examples for full validation

Architecture sync check:

```bash
python scripts/check_architecture_sync.py
```
