# Test: Crash Analysis

## Input
- Directory: examples/
- Platform: esp32
- Workflow: debug_crash
- Expected trigger: repro_bundle.py

## Acceptance Criteria
- [ ] repro_bundle.py exits normally
- [ ] Output JSON contains `workflow: "debug_crash"`
- [ ] Output contains `environment` field
- [ ] Output contains `platform_profile` field
- [ ] Output contains `checker_json` array
- [ ] No Python traceback

## Automation Command
```bash
python tools/repro_bundle.py --workflow debug_crash --dir examples --platform esp32 --output forward_tests/out_crash.json
```
