# L2: RTOS System Review — 系统级审查

> 从代码/模型中提取 RTOS 系统模型，运行 task graph、scheduler、IPC、memory、timebase 分析。

## 触发条件

- 用户要求"RTOS 系统审查"、"任务拓扑分析"、"调度分析"
- 新模块引入 task/queue/mutex 时
- 性能问题、优先级反转、死锁排查时

## 步骤

### 1. 生成系统模型

```bash
python tools/rtos_model.py --dir src --output rtos_model.json
```

或从 constraint_manifest.json 生成：

```bash
python tools/rtos_model.py --from-manifest constraint_manifest.json --output rtos_model.json
```

### 2. 任务图分析

```bash
python tools/task_graph_analyzer.py --model rtos_model.json
```

关注：循环等待、无消费者队列、无背压 producer、孤儿任务。

### 3. 调度分析

```bash
python tools/scheduler_analyzer.py --model rtos_model.json
```

关注：优先级反转、高优先级饥饿、core affinity 错误、锁持有时间。

### 4. IPC 契约检查

```bash
python tools/ipc_contract_checker.py --model rtos_model.json
```

关注：大 payload 队列、无 timeout、ISR-safe 标记、跨核同步。

### 5. 内存生命周期分析

```bash
python tools/memory_lifetime_analyzer.py --model rtos_model.json
```

关注：无 owner pool、跨任务 pool、热路径分配、delete cleanup。

### 6. 时间基准分析

```bash
python tools/timebase_analyzer.py --model rtos_model.json
```

关注：timer 回调阻塞、周期 jitter、永久等待。

### 7. What-if 模拟（可选）

```bash
python tools/rtos_sim.py --model rtos_model.json --what-if changes.json
```

## 输出

各分析器输出风险列表和约束域，汇总为系统审查报告。
