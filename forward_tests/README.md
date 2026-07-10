# Forward Tests — Skill Forward Test Framework

Validate skill triggering, lazy loading, and output quality, not just script testing.

## Test Cases

| Test | Simulated Task | Verification Target |
|------|---------------|---------------------|
| test_code_review.md | Code Review | run_review trigger, checker output, evidence generation |
| test_crash_analysis.md | Crash Analysis | debug_crash workflow, repro_bundle output |
| test_generate_module.md | Generate Module | module_contract_gen multi-module, preset integration |
| test_generate_project.md | Generate Project | project_scaffold --preset, task_topology |
| test_auto_fix_plan.md | Auto Fix | auto_fix_engine --plan, FixPlan structure |

## How to Run

```bash
python forward_tests/run_forward_tests.py
python forward_tests/run_forward_tests.py --test code_review
python forward_tests/run_forward_tests.py --json
```

## Acceptance Criteria

Each test case verifies:
1. Tool triggers correctly (exit code)
2. Output format is correct (JSON/evidence)
3. No Python exceptions
4. Key fields are present
