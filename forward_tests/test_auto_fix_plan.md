# 测试：自动修复计划

## 输入
- 文件：examples/bad_cjson_leak.c
- Checker：cjson
- 期望触发：auto_fix_engine.py --plan

## 验收条件
- [ ] auto_fix_engine.py --plan 正常退出
- [ ] JSON 输出包含 `actions` 数组
- [ ] 每个 action 包含 `risk_level` 字段
- [ ] 每个 action 包含 `confidence` 字段
- [ ] 每个 action 包含 `pre_checks` 数组
- [ ] 每个 action 包含 `post_checkers` 数组
- [ ] 输出包含 `pre_flight` 数组
- [ ] 输出包含 `total_risk` 字段
- [ ] --evidence 输出包含 fix_suggestions
- [ ] 无 Python traceback

## 自动化命令
```bash
python tools/auto_fix_engine.py examples/bad_cjson_leak.c --checker cjson --plan --json --evidence forward_tests/out_fixplan.json
```
