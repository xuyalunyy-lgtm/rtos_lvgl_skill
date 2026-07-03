# SDK Abstraction Quick Reference

> 轻量 SDK 抽象索引。完整版见 `sdk_abstraction.yaml`。

## 标准操作族

| 族 | 操作 | 用途 |
|---|---|---|
| **Semaphore** | SEM_CREATE, SEM_TAKE, SEM_GIVE, SEM_DELETE | 信号量 |
| **Mutex** | MUTEX_CREATE, MUTEX_LOCK, MUTEX_UNLOCK, MUTEX_DELETE | 互斥锁 |
| **Queue** | QUEUE_CREATE, QUEUE_SEND, QUEUE_RECV, QUEUE_OVERWRITE, QUEUE_DELETE | 队列 |
| **Task** | TASK_CREATE, TASK_DELETE, TASK_DELAY, TASK_NOTIFY_GIVE, TASK_NOTIFY_TAKE | 任务 |
| **Timer** | TIMER_CREATE, TIMER_START, TIMER_STOP, TIMER_DELETE | 定时器 |
| **Critical** | CRITICAL_ENTER, CRITICAL_EXIT, IRQ_DISABLE, IRQ_ENABLE, IRQ_YIELD | 临界区 |
| **Memory** | HEAP_ALLOC, HEAP_FREE, HEAP_ALLOC_DMA, HEAP_ALLOC_EXTERNAL | 内存 |
| **Constants** | TIMEOUT_FOREVER, TIMEOUT_ZERO, MS_TO_TICKS | 常量 |
| **cJSON** | PARSE, DELETE, CREATE, ADD_ITEM | JSON |
| **LVGL** | TIMER_HANDLER, ASYNC_CALL, OBJ_CREATE, OBJ_SET, OBJ_DELETE, DISP_DRV_REG | UI |
| **Network** | SOCKET_RECV, SOCKET_SEND, SOCKET_CONNECT, SOCKET_SET_TIMEOUT | Socket |
| **TLS** | TLS_READ, TLS_WRITE, TLS_HANDSHAKE | TLS |
| **Storage** | NVS_WRITE, NVS_COMMIT, NVS_CLOSE, FLASH_WRITE, FLASH_ERASE | 存储 |
| **OTA** | OTA_BEGIN, OTA_WRITE, OTA_END, OTA_MARK_VALID, OTA_ROLLBACK | OTA |
| **OTA Verify** | OTA_VERIFY, OTA_SECURE_BOOT | OTA 验证 |
| **Cache/DMA** | CACHE_CLEAN, CACHE_INVALIDATE, DMA_BUFFER_SYNC | Cache/DMA |
| **GPIO** | GPIO_CONFIG, GPIO_SET, GPIO_GET, I2C_TRANSFER, SPI_TRANSFER | 外设 |
| **Power** | DEEP_SLEEP, LIGHT_SLEEP, SLEEP_WAKEUP_CAUSE, PERIPHERAL_POWER_DOWN | 电源 |
| **Logging** | LOG_WRITE, PRINTF | 日志 |
| **WiFi** | WIFI_CONNECT, WIFI_DISCONNECT, WIFI_EVENT_REGISTER, WIFI_EVENT_UNREGISTER | WiFi |
| **Watchdog** | WDT_ADD, WDT_RESET, WDT_INIT | 看门狗 |

## 平台 API 映射入口

| 平台 | SDK Map 文件 |
|---|---|
| ESP32 | `platforms/esp32_sdk_map.yaml` |
| Zephyr | `platforms/zephyr_sdk_map.yaml` |
| STM32 | `platforms/stm32_sdk_map.yaml` |
| JL | `platforms/jl_sdk_map.yaml` |
| BK | `platforms/bk_sdk_map.yaml` |

## 使用方式

```python
from sdk_lookup import SdkLookup
lookup = SdkLookup("esp32")  # 或 "zephyr"
apis = lookup.get_apis("SEM_TAKE")  # → ["xSemaphoreTake"]
regex = lookup.build_regex("SEM_TAKE", "MUTEX_LOCK")
```
