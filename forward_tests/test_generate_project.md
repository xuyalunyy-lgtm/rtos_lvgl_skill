# Test: Generate Project

## Input
- Project name: test_voice_device
- Preset: voice-screen
- Platform: esp32
- Expected trigger: project_scaffold.py --preset

## Acceptance Criteria
- [ ] project_scaffold.py exits normally
- [ ] Generates CMakeLists.txt
- [ ] Generates main/main.c
- [ ] Generates main/app_mvp.h
- [ ] Generates main/task_topology.h
- [ ] Generates constraint_manifest.json
- [ ] main.c contains task_topology or TaskHandle
- [ ] constraint_manifest.json contains required_constraints
- [ ] --evidence output contains generated_files
- [ ] No Python traceback

## Automation Command
```bash
python tools/project_scaffold.py --name test_voice_device --preset voice-screen --platform esp32 --outdir forward_tests/out_project --evidence forward_tests/out_project_evidence.json
```
