# 测试：RTOS 系统审查

## 输入
- 项目：tools/fixtures/mini_esp32
- 工具：rtos_model.py + task_graph_analyzer.py + scheduler_analyzer.py + ipc_contract_checker.py + memory_lifetime_analyzer.py + timebase_analyzer.py
- 期望触发：模型提取 → 任务图 → 调度 → IPC → 内存 → 时间基准

## 验收条件
- [ ] rtos_model.py --dir fixtures/mini_esp32 输出 ≥3 tasks、≥2 queues、≥1 mutex、≥1 timer
- [ ] task_graph_analyzer.py --model rtos_model.json 输出风险列表
- [ ] scheduler_analyzer.py --model rtos_model.json 输出风险列表
- [ ] ipc_contract_checker.py --model rtos_model.json 输出 IPC 契约
- [ ] memory_lifetime_analyzer.py --model rtos_model.json 输出内存风险
- [ ] timebase_analyzer.py --model rtos_model.json 输出时间风险
- [ ] 无 Python traceback

## 自动化命令
```bash
python tools/rtos_model.py --dir tools/fixtures/mini_esp32 --output /tmp/rtos_model.json
python tools/task_graph_analyzer.py --model /tmp/rtos_model.json
python tools/scheduler_analyzer.py --model /tmp/rtos_model.json
python tools/ipc_contract_checker.py --model /tmp/rtos_model.json
python tools/memory_lifetime_analyzer.py --model /tmp/rtos_model.json
python tools/timebase_analyzer.py --model /tmp/rtos_model.json
```
