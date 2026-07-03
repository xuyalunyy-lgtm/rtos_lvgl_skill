# 测试：RTOS 系统审查

## 输入
- 项目：tools/fixtures/mini_esp32
- 工具：run_review.py（集成 RTOS 审查能力）
- 期望触发：约束检查 → 风险报告 → 建议输出

## 验收条件
- [ ] run_review.py --dir fixtures/mini_esp32 --platform esp32 输出约束检查结果
- [ ] 输出包含 task/queue/mutex/timer 相关约束检查
- [ ] 输出包含调度、IPC、内存、时间基准相关风险提示
- [ ] 无 Python traceback

## 自动化命令
```bash
python tools/run_review.py --dir tools/fixtures/mini_esp32 --platform esp32 --json
```

## 备注
原 RTOS 专用工具（rtos_model.py、task_graph_analyzer.py、scheduler_analyzer.py、
ipc_contract_checker.py、memory_lifetime_analyzer.py、timebase_analyzer.py）
已归档至 archive/tools/，相关审查能力已集成到 run_review.py 中。
