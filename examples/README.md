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

## C26 — 编解码 / 媒体格式一致性

| | 文件 | ID | Checker |
|---|------|-----|---------|
| ❌ | [bad_media_format_mismatch.c](bad_media_format_mismatch.c) | C26.1–C26.6 | `media_format_checker.py` |
| ✅ | [good_media_format_contract.c](good_media_format_contract.c) sample rate/frame/stride/codec lifecycle | C26.1–C26.6 | `media_format_checker.py` |

深细节 → [av_codec_format.txt](../prompts/av_codec_format.txt)

## C27 — 音视频时钟漂移 / Jitter Buffer

| | 文件 | ID | Checker |
|---|------|-----|---------|
| ❌ | [bad_av_clock_jitter.c](bad_av_clock_jitter.c) | C27.1–C27.6 | `av_clock_jitter_checker.py` |
| ✅ | [good_av_clock_jitter.c](good_av_clock_jitter.c) audio clock master + jitter watermarks + drift clamp | C27.1–C27.6 | `av_clock_jitter_checker.py` |

深细节 → [av_clock_jitter.txt](../prompts/av_clock_jitter.txt)

## C28 — 媒体 DMA/cache/零拷贝 buffer 生命周期

| | 文件 | ID | Checker |
|---|------|-----|---------|
| ❌ | [bad_av_dma_buffer_lifecycle.c](bad_av_dma_buffer_lifecycle.c) | C28.1–C28.6 | `av_dma_buffer_checker.py` |
| ✅ | [good_av_dma_buffer_lifecycle.c](good_av_dma_buffer_lifecycle.c) DMA-capable pool + cache sync + owner lifecycle | C28.1–C28.6 | `av_dma_buffer_checker.py` |

深细节 → [av_dma_buffer_lifecycle.txt](../prompts/av_dma_buffer_lifecycle.txt)

## C29 - Module Boundary / High Cohesion, Low Coupling

| | 文件 | ID | Checker |
|---|------|-----|---------|
| ✅ | [good_module_boundary.c](good_module_boundary.c) + [good_module_boundary.h](good_module_boundary.h) | C29.6-C29.10 | `module_boundary_checker.py` |
| ❌ | [bad_god_module.c](bad_god_module.c) | C29.6, C29.9 | `module_boundary_checker.py` |
| ❌ | [bad_cross_layer_dependency.c](bad_cross_layer_dependency.c) | C29.7, C29.8 | `module_boundary_checker.py` |

细节 → [runtime_efficiency_contracts.txt](../prompts/runtime_efficiency_contracts.txt)

## C31 — 超时预算

| | 文件 | ID | Checker |
|---|------|-----|---------|
| ❌ | [bad_timeout_budget.c](../tools/fixtures/bad_timeout_budget.c) | C31.1, C31.2, C31.3 | `blocking_wait_checker.py` |
| ✅ | [good_timeout_budget.c](../tools/fixtures/good_timeout_budget.c) 有限 timeout + socket deadline + 返回值处理 | C31.1–C31.3 | `blocking_wait_checker.py` |

深细节 → [runtime_efficiency_contracts.txt](../prompts/runtime_efficiency_contracts.txt)

## C36/C37 — 数据拷贝预算 / 背压与降级

| | 文件 | ID | Checker |
|---|------|-----|---------|
| ❌ | [bad_efficiency_budget.c](../tools/fixtures/bad_efficiency_budget.c) | C36.2, C36.5, C37.2, C37.4 | `efficiency_budget_checker.py` |
| ✅ | [good_efficiency_budget.c](../tools/fixtures/good_efficiency_budget.c) descriptor 入队 + 有限 timeout + drop 计数 | C36.2, C36.3, C37.2 | `efficiency_budget_checker.py` |

深细节 → [runtime_efficiency_contracts.txt](../prompts/runtime_efficiency_contracts.txt)

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
| ✅ | [good_checked_return.c](good_checked_return.c) 返回值检查 + goto cleanup + malloc fallback | C12.1–C12.4 | `return_check_checker.py` |

深细节 → [error_handling.txt](../prompts/error_handling.txt)

## C14 — 日志规范

| | 文件 | ID | Checker |
|---|------|-----|---------|
| ❌ | [bad_isr_printf.c](bad_isr_printf.c) | C14.1, C14.3, C14.4 | `logging_checker.py` |
| ✅ | [good_logging.c](good_logging.c) LOG_* 宏 + TAG + 脱敏 + 限频 | C14.1, C14.4, C14.6 | `logging_checker.py` |

深细节 → [logging_debug.txt](../prompts/logging_debug.txt)

## C18 — 外设驱动安全

| | 文件 | ID | Checker |
|---|------|-----|---------|
| ❌ | [bad_gpio_no_config.c](bad_gpio_no_config.c) | C18.1, C18.2, C18.4 | `peripheral_driver_checker.py` |
| ✅ | [good_gpio_config.c](good_gpio_config.c) GPIO 方向配置 + I2C 地址文档 | C18.1, C18.2 | `peripheral_driver_checker.py` |

