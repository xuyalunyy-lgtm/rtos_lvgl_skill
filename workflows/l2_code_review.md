# Workflow: L2 Code Review

**触发：** 用户要求 review / audit / 审查嵌入式 C 代码质量。

<thinking>
1. 确认目标平台（ESP32/STM32/JL/BK）
2. 识别涉及模块：网络 / LVGL / 音频 / cJSON
3. 仅加载与本审查相关的 scene prompt（勿加载全部 prompts/）
</thinking>

## Step 1 — 读总纲

读取 [references/core_rules.md](../references/core_rules.md) + [constraint_detail.md](../references/constraint_detail.md)（违规报告引用 `C#.#`）。Prompt 选型 → [skill_structure.md](../references/skill_structure.md)

## Step 2 — 反例对照

| 嫌疑 | 对照 |
|------|------|
| 跨线程 LVGL | [bad_lvgl_cross_thread.c](../examples/bad_lvgl_cross_thread.c) |
| ISR 阻塞 | [bad_isr_blocking.c](../examples/bad_isr_blocking.c) |
| cJSON 泄漏 | [bad_cjson_leak.c](../examples/bad_cjson_leak.c) |
| **Queue 栈指针/cJSON*** | [bad_queue_stack_pointer.c](../examples/bad_queue_stack_pointer.c) |
| WSS 栈/重连 | [bad_wss_blocking.c](../examples/bad_wss_blocking.c) → 正例 [good_wss_reconnect.c](../examples/good_wss_reconnect.c) |

按需深读：[lvgl_thread_safety.txt](../prompts/lvgl_thread_safety.txt)、[memory_ownership.txt](../prompts/memory_ownership.txt)、[deadlock_lock_order.txt](../prompts/deadlock_lock_order.txt)、[memory_alloc_optimize.txt](../prompts/memory_alloc_optimize.txt)（堆/栈/缩池嫌疑）

## Step 3 — 自动化 checker（完整版）

在用户源码目录执行（**仅** `src/` 或用户指定路径，不扫 home / `.env`）：

```bash
python tools/run_review.py --dir ./src --platform <esp32|stm32|jl|bk|freertos>
```

含 `cjson_leak_checker`、`isr_safety_checker`、`lvgl_thread_checker`、**`queue_ownership_checker`（铁律 #2）**。

Python 不可用：标注「待本地补验」，改用手工核对 checklist。

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
