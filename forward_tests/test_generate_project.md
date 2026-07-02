# 测试：生成项目

## 输入
- 项目名：test_voice_device
- Preset：voice-screen
- 平台：esp32
- 期望触发：project_scaffold.py --preset

## 验收条件
- [ ] project_scaffold.py 正常退出
- [ ] 生成 CMakeLists.txt
- [ ] 生成 main/main.c
- [ ] 生成 main/app_mvp.h
- [ ] 生成 main/task_topology.h
- [ ] 生成 constraint_manifest.json
- [ ] main.c 包含 task_topology 或 TaskHandle
- [ ] constraint_manifest.json 包含 required_constraints
- [ ] --evidence 输出包含 generated_files
- [ ] 无 Python traceback

## 自动化命令
```bash
python tools/project_scaffold.py --name test_voice_device --preset voice-screen --platform esp32 --outdir forward_tests/out_project --evidence forward_tests/out_project_evidence.json
```