深细节 → [peripheral_driver_safety.txt](../prompts/peripheral_driver_safety.txt)

## C19 — Flash/NVS 安全

| | 文件 | ID | Checker |
|---|------|-----|---------|
| ❌ | [bad_nvs_no_commit.c](bad_nvs_no_commit.c) | C19.1, C21.1 | `flash_nvs_checker.py` |
| ✅ | [good_nvs_commit.c](good_nvs_commit.c) NVS commit + 返回值检查 | C19.1 | `flash_nvs_checker.py` |

深细节 → [flash_nvs_safety.txt](../prompts/flash_nvs_safety.txt)

## C20 — 网络韧性

| | 文件 | ID | Checker |
|---|------|-----|---------|
| ❌ | [bad_reconnect_no_backoff.c](bad_reconnect_no_backoff.c) | C20.1, C20.2 | `network_resilience_checker.py` |
| ✅ | [good_reconnect_backoff.c](good_reconnect_backoff.c) 指数退避 + 超时 + DNS fallback | C20.1–C20.3 | `network_resilience_checker.py` |

深细节 → [network_resilience.txt](../prompts/network_resilience.txt)

## C21 — 低功耗管理

| | 文件 | ID | Checker |
|---|------|-----|---------|
| ❌ | [bad_sleep_no_save.c](bad_sleep_no_save.c) | C21.1, C21.2, C21.4 | `low_power_checker.py` |
| ✅ | [good_sleep_save.c](good_sleep_save.c) 状态保存 + 外设断电 + 唤醒恢复 | C21.1, C21.4 | `low_power_checker.py` |

深细节 → [low_power_management.txt](../prompts/low_power_management.txt)

## C22 — OTA / 固件升级安全

| | 文件 | ID | Checker |
|---|------|-----|---------|
| ❌ | [bad_ota_no_rollback.c](bad_ota_no_rollback.c) | C22.1, C22.2, C22.4, C22.5 | `ota_safety_checker.py` |
| ✅ | [good_ota_update.c](good_ota_update.c) 签名验证 + 回滚 + 超时 + 断电恢复 | C22.1–C22.5 | `ota_safety_checker.py` |

深细节 → [ota_update_safety.txt](../prompts/ota_update_safety.txt)

## C23 — 显示驱动安全

| | 文件 | ID | Checker |
|---|------|-----|---------|
| ❌ | [bad_display_no_init.c](bad_display_no_init.c) | C23.1, C23.5, C23.6 | `display_driver_checker.py` |
| ✅ | [good_display_init.c](good_display_init.c) LCD 时序 + 帧缓冲检查 + lv_disp_drv 完整注册 | C23.1, C23.5, C23.6 | `display_driver_checker.py` |

深细节 → [lcd_display_driver.txt](../prompts/lcd_display_driver.txt)

## C43 — 锁预算与优先级反转防护

| | 文件 | ID | Checker |
|---|------|-----|---------|
| ✅ | [good_lock_budget.c](../tools/fixtures/good_lock_budget.c) | C43.1, C43.4, C43.5 | `lock_budget_checker.py` |
| ❌ | [bad_lock_budget.c](../tools/fixtures/bad_lock_budget.c) | C43.1, C43.2, C43.3, C43.4, C43.5 | `lock_budget_checker.py` |

深细节 → [runtime_efficiency_contracts.txt](../prompts/runtime_efficiency_contracts.txt)

## C44 — 临界区/关中断预算

| | 文件 | ID | Checker |
|---|------|-----|---------|
| ✅ | [good_critical_section.c](../tools/fixtures/good_critical_section.c) | C44.1, C44.3 | `critical_section_checker.py` |
| ❌ | [bad_critical_section.c](../tools/fixtures/bad_critical_section.c) | C44.1, C44.2, C44.3, C44.4, C44.5 | `critical_section_checker.py` |

深细节 → [runtime_efficiency_contracts.txt](../prompts/runtime_efficiency_contracts.txt)

## C45 — 传感器集成契约

| | 文件 | ID | Checker |
|---|------|-----|---------|
| ✅ | [good_sensor_integration.c](../tools/fixtures/good_sensor_integration.c) | C45.1, C45.2, C45.3, C45.4, C45.5 | `sensor_integration_checker.py` |
| ❌ | [bad_sensor_integration.c](../tools/fixtures/bad_sensor_integration.c) | C45.1, C45.2, C45.3, C45.4, C45.5 | `sensor_integration_checker.py` |

深细节 → [runtime_efficiency_contracts.txt](../prompts/runtime_efficiency_contracts.txt)

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

# 铁律 C1–C4 + C10 + C22 + C25 + C26 + C27 + C28 + C31 + C36/C37 + C43 + C44 + C45 范例 good/bad 约束
python tools/run_review.py --validate-examples

# 审查用户源码（含 queue 所有权）
python tools/run_review.py --dir ./src --platform jl
```

`--validate-examples` 期望：**所有 `good_*.c` 通过**，**`bad_*` 反例触发对应 checker 失败**。
