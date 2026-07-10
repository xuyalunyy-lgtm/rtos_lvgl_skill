# Test: Code Review

## Input
- Directory: examples/
- Platform: esp32
- Expected trigger: run_review.py

## Acceptance Criteria
- [ ] run_review.py exits normally (exit code 0 or 1)
- [ ] JSON output contains `checkers` array
- [ ] JSON output contains `total_issues` field
- [ ] --evidence output contains `source_tool: "run_review"`
- [ ] --evidence output contains `issues` array
- [ ] No Python traceback

## Automation Command
```bash
python tools/run_review.py --dir examples --json --evidence forward_tests/out_review.json
```
