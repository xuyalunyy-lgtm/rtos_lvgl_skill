# Core Rules Quick Reference

> Lightweight core rules. See `core_rules.md` for the full version.

## Iron Rules (MUST comply)

1. **RTOS Constraints Take Priority**: C1-C48 constraints MUST take priority over any SDK example
2. **Lifecycle Symmetry**: init MUST have deinit, create MUST have delete
3. **ISR Safety**: ISR MUST NOT block, malloc, printf, or cJSON_Parse
4. **Queue Ownership Transfer**: After xQueueSend, MUST NOT access the payload
5. **Finite Timeout**: MUST NOT use portMAX_DELAY as the default timeout
6. **Return Value Check**: xTaskCreate/pvPortMalloc/xQueueCreate MUST check the return value
7. **Log Sanitization**: Password/token/key MUST NOT be printed in plaintext
8. **Startup Sequence**: Peripheral initialization MUST occur before task creation

## Platform Differences Quick Reference

| Concept | ESP32 | Zephyr |
|---|---|---|
| Task Creation | xTaskCreate | k_thread_create |
| Queue | xQueueCreate | K_MSGQ_DEFINE |
| Semaphore | xSemaphoreCreateBinary | K_SEM_DEFINE |
| Mutex | xSemaphoreCreateMutex | K_MUTEX_DEFINE |
| Delay | vTaskDelay(pdMS_TO_TICKS) | k_msleep |
| Infinite Wait | portMAX_DELAY | K_FOREVER |
| Logging | ESP_LOGI(TAG, ...) | LOG_INF(...) |
| Heap Allocation | heap_caps_malloc | k_malloc |

## Constraint Shards Quick Reference

| Shard | Included Constraints | Scenario |
|---|---|---|
| review | C1-C6, C11-C16 | Code Review |
| memory | C7, C28, C36 | Memory Analysis |
| rtos | C8, C15, C17, C29-C35, C43-C44 | RTOS Runtime |
| platform | C18-C21, C23, C42, C45 | Platform-Specific |
| media | C25-C27 | Audio/Video |
| ota | C9, C22, C24 | OTA/Keys |
| recover | C37-C41 | Fault Recovery |
