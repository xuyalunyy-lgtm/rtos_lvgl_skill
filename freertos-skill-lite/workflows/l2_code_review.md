# Workflow: L2 Code Review

**触发：** 用户要求 review / audit / 审查嵌入式 C 代码质量。

<thinking>
1. 确认目标平台（ESP32/STM32/JL/BK）
2. 识别涉及模块：网络 / LVGL / 音频 / cJSON
3. 仅加载与本审查相关的 scene prompt（勿加载全部 prompts/）
</thinking>

## Step 1 — 读总纲

读取 [references/core_rules.md](../references/core_rules.md) 六条硬性约束 + [constraint_detail.md](../references/constraint_detail.md)（违规报告引用 `C#.#`）。

## Step 2 — 反例对照

| 嫌疑 | 对照 |
|------|------|
| 跨线程 LVGL | 完整版 `examples/bad_lvgl_cross_thread.c` |
| ISR 阻塞 | 完整版 `examples/bad_isr_blocking.c` |
| cJSON 泄漏 | 完整版 `examples/bad_cjson_leak.c` |
| **Queue 栈指针/cJSON*** | 完整版 `examples/bad_queue_stack_pointer.c` |
| WSS 栈/重连 | 完整版 `examples/bad_wss_blocking.c` → 正例 完整版 `examples/good_wss_reconnect.c` |

按需深读：[lvgl_thread_safety.txt](../prompts/lvgl_thread_safety.txt)、[memory_ownership.txt](../prompts/memory_ownership.txt)、[deadlock_lock_order.txt](../prompts/deadlock_lock_order.txt)

## Step 3 — 人工审查（Lite）

使用 [l2_code_review_lite.md](l2_code_review_lite.md)。
## Step 4 — 输出

<output_format>

```markdown
## 结论
通过 / 需修复（一句话）

## 违规项（对照 constraint_detail `C#.#`）
- C2.2 — file:line — 问题 — 修复建议（引用 good 范例模式）

## Checker 结果
（粘贴 run_review 摘要或「未运行」）

## 修复优先级
P0 安全/崩溃 → P1 泄漏/死锁 → P2 风格
```

</output_format>
