# Test: RTOS System Review

## Input
- Project: tools/fixtures/mini_esp32
- Tool: run_review.py (with integrated RTOS review capabilities)
- Expected trigger: constraint check -> risk report -> suggestion output

## Acceptance Criteria
- [ ] run_review.py --dir fixtures/mini_esp32 --platform esp32 outputs constraint check results
- [ ] Output contains task/queue/mutex/timer related constraint checks
- [ ] Output contains scheduling, IPC, memory, timebase related risk warnings
- [ ] No Python traceback

## Automation Command
```bash
python tools/run_review.py --dir tools/fixtures/mini_esp32 --platform esp32 --json
```

## Notes
The original RTOS-specific tools (rtos_model.py, task_graph_analyzer.py, scheduler_analyzer.py,
ipc_contract_checker.py, memory_lifetime_analyzer.py, timebase_analyzer.py)
have been archived to archive/tools/, and the related review capabilities have been integrated into run_review.py.
