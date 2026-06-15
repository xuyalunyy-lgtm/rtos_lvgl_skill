# ESP32 / ESP-IDF 平台专档

Agent 确认目标平台为 ESP32 系列时读取本文件。

## 关键差异速览

| 项目 | ESP-IDF 惯例 | 注意 |
|------|-------------|------|
| 任务优先级 | 数字**越大**越高，常用 `configMAX_PRIORITIES - N` | 与原生 FreeRTOS 文档表述相反 |
| 任务创建 | `xTaskCreate` 或 `xTaskCreatePinnedToCore` | I2S/音频建议绑 Core 1，WiFi 在 Core 0 |
| 堆内存 | `heap_caps_malloc(size, MALLOC_CAP_8BIT)` | DMA 缓冲用 `MALLOC_CAP_DMA \| MALLOC_CAP_INTERNAL` |
| 栈监控 | `uxTaskGetStackHighWaterMark(NULL)` | menuconfig 开 `CONFIG_FREERTOS_CHECK_STACKOVERFLOW_CANARY` |
| WebSocket | `esp_websocket_client` 组件 | 事件回调在 ESP 事件任务，**非** UI 线程 |
| TLS | mbedTLS 内置于 IDF | WSS 任务栈建议 ≥ 6144 bytes（IDF 5.x） |

## 推荐任务优先级（ESP-IDF 风格）

```c
/* 示例：configMAX_PRIORITIES = 25 */
#define AUDIO_TASK_PRIO      (configMAX_PRIORITIES - 1)   /* 24 — 最高 */
#define WSS_TASK_PRIO        (configMAX_PRIORITIES - 3)   /* 22 */
#define LVGL_TASK_PRIO       (configMAX_PRIORITIES - 5)   /* 20 */
#define PRESENTER_TASK_PRIO  (configMAX_PRIORITIES - 7)   /* 18 */
```

输出优先级表时**同时给出相对顺序和 IDF 数值**，避免用户与 STM32 混淆。

## 任务创建模板

```c
/* 音频采集 — 绑 Core 1，避免与 WiFi 抢占 */
xTaskCreatePinnedToCore(
    audio_process_task, "audio",
    4096, NULL,
    AUDIO_TASK_PRIO,
    &s_audio_hdl, 1
);

/* LVGL — 绑 Core 1（与音频同核时需控制刷新频率） */
xTaskCreatePinnedToCore(
    lvgl_task, "lvgl",
    8192, NULL,
    LVGL_TASK_PRIO,
    &s_lvgl_hdl, 1
);
```

## WSS / 网络（Model 层）

```c
#include "esp_websocket_client.h"

/* 事件回调在 esp_event 任务上下文 — 禁止 lv_obj_* */
static void ws_event_handler(void *arg, esp_event_base_t base,
                             int32_t event_id, void *event_data)
{
    esp_websocket_event_data_t *data = (esp_websocket_event_data_t *)event_data;

    switch (event_id) {
    case WEBSOCKET_EVENT_DATA:
        /* 解析后 xQueueSend 给 Presenter，不碰 UI */
        break;
    case WEBSOCKET_EVENT_DISCONNECTED:
        net_emit_event(NET_EVT_ERROR, NULL, 0);
        break;
    default:
        break;
    }
}
```

- `esp_websocket_client` 内部处理 TLS，无需手动调 mbedTLS，但栈开销仍大。
- 接收缓冲建议放 PSRAM（若硬件支持）：`heap_caps_malloc(len, MALLOC_CAP_SPIRAM)`.

## LVGL 集成（ESP-IDF）

- 官方 port：`esp_lvgl_port` 或 `lvgl_esp32_drivers`
- `lv_timer_handler()` 必须在专用 `lvgl_task` 中循环调用
- 跨任务刷新：优先 `lv_async_call()`；若用互斥锁，与 `esp_lvgl_port_lock()` 封装保持一致
- **禁止**在 `ws_event_handler` 或 `esp_http_client` 回调中直接 `lv_label_set_text`

