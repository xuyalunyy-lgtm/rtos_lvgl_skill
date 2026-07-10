# Context Route Quality Samples

> 5 core quality samples to verify that the compact default budget does not "save tokens at the cost of missing critical constraints".

## Sample Definitions

### 1. cjson_review_esp32

- **Scenario**: ESP32 project cJSON leak review
- **workflow**: code_review
- **platform**: esp32
- **constraints**: C3, C7
- **compact must cover**:
  - constraint_review.md (C3 cJSON lifecycle)
  - constraint_memory.md (C7 memory allocation)
  - esp32_quick.md (PSRAM/heap differences)
- **Upgrade trigger**: Requires complete cJSON checker rules, detailed ESP32 heap_caps API
- **Quality expectation**: Compact mode should be able to identify cJSON_Parse/Delete pairing issues, goto cleanup templates

### 2. zephyr_crash_log

- **Scenario**: Zephyr device kernel oops diagnosis
- **workflow**: crash_debug
- **platform**: zephyr
- **constraints**: C4, C8, C31
- **compact must cover**:
  - constraint_review.md (C4 ISR safety)
  - constraint_rtos.md (C8 boot sequence, C31 timeout budget)
  - zephyr_quick.md (Zephyr crash localization)
- **Upgrade trigger**: Requires complete Zephyr kernel API, devicetree configuration details
- **Quality expectation**: Compact mode should be able to identify ISR blocking, boot sequence errors, infinite waits

### 3. esp32_memory_pressure

- **Scenario**: ESP32 device heap continuously declining
- **workflow**: memory_analysis
- **platform**: esp32
- **constraints**: C7, C28, C36
- **compact must cover**:
  - constraint_memory.md (C7 memory allocation, C28 DMA, C36 copy budget)
  - esp32_quick.md (PSRAM/heap partitioning)
- **Upgrade trigger**: Requires complete heap_caps API, DMA buffer alignment details
- **Quality expectation**: Compact mode should be able to identify unmatched free calls, PSRAM misuse, DMA cache issues

### 4. ota_rollback_review

- **Scenario**: ESP32 automatic rollback after OTA upgrade
- **workflow**: code_review
- **platform**: esp32
- **constraints**: C9, C22
- **compact must cover**:
  - constraint_ota.md (C9 keys, C22 OTA security)
  - esp32_quick.md (OTA common pitfalls)
- **Upgrade trigger**: Requires complete OTA API, secure boot configuration, partition table details
- **Quality expectation**: Compact mode should be able to identify missing mark_valid, missing signature verification, unclear rollback paths

### 5. media_dma_lifecycle

- **场景**：ESP32 音视频 DMA buffer 生命周期审查
- **workflow**：code_review
- **platform**：esp32
- **constraints**：C25, C28
- **compact 必须覆盖**：
  - constraint_media.md（C25 A/V 管线）
  - constraint_memory.md（C28 DMA/Cache）
  - esp32_quick.md（DMA cache 注意事项）
- **升级触发**：需要完整 DMA API、cache clean/invalidate 细节
- **质量期望**：compact 模式应能识别 DMA buffer 未对齐、cache 未 invalidate、旧帧复用

## 预算目标

| 样例 | compact tokens | 必须覆盖 | 不得默认加载 |
|---|---|---|---|
| cjson_review_esp32 | <15k | review + memory + esp32_quick | constraint_detail, iteration_log |
| zephyr_crash_log | <15k | review + rtos + zephyr_quick | constraint_detail, CHANGELOG_archive |
| esp32_memory_pressure | <12k | memory + esp32_quick | constraint_detail, platform_diff_matrix |
| ota_rollback_review | <12k | ota + esp32_quick | constraint_detail, constraint_graph |
| media_dma_lifecycle | <15k | media + memory + esp32_quick | constraint_detail, full core_rules |
