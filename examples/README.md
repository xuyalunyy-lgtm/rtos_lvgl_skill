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

Cache 一致性细则 → [audio_dma_pingpong.txt](../prompts/audio_dma_pingpong.txt) **C4.8**

## C10 — 语音 / ASR / Uplink（共享引擎）

| | 文件 | ID | Checker |
|---|------|-----|---------|
| ❌ | [bad_prompt_no_detach.c](bad_prompt_no_detach.c) | C10.1, C10.2, C10.5 | `voice_sequence_checker.py` |
| ✅ | [good_voice_prompt_uplink.c](good_voice_prompt_uplink.c) detach + settle + session generation | C10.1–C10.6 | `voice_sequence_checker.py` |

深细节 → [voice_asr_uplink.txt](../prompts/voice_asr_uplink.txt)

## C25 — 音视频管线 / A/V Sync

| | 文件 | ID | Checker |
|---|------|-----|---------|
| ❌ | [bad_av_pipeline_blocking.c](bad_av_pipeline_blocking.c) | C25.1–C25.5 | `av_pipeline_checker.py` |
| ✅ | [good_av_pipeline_sync.c](good_av_pipeline_sync.c) audio clock master + PTS/seq + bounded queue | C25.1–C25.6 | `av_pipeline_checker.py` |

深细节 → [av_pipeline_sync.txt](../prompts/av_pipeline_sync.txt)

## C8 — 启动 / WDT / 阻塞

| | 文件 | ID | Checker |
|---|------|-----|---------|
| ❌ | [bad_wss_blocking.c](bad_wss_blocking.c) | C8.2, C8.4, C8.6, C7.5 | 人工 |
| ✅ | [good_boot_sequence.c](good_boot_sequence.c) | C8.1, C8.6 | 人工 |
| ✅ | [good_wss_reconnect.c](good_wss_reconnect.c) | C8.5, C7.9, C8.2 | 人工 |

## C12 — 错误处理

| | 文件 | ID | Checker |
|---|------|-----|---------|
| ❌ | [bad_unchecked_return.c](bad_unchecked_return.c) | C12.1, C12.2, C12.4, C12.5 | `return_check_checker.py` |

深细节 → [error_handling.txt](../prompts/error_handling.txt)

## C14 — 日志规范

| | 文件 | ID | Checker |
|---|------|-----|---------|
| ❌ | [bad_isr_printf.c](bad_isr_printf.c) | C14.1, C14.3, C14.4 | `logging_checker.py` |

深细节 → [logging_debug.txt](../prompts/logging_debug.txt)

## C18 — 外设驱动安全

| | 文件 | ID | Checker |
|---|------|-----|---------|
| ❌ | [bad_gpio_no_config.c](bad_gpio_no_config.c) | C18.1, C18.2, C18.4 | `peripheral_driver_checker.py` |

深细节 → [peripheral_driver_safety.txt](../prompts/peripheral_driver_safety.txt)

## C19 — Flash/NVS 安全

| | 文件 | ID | Checker |
|---|------|-----|---------|
| ❌ | [bad_nvs_no_commit.c](bad_nvs_no_commit.c) | C19.1, C21.1 | `flash_nvs_checker.py` |

深细节 → [flash_nvs_safety.txt](../prompts/flash_nvs_safety.txt)

## C20 — 网络韧性

| | 文件 | ID | Checker |
|---|------|-----|---------|
| ❌ | [bad_reconnect_no_backoff.c](bad_reconnect_no_backoff.c) | C20.1, C20.2 | `network_resilience_checker.py` |

深细节 → [network_resilience.txt](../prompts/network_resilience.txt)

## C21 — 低功耗管理

| | 文件 | ID | Checker |
|---|------|-----|---------|
| ❌ | [bad_sleep_no_save.c](bad_sleep_no_save.c) | C21.1, C21.2, C21.4 | `low_power_checker.py` |

深细节 → [low_power_management.txt](../prompts/low_power_management.txt)

## C23 — 显示驱动安全

| | 文件 | ID | Checker |
|---|------|-----|---------|
| ❌ | [bad_display_no_init.c](bad_display_no_init.c) | C23.1, C23.5, C23.6 | `display_driver_checker.py` |

深细节 → [lcd_display_driver.txt](../prompts/lcd_display_driver.txt)

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

# 铁律 C1–C4 + C10 + C25 范例 good/bad 约束
python tools/run_review.py --validate-examples

# 审查用户源码（含 queue 所有权）
python tools/run_review.py --dir ./src --platform jl
```

`--validate-examples` 期望：**所有 `good_*.c` 通过**，**`bad_*` 反例触发对应 checker 失败**。
