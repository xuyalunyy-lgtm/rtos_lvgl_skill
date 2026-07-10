# Test: Auto Fix Plan

## Input
- File: examples/bad_cjson_leak.c
- Checker: cjson
- Expected trigger: auto_fix_engine.py --plan

## Acceptance Criteria
- [ ] auto_fix_engine.py --plan exits normally
- [ ] JSON output contains `actions` array
- [ ] Each action contains `risk_level` field
- [ ] Each action contains `confidence` field
- [ ] Each action contains `pre_checks` array
- [ ] Each action contains `post_checkers` array
- [ ] Output contains `pre_flight` array
- [ ] Output contains `total_risk` field
- [ ] --evidence output contains fix_suggestions
- [ ] No Python traceback

## Automation Command
```bash
python tools/auto_fix_engine.py examples/bad_cjson_leak.c --checker cjson --plan --json --evidence forward_tests/out_fixplan.json
```
