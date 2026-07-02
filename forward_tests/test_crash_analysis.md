# 测试：Crash 分析

## 输入
- 目录：examples/
- 平台：esp32
- 工作流：debug_crash
- 期望触发：repro_bundle.py

## 验收条件
- [ ] repro_bundle.py 正常退出
- [ ] 输出 JSON 包含 `workflow: "debug_crash"`
- [ ] 输出包含 `environment` 字段
- [ ] 输出包含 `platform_profile` 字段
- [ ] 输出包含 `checker_json` 数组
- [ ] 无 Python traceback

## 自动化命令
```bash
python tools/repro_bundle.py --workflow debug_crash --dir examples --platform esp32 --output forward_tests/out_crash.json
```
