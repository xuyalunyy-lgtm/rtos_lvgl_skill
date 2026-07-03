# Core Rules Quick Reference

> 轻量核心规则。完整版见 `core_rules.md`。

## 铁律（必须遵守）

1. **RTOS 约束优先**：C1-C45 约束优先于任何 SDK 示例
2. **生命周期对称**：init 必须有 deinit，create 必须有 delete
3. **ISR 安全**：ISR 中禁止阻塞、malloc、printf、cJSON_Parse
4. **队列所有权转移**：xQueueSend 后禁止访问 payload
5. **超时有限**：禁止 portMAX_DELAY 作为默认超时
6. **返回值检查**：xTaskCreate/pvPortMalloc/xQueueCreate 必须检查返回值
7. **日志脱敏**：密码/token/key 禁止明文打印
8. **启动顺序**：外设初始化必须在任务创建之前

## 平台差异速查

| 概念 | ESP32 | Zephyr |
|---|---|---|
| 任务创建 | xTaskCreate | k_thread_create |
| 队列 | xQueueCreate | K_MSGQ_DEFINE |
| 信号量 | xSemaphoreCreateBinary | K_SEM_DEFINE |
| 互斥锁 | xSemaphoreCreateMutex | K_MUTEX_DEFINE |
| 延时 | vTaskDelay(pdMS_TO_TICKS) | k_msleep |
| 永久等待 | portMAX_DELAY | K_FOREVER |
| 日志 | ESP_LOGI(TAG, ...) | LOG_INF(...) |
| 堆分配 | heap_caps_malloc | k_malloc |

## 约束分片速查

| 分片 | 包含约束 | 场景 |
|---|---|---|
| review | C1-C6, C11-C16 | 代码审查 |
| memory | C7, C28, C36 | 内存分析 |
| rtos | C8, C15, C17, C29-C35, C43-C44 | RTOS 运行时 |
| platform | C18-C21, C23, C42, C45 | 平台相关 |
| media | C25-C27 | 音视频 |
| ota | C9, C22, C24 | OTA/密钥 |
| recover | C37-C41 | 故障恢复 |
