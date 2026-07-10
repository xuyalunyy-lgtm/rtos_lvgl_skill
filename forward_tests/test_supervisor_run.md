# Test: Codex Supervisor Managed Execution

## Input
- Job file: .codex/jobs/example-fix-checker.json
- Expected trigger: codex_supervisor.py run --dry-run

## Acceptance Criteria
- [ ] codex_supervisor.py --self-test all 12 items pass
- [ ] queue subcommand lists jobs
- [ ] gate subcommand returns approve for low-risk plans
- [ ] gate subcommand returns reject for protected paths
- [ ] gate subcommand returns reject for dangerous commands
- [ ] gate subcommand returns needs_confirmation for high risk
- [ ] run --dry-run exits normally (may abort due to dirty tree, which is expected behavior)
- [ ] run generates supervisor_report.json
- [ ] run generates supervisor_report.md
- [ ] run generates JSONL log
- [ ] No Python traceback

## Automation Command
```bash
python scripts/codex_supervisor.py --self-test
python scripts/codex_supervisor.py queue
python scripts/codex_supervisor.py run --job .codex/jobs/example-fix-checker.json --dry-run
```
