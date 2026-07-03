# ESP32 Quick Reference

> 轻量 ESP32 平台速查。完整版见 `esp32.md`。

## 关键差异

- **双核**：Core 0 (WiFi/BT) + Core 1 (用户任务)，用 `xTaskCreatePinnedToCore` 绑核
- **PSRAM**：`heap_caps_malloc(sz, MALLOC_CAP_SPIRAM)` 优先外部 RAM
- **DMA**：`heap_caps_malloc(sz, MALLOC_CAP_DMA)` 必须 cache line 对齐
- **Task WDT**：默认 5s，用 `esp_task_wdt_add()` 注册，`esp_task_wdt_reset()` 喂狗
- **NVS**：写入后必须 `nvs_commit()`，返回值必须检查

## 常用 API 对照

| 操作 | ESP-IDF API |
|---|---|
| 任务创建 | `xTaskCreatePinnedToCore(fn, name, stack, param, prio, &hdl, core)` |
| 队列 | `xQueueCreate(len, item_sz)` |
| 信号量 | `xSemaphoreCreateBinary()` / `xSemaphoreCreateMutex()` |
| 延时 | `vTaskDelay(pdMS_TO_TICKS(ms))` |
| 堆分配 | `heap_caps_malloc(sz, MALLOC_CAP_8BIT)` |
| 日志 | `ESP_LOGI(TAG, "fmt", ...)` |
| WiFi | `esp_wifi_connect()` / `esp_event_handler_register()` |
| OTA | `esp_ota_begin()` / `esp_ota_write()` / `esp_ota_end()` |

## 高频踩坑

1. **ISR 中调用非 FromISR API** → 用 `xSemaphoreGiveFromISR` / `xQueueSendFromISR`
2. **PSRAM 分配未检查返回值** → PSRAM 可能不可用，必须检查 NULL
3. **NVS 写入未 commit** → 断电后数据丢失
4. **OTA 未 mark_valid** → 重启后自动回滚
5. **WiFi 重连无退避** → 用指数退避，避免风暴

## Crash 定位

```bash
# addr2line
xtensa-esp32-elf-addr2line -pfiaC -e build/firmware.elf 0x400xxxxx
```
