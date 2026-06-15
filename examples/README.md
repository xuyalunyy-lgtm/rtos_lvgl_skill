# Examples 索引（铁律 ↔ 约束 ID ↔ Checker）

L2 Code Review 时按嫌疑加载对应文件；违规报告引用 `C#.#`（见 [constraint_detail.md](../references/constraint_detail.md)）。

## C1 — LVGL 线程安全

| | 文件 | ID | Checker |
|---|------|-----|---------|
| ❌ | [bad_lvgl_cross_thread.c](bad_lvgl_cross_thread.c) | C1.1 | `lvgl_thread_checker.py` |
| ✅ | [good_mvp_pattern.c](good_mvp_pattern.c) `lv_async_call` | C1.2, C1.3 | 同上 |
| ✅ | [good_presenter_consumer.c](good_presenter_consumer.c) `view_post_set_text` | C1.2 | 同上 |

## C2 — Queue payload 所有权

| | 文件 | ID | Checker |
|---|------|-----|---------|
| ❌ | [bad_queue_stack_pointer.c](bad_queue_stack_pointer.c) | C2.1, C2.2 | **`queue_ownership_checker.py`** |
| ✅ | [good_wss_json_parse.c](good_wss_json_parse.c) heap payload | C2.3, C2.4 | 同上 |
| ✅ | [good_presenter_consumer.c](good_presenter_consumer.c) Presenter `vPortFree` | C2.3 | 同上 |

## C3 — cJSON 防泄漏

| | 文件 | ID | Checker |
|---|------|-----|---------|
| ❌ | [bad_cjson_leak.c](bad_cjson_leak.c) | C3.1, C3.2 | `cjson_leak_checker.py` |
| ✅ | [good_wss_json_parse.c](good_wss_json_parse.c) `parse_message_text` | C3.1, C3.3 | 同上 |

## WSS / mbedTLS（栈、SNTP、重连）

| | 文件 | ID | Checker |
|---|------|-----|---------|
| ❌ | [bad_wss_blocking.c](bad_wss_blocking.c) | C1.5 | `stack_calculator.py` + 人工 |
| ✅ | [good_wss_reconnect.c](good_wss_reconnect.c) 指数退避 + SNTP 前置 | — | 人工 + `queue_ownership_checker.py` |
| ✅ | [good_wss_json_parse.c](good_wss_json_parse.c) 解析闭环 | C3.3 | 同上 |

## C4 — ISR / DMA

| | 文件 | ID | Checker |
|---|------|-----|---------|
| ❌ | [bad_isr_blocking.c](bad_isr_blocking.c) | C4.1, C4.3 | `isr_safety_checker.py` |

## MVP 分层闭环

| | 文件 |
|---|------|
| ✅ View + Presenter + 按钮 | [good_mvp_pattern.c](good_mvp_pattern.c) |
| ✅ Model → Queue → Presenter | [good_wss_json_parse.c](good_wss_json_parse.c) + [good_presenter_consumer.c](good_presenter_consumer.c) |
| 共享类型 | [app_mvp.h](app_mvp.h) |

## 一键验证（仓库根目录）

```bash
# checker fixtures 自测
python tools/run_review.py --self-test

# 铁律 C1–C4 范例 good/bad 约束
python tools/run_review.py --validate-examples

# 审查用户源码（含 queue 所有权）
python tools/run_review.py --dir ./src --platform jl
```

`--validate-examples` 期望：**所有 `good_*.c` 通过**，**`bad_*` 反例触发对应 checker 失败**。
