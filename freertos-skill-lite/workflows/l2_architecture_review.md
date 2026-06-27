# Workflow: L2 架构设计审查

场景：用户发起「软件架构 review / 架构评审 / 模块边界评估」时使用。  
目标：给出可落地的 RTOS 架构判断，发现会导致实时性能、稳定性与可维护性问题的设计缺陷。

## Step 1：确认输入完整性（先于审查）

- 产品目标是否明确（关键指标、吞吐/时延、功耗）
- 平台约束是否明确（SoC、外设、总线、DMA/IRQ）
- 各任务验收指标是否明确（P0/P1/P2）
- 是否有启动顺序、错误恢复和回退策略
- 是否提供已有架构描述（模块、队列、ISR、驱动、状态定义）

缺失关键项时，先给补充问题清单，不产出完整审查结论。

## Step 2：加载所需上下文

- `references/core_rules.md`
- `references/constraint_index.md`
- `platforms/<xxx>.md`
- `references/skill_structure.md`
- `prompts/software_architecture_design.txt`
- 如属于工程级任务，参考 `workflows/l2_project_review.md`

## Step 3：输出审查与必检点（Architecture Mandatory Checklist）

下面 3 类约束为硬性检查项，每项必须给出状态：
- `[PASS]`：通过
- `[WARN]`：部分通过，需补充
- `[FAIL]`：不通过，明确阻塞项

### A. 输入-处理-输出（I/P/O）与 RTOS 队列解耦
1. 是否存在清晰三层划分（Input / Core / Output）？
2. ISR/DMA 回调是否只做打包入队，不包含业务计算？
3. 数据包结构是否固定（字段、长度、校验、时间戳、来源）？
4. 入/出队列是否定义了深度、溢出策略、超时策略、丢失统计？
5. 数据所有权是否明确（谁分配、谁消费、谁释放）？

### B. 状态机驱动架构（FSM / HFSM）
1. 是否存在状态机模型而非大量 `if` 脱节逻辑？
2. 是否存在主状态和必要子状态（HFSM）？
3. 是否存在错误态与恢复路径（如 `ERROR -> RECOVERING -> IDLE`）？
4. 是否禁止 ISR 直接改写业务状态？是否有事件化触发机制？
5. 是否提供状态转移可观测性（状态计数、非法转移、停滞检测）？

### C. HAL + 组件化架构
1. 应用层是否通过接口访问外设（非硬依赖 vendor HAL）？
2. 是否存在 `xxx_ops_t` / 上下文句柄/组件注册机制？
3. 是否有平台适配替换策略（宏/链接策略），核心层不改即可切换芯片实现？
4. 关键外设（ADC/GPIO/I2C/DISPLAY/FLASH 等）是否都有最小接口定义？
5. 接口错误码与生命周期（init/start/stop/deinit）是否一致？

## Step 4：发现项归类

按优先级输出整改清单：

- P0（必须修复）：架构不兼容、实时性失效、安全/可靠性风险、数据丢失关键路径错误
- P1（建议修复）：影响稳定性或可维护性，当前可运行但有回归风险
- P2（优化）：长周期演进性问题或可观测性不足

每个问题输出：`位置 -> 问题 -> 风险 -> 修改建议 -> 验证方式`

## Step 5：最终交付格式

```markdown
## 架构审查结论
- 总体结论：PASS / WARN / FAIL
- 关键阻塞项：<最多 3 条，含处理优先级>

## Architecture Mandatory Checklist
- A. I/P/O 三层架构：[PASS/WARN/FAIL]
- B. FSM / HFSM：[PASS/WARN/FAIL]
- C. HAL + 组件化：[PASS/WARN/FAIL]

### 1. 架构问题清单
- P0:
- P1:
- P2:

### 2. 修复建议（按顺序）
- ...

### 3. 验收测试清单
- 中断洪峰下队列行为
- 状态机非法转移与错误恢复
- 队列丢包/延迟/溢出告警
- HAL 接口注入替换验证

### 4. 输出文档建议
- ARCHITECTURE.md
- docs/sequence.md
- components/<module>/README.md
```

## 执行原则

- 必须以 `software_architecture_design.txt` 的输出结构为基准核对
- 只给“可执行、可验证、可回滚”的建议
- 避免给出与 RTOS 特性冲突的设计（如在高频 ISR 中做复杂处理）
