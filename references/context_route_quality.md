# Context Route Quality Samples

> 5 条核心质量样例，验证 compact 默认预算没有"省 token 省到漏关键约束"。

## 样例定义

### 1. cjson_review_esp32

- **场景**：ESP32 项目 cJSON 泄漏审查
- **workflow**：code_review
- **platform**：esp32
- **constraints**：C3, C7
- **compact 必须覆盖**：
  - constraint_review.md（C3 cJSON 生命周期）
  - constraint_memory.md（C7 内存分配）
  - esp32_quick.md（PSRAM/heap 差异）
- **升级触发**：需要完整 cJSON checker 规则、ESP32 heap_caps 详细 API
- **质量期望**：compact 模式应能识别 cJSON_Parse/Delete 配对问题、goto cleanup 模板

### 2. zephyr_crash_log

- **场景**：Zephyr 设备 kernel oops 诊断
- **workflow**：crash_debug
- **platform**：zephyr
- **constraints**：C4, C8, C31
- **compact 必须覆盖**：
  - constraint_review.md（C4 ISR 安全）
  - constraint_rtos.md（C8 启动顺序、C31 超时预算）
  - zephyr_quick.md（Zephyr crash 定位）
- **升级触发**：需要完整 Zephyr kernel API、devicetree 配置细节
- **质量期望**：compact 模式应能识别 ISR 阻塞、启动顺序错误、永久等待

### 3. esp32_memory_pressure

- **场景**：ESP32 设备堆持续下降
- **workflow**：memory_analysis
- **platform**：esp32
- **constraints**：C7, C28, C36
- **compact 必须覆盖**：
  - constraint_memory.md（C7 内存分配、C28 DMA、C36 拷贝预算）
  - esp32_quick.md（PSRAM/heap 分区）
- **升级触发**：需要完整 heap_caps API、DMA buffer 对齐细节
- **质量期望**：compact 模式应能识别未配对 free、PSRAM 误用、DMA cache 问题

### 4. ota_rollback_review

- **场景**：ESP32 OTA 升级后自动回滚
- **workflow**：code_review
- **platform**：esp32
- **constraints**：C9, C22
- **compact 必须覆盖**：
  - constraint_ota.md（C9 密钥、C22 OTA 安全）
  - esp32_quick.md（OTA 常见踩坑）
- **升级触发**：需要完整 OTA API、secure boot 配置、分区表细节
- **质量期望**：compact 模式应能识别未 mark_valid、签名验证缺失、回滚路径不清

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
