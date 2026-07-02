# Forward Tests — Skill 前向测试体系

验证 skill 触发、懒加载、输出质量，而非只测脚本。

## 测试用例

| 测试 | 模拟任务 | 验证目标 |
|------|---------|---------|
| test_code_review.md | 代码审查 | run_review 触发、checker 输出、evidence 生成 |
| test_crash_analysis.md | Crash 分析 | debug_crash 工作流、repro_bundle 输出 |
| test_generate_module.md | 生成模块 | module_contract_gen 多模块、preset 集成 |
| test_generate_project.md | 生成项目 | project_scaffold --preset、task_topology |
| test_auto_fix_plan.md | 自动修复 | auto_fix_engine --plan、FixPlan 结构 |

## 运行方式

```bash
python forward_tests/run_forward_tests.py
python forward_tests/run_forward_tests.py --test code_review
python forward_tests/run_forward_tests.py --json
```

## 验收条件

每个测试用例验证：
1. 工具正确触发（exit code）
2. 输出格式正确（JSON/evidence）
3. 无 Python 异常
4. 关键字段存在
