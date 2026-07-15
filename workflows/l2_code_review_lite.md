# 工作流：L2 代码审查（Lite 版）

**触发：** 用户要求 review / audit / 审查嵌入式 C 代码。

> Lite 无 `examples/` 与 `tools/`。反例见完整版 `examples/bad_*.c` 文字描述。

## Step 1 — 读总纲

[references/core_rules.md](../references/core_rules.md)

## Step 2 — 反模式速查

| 违规 | 典型写法 | 后果 |
|------|----------|------|
| 跨线程 LVGL | WSS 任务里 `lv_label_set_text` | HardFault / 花屏 |
| ISR 阻塞 | Callback 里 `xSemaphoreTake(..., portMAX_DELAY)` | 系统卡死 |
| cJSON 泄漏 | `Parse` 后 early `return` 无 `Delete` | 堆耗尽 |
| 栈指针进 Queue | 传局部变量地址 | 野指针 |
| WSS tight 重连 | 断线立即握手无退避 | heap / WDT |
| 缺模块契约 | API 未说明 context/blocking/ownership | 接手成本高 / 误调用 |
| 无界等待 | `portMAX_DELAY` / `WAIT_FOREVER` 默认使用 | 假死 / stop 卡住 |
| 热路径重活 | callback 内 malloc/printf/JSON/TLS | 实时尖峰 / WDT |

按需读 scene prompt（仅相关 1–2 个）；模块契约/拓扑读 [module_contract_topology.txt](../prompts/module_contract_topology.txt)、超时/可观测/生命周期读 [timeout_lifecycle_observability.txt](../prompts/timeout_lifecycle_observability.txt)、热路径/关键路径/数据拷贝读 [hotpath_critical_budget.txt](../prompts/hotpath_critical_budget.txt)、背压降级/故障恢复/配置矩阵/复现闭环/回归样本读 [backpressure_recovery_config.txt](../prompts/backpressure_recovery_config.txt)、板级资源/锁预算/临界区/传感器集成读 [runtime_efficiency_contracts.txt](../prompts/runtime_efficiency_contracts.txt)。

## Step 3 — 人工审查

执行 [references/lite_manual_checklist.md](../references/lite_manual_checklist.md) 全部 checkbox。

## Step 4 — 输出

```markdown
## 结论
## 违规项
## Lite 人工审查已完成
## 修复优先级
```
