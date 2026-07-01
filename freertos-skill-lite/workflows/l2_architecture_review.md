# Workflow: L2 架构设计审查

场景：用户发起「软件架构 review / 架构评审 / 模块边界评估」时使用。  
目标：给出可落地的 RTOS 架构判断，识别实时性、稳定性、可恢复性与可维护性风险。

## Step 1：确认输入完整性（先于审查）

- 产品目标是否明确（吞吐/时延/功耗/容量）
- 平台约束是否明确（SoC、外设、总线、DMA/IRQ）
- P0/P1/P2 目标与验收指标是否明确
- 是否提供启动顺序、错误恢复与回退策略
- 是否提供架构输入（模块列表、模块契约、任务/队列拓扑、ISR 处理路径、状态定义）

缺失关键项时，先输出补充问题清单，不产出完整审查结论。

## Step 2：加载上下文

- `references/core_rules.md`
- `references/constraint_index.md`
- `references/constraint_detail.md`（按需）
- `platforms/<xxx>.md`
- `references/skill_structure.md`
- `prompts/software_architecture_design.txt`
- `prompts/runtime_efficiency_contracts.txt`（涉及模块边界、任务拓扑、超时预算、生命周期、热路径、关键路径预算、数据拷贝、背压降级、故障恢复、配置矩阵、复现闭环、回归样本或板级资源时）
- 如属于工程级任务，参考 `workflows/l2_project_review.md`

## Step 3：Architecture Mandatory Checklist（硬约束）

以下每项必须输出：`[PASS/WARN/FAIL]`

### A. I/P/O 三层 + RTOS 队列解耦
1. 是否存在明确三层：Input / Core / Output
2. ISR/DMA 回调是否只做入队与最小处理
3. Raw 消息是否有固定数据模型（时间戳/CRC/来源/序列）
4. 队列深度、超时、溢出策略是否完整
5. 所有权转移与内存释放是否明确

### B. FSM / HFSM
1. 是否有状态机驱动而非分散分支逻辑
2. 是否覆盖 ERROR->RECOVERING->IDLE 类恢复链路
3. 是否定义非法状态转移行为（兜底/告警/限流）
4. ISR 与核心状态更新是否解耦（事件化）
5. 是否有状态可观测指标（状态计数、非法转移计数）

### C. HAL + 组件化
1. 核心业务是否只依赖接口结构体，不直接访问厂商 API
2. 是否有 `xxx_ops_t / handle / component registry`
3. 是否定义关键外设最小接口（至少 5 个）
4. 是否可替换芯片实现且核心层不改
5. 错误码和生命周期是否统一（init/start/stop/deinit）

### D. C29-C45 运行时效率契约
1. 每个模块是否声明 context/blocking/ownership/lifecycle/error（C29）
2. 是否有 task/queue topology：priority/stack/depth/producer/consumer/backpressure/exit（C30）
3. 所有等待是否有 timeout budget，永久等待是否满足例外条件（C31）
4. 是否有 state/error/counter/watermark/max time/dump 观测点（C32）
5. acquire/release 是否对称，hot path 是否只做轻量投递和计数（C33/C34）
6. 关键路径是否有 stage budget、timeout、fallback、metric（C35）
7. 数据路径是否声明 copy count、owner/release、DMA cache 策略（C36）
8. 高频 producer 是否有背压、降级、bounded retry 与 telemetry（C37）
9. 故障域、自动恢复、supervisor/watchdog 与安全降级是否明确（C38）
10. Kconfig/feature/board/SDK 差异是否进入配置矩阵并 fail fast（C39）
11. build/flash/log/decode/test 是否有一键复现闭环（C40）
12. 新约束/bugfix 是否有通用 good/bad 回归样本（C41）
13. GPIO/DMA/clock/IRQ/cache/heap/PSRAM 是否有板级资源契约（C42）
14. 锁等待、持锁预算、lock_order 和优先级继承是否明确（C43）
15. 临界区/关中断是否短小、对称、有预算且无重活（C44）
16. 传感器 init/probe、总线 timeout、data-ready、sample metadata 与校准生命周期是否明确（C45）

## Step 4：架构评分门禁（必须给出）

- 定义三档分数并给总分：
  - 实时性与正确性（40%）
  - 可维护性与可移植性（30%）
  - 可观测性与可恢复性（30%）
- 总分规则：
  - `PASS >= 85`
  - `WARN >= 70`
  - `FAIL < 70`
- 直接阻塞条件（即使总分高也 FAIL）：
  - I/P/O 未解耦且 ISR 有业务逻辑
  - 业务状态在 ISR 内直接改变
  - HAL 未抽象，核心层直接依赖 MCU SDK
  - Error recovery 缺失或不可观测
  - 队列策略未定义但存在高频消息
  - 存在无界等待或 hot path 阻塞

## Step 5：异常场景验证矩阵（必须至少覆盖）

每项给出：场景 -> 预期行为 -> 风险 -> 修复建议 -> 观测指标

1. 中断风暴（>95% 峰值速率）
2. 队列满且持续 1s / 5s
3. 非法状态转移突发
4. 外设驱动返回错误码风暴
5. 看门狗触发后 2 次恢复尝试

## Step 6：问题归类与整改优先级

- P0（必须修）：直接阻断实时性/安全/可靠性的缺陷
- P1（应修）：当前可运行，但存在高回归风险
- P2（优化）：可复用性、测试覆盖和文档可迭代提升项

每个问题输出：`位置 -> 问题 -> 风险 -> 方案 -> 验证 -> 负责人建议`

## Step 7：主线 / Lite 一致性治理

- 校验项（审查时必须出现）：
  - 主线与 Lite 的 `software_architecture_design` 是否都包含 I/P/O/FSM/HAL 三类约束
  - 主线与 Lite 的 `l2_architecture_review` 是否都具备评分门禁与异常场景
- 不一致将记录为 P0（文档治理阻塞），建议同步提交

## Step 8：输出格式（严格）

```markdown
## 架构审查结论
- 总体结论：PASS / WARN / FAIL
- 总分：xx / 100
- 关键阻塞项：
  - ...

## Architecture Mandatory Checklist
- A. I/P/O 三层：PASS/WARN/FAIL
- B. FSM/HFSM：PASS/WARN/FAIL
- C. HAL + 组件化：PASS/WARN/FAIL
- D. C29-C45 运行时效率契约：PASS/WARN/FAIL

### 1. 评分明细
- 实时性与正确性：xx/40
- 可维护性与可移植性：xx/30
- 可观测性与可恢复性：xx/30

### 2. 发现项
- P0:
- P1:
- P2:

### 3. 异常场景验证
- ...

### 4. 一致性治理
- 主线/Lite 同步校验：PASS / FAIL
- 不一致项：...

### 5. 建议与下一步
- ...
```
