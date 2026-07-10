# Test: Codegen Gate Constraint-Driven Generation

## Input
- Project: tools/fixtures/mini_esp32
- Tools: project_scaffold.py + codegen_gate.py
- Expected trigger: generate -> manifest -> gate -> pass/fail

## Acceptance Criteria
- [ ] project_scaffold.py --name test --platform esp32 generates generation_manifest.json
- [ ] generation_manifest.json contains schema_version, generator, platform, generated_files, constraints
- [ ] codegen_gate.py --self-test all 5 items pass
- [ ] codegen_gate.py --dir <generated_dir> --manifest <manifest> --strict passes for valid code
- [ ] codegen_gate.py rejects code containing bare portMAX_DELAY
- [ ] codegen_gate.py rejects manifest with missing files
- [ ] codegen_gate.py rejects manifest with missing required fields
- [ ] codegen_gate.py rejects when constraints are uncovered (strict mode)
- [ ] No Python traceback

## Automation Command
```bash
python tools/codegen_gate.py --self-test
python tools/project_scaffold.py --name gate_test --platform esp32 --outdir /tmp/gate_test
python tools/codegen_gate.py --dir /tmp/gate_test/gate_test --manifest /tmp/gate_test/gate_test/generation_manifest.json --platform esp32 --strict
```
