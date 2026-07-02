# Supervisor Report — 3d981e919a1d

| 字段 | 值 |
|------|-----|
| Job | example-fix-checker |
| 状态 | **aborted** |
| 迭代 | 0/3 |
| 分支 |  |
| 耗时 | 0.0s |

## 计划
- 意图: N/A
- 风险: N/A
- 文件: 0 个

## 门禁

## Diff
```

```

## 验证

## 错误
- 工作区有未提交修改:
M scripts/codex_supervisor.py
?? .codex/jobs/
?? .codex/runs/
?? .codex/schemas/gate_decision.schema.json
?? .codex/schemas/job.schema.json
?? .codex/schemas/supervisor_report.schema.json

请先 commit/stash 或在 job 中设置 require_clean_worktree=false