# 测试：Codex Supervisor 托管执行

## 输入
- Job 文件：.codex/jobs/example-fix-checker.json
- 期望触发：codex_supervisor.py run --dry-run

## 验收条件
- [ ] codex_supervisor.py --self-test 12 项全绿
- [ ] queue 子命令列出 jobs
- [ ] gate 子命令对低风险计划返回 approve
- [ ] gate 子命令对保护路径返回 reject
- [ ] gate 子命令对危险命令返回 reject
- [ ] gate 子命令对 high 风险返回 needs_confirmation
- [ ] run --dry-run 正常退出（可能因脏树 abort，属预期行为）
- [ ] run 生成 supervisor_report.json
- [ ] run 生成 supervisor_report.md
- [ ] run 生成 JSONL 日志
- [ ] 无 Python traceback

## 自动化命令
```bash
python scripts/codex_supervisor.py --self-test
python scripts/codex_supervisor.py queue
python scripts/codex_supervisor.py run --job .codex/jobs/example-fix-checker.json --dry-run
```
