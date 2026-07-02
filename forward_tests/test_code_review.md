# 测试：代码审查

## 输入
- 目录：examples/
- 平台：esp32
- 期望触发：run_review.py

## 验收条件
- [ ] run_review.py 正常退出（exit code 0 或 1）
- [ ] JSON 输出包含 `checkers` 数组
- [ ] JSON 输出包含 `total_issues` 字段
- [ ] --evidence 输出包含 `source_tool: "run_review"`
- [ ] --evidence 输出包含 `issues` 数组
- [ ] 无 Python traceback

## 自动化命令
```bash
python tools/run_review.py --dir examples --json --evidence forward_tests/out_review.json
```
