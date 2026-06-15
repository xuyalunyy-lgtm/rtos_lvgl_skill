# Examples 索引（铁律 ↔ 范例 ↔ Checker）

L2 Code Review 时按嫌疑加载对应文件；完整版可运行 checker 验证。

## 铁律 #1 — LVGL 线程安全

| | 文件 | Checker |
|---|------|---------|
| ❌ | [bad_lvgl_cross_thread.c](bad_lvgl_cross_thread.c) | `lvgl_thread_checker.py` |
| ✅ | [good_presenter_consumer.c](good_presenter_consumer.c) `view_post_set_text` | 同上（View 允许） |

## 铁律 #2 — Queue payload 所有权

| | 文件 | Checker |
|---|------|---------|
| ❌ | [bad_queue_stack_pointer.c](bad_queue_stack_pointer.c) | **`queue_ownership_checker.py`** |
| ✅ | [good_wss_json_parse.c](good_wss_json_parse.c) heap payload | 同上 |
| ✅ | [good_presenter_consumer.c](good_presenter_consumer.c) Presenter `vPortFree` | 同上 |

## 铁律 #3 — cJSON 防泄漏

| | 文件 | Checker |
|---|------|---------|
| ❌ | [bad_cjson_leak.c](bad_cjson_leak.c) | `cjson_leak_checker.py` |
| ✅ | [good_wss_json_parse.c](good_wss_json_parse.c) `parse_message_text` | 同上 |

## WSS / mbedTLS（栈、SNTP、重连）

| | 文件 | Checker |
|---|------|---------|
| ❌ | [bad_wss_blocking.c](bad_wss_blocking.c) | `stack_calculator.py` + 人工 |
| ✅ | [good_wss_reconnect.c](good_wss_reconnect.c) 指数退避 + SNTP 前置 | 人工 + `queue_ownership_checker.py` |
| ✅ | [good_wss_json_parse.c](good_wss_json_parse.c) 解析闭环 | 同上 |

## ISR / DMA（铁律 #4）

| | 文件 | Checker |
|---|------|---------|
| ❌ | [bad_isr_blocking.c](bad_isr_blocking.c) | `isr_safety_checker.py` |

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

# 铁律 #2 + 范例 good/bad 约束
python tools/run_review.py --validate-examples

# 审查用户源码（含 queue 所有权）
python tools/run_review.py --dir ./src --platform jl
```

`--validate-examples` 期望：**所有 `good_*.c` 通过**，**`bad_queue_stack_pointer.c` 等反例触发对应 checker 失败**。
