# Workflow: L2 Code Review（Lite 版）

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

按需读 scene prompt（仅相关 1–2 个）。

## Step 3 — 人工审查

执行 [references/lite_manual_checklist.md](../references/lite_manual_checklist.md) 全部 checkbox。

## Step 4 — 输出

```markdown
## 结论
## 违规项
## Lite 人工审查已完成
## 修复优先级
```