## I2S / DMA 音频

```c
#include "driver/i2s_std.h"

/* IDF 5.x 新 I2S API — DMA 缓冲在 i2s_channel_enable 时配置 */
i2s_chan_config_t chan_cfg = I2S_CHANNEL_DEFAULT_CONFIG(I2S_NUM_0, I2S_ROLE_MASTER);
i2s_std_config_t std_cfg  = /* ... */;

i2s_new_channel(&chan_cfg, &tx_handle, &rx_handle);
i2s_channel_init_std_mode(rx_handle, &std_cfg);

/* 回调注册在 i2s_event_callbacks_t — ISR 上下文，仅 FromISR API */
```

- Mic 采集任务建议 `configMAX_PRIORITIES - 1`，高于 LVGL。
- DMA 缓冲：`heap_caps_malloc(size, MALLOC_CAP_DMA | MALLOC_CAP_INTERNAL)`。

## FreeRTOS 配置（sdkconfig 关键项）

```
CONFIG_FREERTOS_HZ=1000
CONFIG_FREERTOS_CHECK_STACKOVERFLOW_CANARY=y
CONFIG_ESP_MAIN_TASK_STACK_SIZE=3584
CONFIG_ESP_SYSTEM_EVENT_TASK_STACK_SIZE=4096
```

## 常见 Crash 定位

| 现象 | ESP32 特有原因 |
|------|---------------|
| `Guru Meditation Error: Core panic` | 跨核竞态、ISR 阻塞、栈溢出 |
| `TLSF allocator` 报错 | DMA 缓冲未用 `MALLOC_CAP_DMA` |
| WiFi + LVGL 卡死 | LVGL 与 WiFi 同核高负载，需绑核或降刷新率 |
| `esp_websocket` 握手失败 | 系统时间未同步（SNTP），证书校验失败 |

## SDK 深度裁剪（ESP-IDF）

> **以下仅为候选项**，须在产品需求问卷确认「不需要」后再关闭；禁止未询问用户直接套用。

### 配置入口

```bash
idf.py menuconfig
```

### 优先关闭项（按产品闭包删）

| 类别 | menuconfig 路径 | 未用时关闭 |
|------|----------------|-----------|
| 蓝牙 | Component config → Bluetooth | `CONFIG_BT_ENABLED=n` |
| 经典 BT/BLE | Bluetooth → ... | 全关 |
| OTA | Component config → App update | 无 OTA 则关 |
| HTTP Server | Component config → HTTP Server | 无本地配网页则关 |
| mDNS | Component config → mDNS | 无局域网发现则关 |
| 多余 log | Component config → Log | 设 `CONFIG_LOG_DEFAULT_LEVEL_WARN` |
| TLS cipher | mbedTLS → TLS Key Exchange Methods | 仅留 ECDHE-RSA + AES-GCM |
| LVGL | Component config → LVGL | 关 demo、缩 `CONFIG_LV_MEM_SIZE` |
| WiFi | 保留 STA，关 AP/SoftAP（若不用） | |
| 分区 | Partition Table | 自定义 `partitions.csv` 缩 app/缩小 spiffs |

### 组件 / 源码裁剪

```
main/CMakeLists.txt    → 移除未用 src 和 REQUIRES 组件
components/            → 删自建未用组件
managed_components/    → idf.py 不加多余依赖
```

### ESP-IDF 裁剪验证

```bash
idf.py size              # Flash/RAM 组件占比
idf.py size-components  # 逐项对比
```

记录 `idf.py size` 裁剪前后对比；堆峰值用 `heap_caps_get_minimum_free_size()` 观测。

## 文件归属惯例（ESP-IDF 工程）

```
main/
├── app_main.c              # 入口，创建任务
├── network_wss_task.c      # Model — WSS
├── app_presenter.c         # Presenter
├── ui_view_manager.c       # View — LVGL
└── audio_capture.c         # Model — I2S DMA
components/
└── my_board/               # 板级驱动
```
