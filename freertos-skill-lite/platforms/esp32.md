# ESP32 / ESP-IDF 平台专档

Agent 确认目标平台为 ESP32 系列时读取本文件。

**基线：** ESP-IDF v5.x（v5.1+ 为主流）。v4.x 差异见文末。

---

## 目录

- [关键差异速览](#关键差异速览)
- [芯片差异表](#芯片差异表)
- [双核架构与绑核策略](#双核架构与绑核策略)
- [推荐任务优先级](#推荐任务优先级)
- [任务创建模板](#任务创建模板)
- [WSS / 网络（Model 层）](#wss--网络model-层)
- [LVGL 集成](#lvgl-集成esp-idf)
- [I2S / DMA 音频](#i2s--dma-音频)
- [PSRAM / 堆管理 / DMA 缓冲](#psram--堆管理--dma-缓冲)
- [看门狗配置详解](#看门狗配置详解)
- [NVS 状态持久化](#nvs-状态持久化)
- [WiFi 配网流程](#wifi-配网流程)
- [安全启动 / Flash 加密 / OTA 安全](#安全启动--flash-加密--ota-安全)
- [FreeRTOS 配置](#freertos-配置sdkconfig-关键项)
- [SDK 深度裁剪](#sdk-深度裁剪esp-idf)
- [文件归属惯例](#文件归属惯例esp-idf-工程)
- [编译与产物](#编译与产物)
- [Crash 定位（addr2line）](#crash-定位addr2line)
- [MVP 集成要点](#mvp-集成要点esp-idf-特有)
- [共享引擎：prompt + 云端 uplink（C10）](#共享引擎prompt--云端-uplinkc10)
- [快速参考路径](#快速参考路径)

---

## 关键差异速览

| 项目 | ESP-IDF 惯例 | 注意 |
|------|-------------|------|
| 任务优先级 | 数字**越大**越高，常用 `configMAX_PRIORITIES - N` | 与原生 FreeRTOS 文档表述相反 |
| 任务创建 | `xTaskCreate` 或 `xTaskCreatePinnedToCore` | I2S/音频建议绑 Core 1，WiFi 在 Core 0 |
| 堆内存 | `heap_caps_malloc(size, MALLOC_CAP_8BIT)` | DMA 缓冲用 `MALLOC_CAP_DMA \| MALLOC_CAP_INTERNAL` |
| 栈监控 | `uxTaskGetStackHighWaterMark(NULL)` | menuconfig 开 `CONFIG_FREERTOS_CHECK_STACKOVERFLOW_CANARY` |
| WebSocket | `esp_websocket_client` 组件 | 事件回调在 ESP 事件任务，**非** UI 线程 |
| TLS | mbedTLS 内置于 IDF | WSS 任务栈建议 ≥ 6144 bytes（IDF 5.x） |
| 看门狗 | Task WDT 默认监控 `esp_timer` + `main` | 禁止在受监控任务中长时间阻塞 |

---

## 芯片差异表

| 芯片 | CPU | PSRAM | Flash | WiFi | BLE | DMA | 适用场景 |
|------|-----|-------|-------|------|-----|-----|----------|
| **ESP32** | 双核 Xtensa 240MHz | 外挂 4MB SPIRAM | 4-16MB | WiFi 4 | BLE 4.2 | I2S 0/1 | 通用 IoT、带屏 |
| **ESP32-S3** | 双核 Xtensa 240MHz | 内置/外挂 8MB OCT | 8-16MB | WiFi 4 | BLE 5.0 | I2S 0/1 + LCD/Camera | AI 语音、带屏摄像头 |
| **ESP32-C6** | 单核 RISC-V 160MHz | 无 | 4-8MB | WiFi 6 | BLE 5.2 | I2S | 低功耗 IoT、模组 |
| **ESP32-H2** | 单核 RISC-V 96MHz | 无 | 4MB | 无 | BLE 5.3 / Thread | 无 | Zigbee/Thread 子设备 |

**选型注意：**
- 需要 PSRAM 的产品（LVGL 帧缓冲、大 JSON 解析）选 ESP32 或 ESP32-S3
- 双核绑核策略仅 ESP32/S3 适用；C6/H2 单核无需绑核
- ESP32-S3 的 USB Serial/JTAG 可用于 OTA，无需额外 USB 芯片

---

## 双核架构与绑核策略

### 架构

```
Core 0 (PRO_CPU)     — WiFi/LwIP、BT、系统任务、esp_timer
Core 1 (APP_CPU)     — 用户业务任务（推荐）
```

- WiFi/LwIP 协议栈**强制运行在 Core 0**，由 IDF 内部管理
- BT 协议栈同样在 Core 0
- 用户任务**默认绑 Core 1**（`xTaskCreatePinnedToCore(..., 1)`）
- `app_main()` 默认在 Core 0 执行；创建任务后应尽快返回

### 绑核决策表

| 任务 | 推荐核心 | 原因 |
|------|---------|------|
| WiFi/TLS/网络 | Core 0 | IDF 协议栈内部管理 |
| WSS Model | Core 0 或 1 | 若纯接收转发可留 Core 0；若需解析则绑 Core 1 |
| LVGL | **Core 1** | 避免与 WiFi 抢占，减少 `Guru Meditation` |
| 音频采集 I2S | **Core 1** | 与 LVGL 同核时控制刷新率 |
| Presenter | Core 1 | 与 LVGL 同核减少跨核 Queue 延迟 |
| OTA | Core 0 | 涉及 Flash 写入与网络，与 WiFi 同核 |

### 跨核通信（C17）

ESP32 双核共享同一 FreeRTOS 实例（不同于 BK7258），因此 **xQueue/xSemaphore 在跨核间有效**。

```c
/* ✅ ESP32 跨核 Queue 直接可用 */
xQueueSend(s_ui_queue, &evt, pdMS_TO_TICKS(10));  /* Core 0 → Core 1 */

/* ✅ 跨核 mutex（FreeRTOS 内置优先级继承） */
xSemaphoreTake(g_lvgl_mutex, pdMS_TO_TICKS(100));
```

**注意：** 虽然 xQueue 跨核有效，但高频跨核 Queue 会产生 cache 同步开销。音频 DMA 等实时路径建议绑同核。

---

## 推荐任务优先级（ESP-IDF 风格）

```c
/* 示例：configMAX_PRIORITIES = 25 */
#define AUDIO_TASK_PRIO      (configMAX_PRIORITIES - 1)   /* 24 — 最高 */
#define WSS_TASK_PRIO        (configMAX_PRIORITIES - 3)   /* 22 */
#define LVGL_TASK_PRIO       (configMAX_PRIORITIES - 5)   /* 20 */
#define PRESENTER_TASK_PRIO  (configMAX_PRIORITIES - 7)   /* 18 */
```

**C15 约束：** 相邻任务优先级差 ≥ 2。输出优先级表时**同时给出相对顺序和 IDF 数值**。

---

## 任务创建模板

```c
/* 音频采集 — 绑 Core 1，避免与 WiFi 抢占 */
xTaskCreatePinnedToCore(
    audio_process_task, "audio",
    4096, NULL,
    AUDIO_TASK_PRIO,
    &s_audio_hdl, 1
);

/* LVGL — 绑 Core 1 */
xTaskCreatePinnedToCore(
    lvgl_task, "lvgl",
    8192, NULL,
    LVGL_TASK_PRIO,
    &s_lvgl_hdl, 1
);

/* WSS — 可绑 Core 0（与 WiFi 同核减少跨核延迟） */
xTaskCreatePinnedToCore(
    wss_task, "wss",
    6144, NULL,              /* TLS 握手峰值 ≥ 6144 */
    WSS_TASK_PRIO,
    &s_wss_hdl, 0
);
```

---

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

- `esp_websocket_client` 内部处理 TLS，无需手动调 mbedTLS
- 接收缓冲建议放 PSRAM：`heap_caps_malloc(len, MALLOC_CAP_SPIRAM)`
- **SNTP 须在 TLS 握手前完成**（C8.2）：`esp_netif_sntp_init()`

---

## LVGL 集成（ESP-IDF）

- 官方 port：`esp_lvgl_port`（推荐）或 `lvgl_esp32_drivers`
- `lv_timer_handler()` 必须在专用 `lvgl_task` 中循环调用
- 跨任务刷新：优先 `lv_async_call()`；若用互斥锁，与 `esp_lvgl_port_lock()` 保持一致
- **禁止**在 `ws_event_handler` 或 `esp_http_client` 回调中直接 `lv_label_set_text`

### LVGL 帧缓冲与 PSRAM

| 配置 | 说明 |
|------|------|
| `CONFIG_LV_USE_DRAW_SW` | 软件渲染，适用于无 GPU 芯片 |
| `CONFIG_LV_MEM_CUSTOM` | 自定义 `lv_mem` 分配器为 `heap_caps_malloc`（PSRAM） |
| `CONFIG_LV_COLOR_DEPTH_16` | RGB565，2 字节/像素，带屏音箱推荐 |
| `CONFIG_LV_DISP_DEF_REFR_PERIOD` | 默认 33ms（30fps），高负载可降至 50ms（20fps） |

---

## I2S / DMA 音频

```c
#include "driver/i2s_std.h"

/* IDF 5.x 新 I2S API */
i2s_chan_config_t chan_cfg = I2S_CHANNEL_DEFAULT_CONFIG(I2S_NUM_0, I2S_ROLE_MASTER);
i2s_std_config_t std_cfg  = /* ... */;

i2s_new_channel(&chan_cfg, &tx_handle, &rx_handle);
i2s_channel_init_std_mode(rx_handle, &std_cfg);
```

- Mic 采集任务建议 `configMAX_PRIORITIES - 1`，高于 LVGL
- DMA 缓冲：`heap_caps_malloc(size, MALLOC_CAP_DMA | MALLOC_CAP_INTERNAL)`
- **禁止** DMA 缓冲放 PSRAM（SPIRAM DMA 有限制）

---

## PSRAM / 堆管理 / DMA 缓冲

### 堆分区

| 分配标签 | 说明 |
|----------|------|
| `MALLOC_CAP_8BIT` | 通用 SRAM（最灵活） |
| `MALLOC_CAP_DMA` | DMA 可访问（Internal SRAM only） |
| `MALLOC_CAP_SPIRAM` | PSRAM |
| `MALLOC_CAP_INTERNAL` | 内部 SRAM（非 PSRAM） |

### 最佳实践

| 场景 | 分配方式 | 原因 |
|------|---------|------|
| JSON 解析树 | `heap_caps_malloc(n, MALLOC_CAP_SPIRAM)` | 大对象放 PSRAM |
| DMA 缓冲 | `heap_caps_malloc(n, MALLOC_CAP_DMA \| MALLOC_CAP_INTERNAL)` | DMA 须 Internal SRAM |
| LVGL 帧缓冲 | `heap_caps_malloc(n, MALLOC_CAP_SPIRAM)` | 大帧缓冲放 PSRAM |
| 小对象（<256B） | 普通 `pvPortMalloc` | 内部 SRAM 分配快 |

### 堆监控

```c
size_t free_heap = heap_caps_get_minimum_free_size(MALLOC_CAP_8BIT);
LOG_I(TAG, "Heap min watermark: %u bytes", free_heap);
heap_caps_print_heap_info(MALLOC_CAP_DMA);
```

### PSRAM 配置（sdkconfig）

```
CONFIG_SPIRAM=y
CONFIG_SPIRAM_MODE_OCT=y               # ESP32-S3 OCT 模式
CONFIG_SPIRAM_SPEED_80M=y
CONFIG_SPIRAM_TRY_ALLOCATE_DMA_L2=y    # ESP32-S3 尝试 DMA 分配到 PSRAM
CONFIG_SPIRAM_MALLOC_ALWAYSINTERNAL=16384  # <16KB 默认内部 SRAM
```

---

## 看门狗配置详解

### Task WDT（`CONFIG_ESP_TASK_WDT`）

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `CONFIG_ESP_TASK_WDT_TIMEOUT_S` | 5 | 超时秒数 |
| `CONFIG_ESP_TASK_WDT_CHECK_IDLE_TASK_CPU0` | y | 监控 Core 0 idle |
| `CONFIG_ESP_TASK_WDT_CHECK_IDLE_TASK_CPU1` | y | 监控 Core 1 idle |

**受监控任务：** `main`（`app_main`）和 `esp_timer` 默认被监控。

```c
/* C8.3 — 任务循环中必须定期 yield */
void presenter_task(void *arg) {
    for (;;) {
        if (xQueueReceive(s_queue, &evt, pdMS_TO_TICKS(100)) == pdTRUE) {
            handle_event(&evt);
        }
        /* xQueueReceive 带 timeout 会自动 yield */
    }
}
```

**禁止：** 在受监控任务中执行长阻塞操作（C8.6）。

### Interrupt WDT（`CONFIG_ESP_INT_WDT`）

- 监控 ISR 不返回的异常情况，默认超时 300ms
- 若 ISR 中有复杂计算导致超时，应将计算移到任务中

### 临时禁用 WDT（调试用，量产禁止）

```c
esp_task_wdt_delete(xTaskGetCurrentTaskHandle());  /* 仅调试 */
```

---

## NVS 状态持久化

NVS（Non-Volatile Storage）是 ESP-IDF 推荐的键值存储方案（C13 落地）。

```c
#include "nvs_flash.h"
#include "nvs.h"

/* 初始化（app_main 中调用一次） */
esp_err_t ret = nvs_flash_init();
if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
    nvs_flash_erase();
    nvs_flash_init();
}

/* WiFi 配网状态持久化（C13） */
void wifi_set_state(wifi_config_state_t st) {
    nvs_handle_t h;
    if (nvs_open("wifi", NVS_READWRITE, &h) == ESP_OK) {
        nvs_set_u8(h, "cfg_state", (uint8_t)st);
        nvs_commit(h);
        nvs_close(h);
    }
}
```

**注意：**
- `nvs_flash_erase()` 会清空**所有** NVS 数据，慎用
- NVS API 线程安全，可从多任务调用
- 确保 `partitions.csv` 含 `nvs` 分区（默认有）

---

## WiFi 配网流程

### 方案选择

| 方案 | 适用场景 | IDF 组件 |
|------|---------|----------|
| **SmartConfig** | 零配网（手机 APP） | `smartconfig` |
| **BLE Provisioning** | 蓝牙配网 | `wifi_provisioning` + `protocomm` |
| **SoftAP** | 设备开热点配网 | `esp_wifi` AP + HTTP Server |
| **已知 SSID** | 量产固定 WiFi | 直接 `esp_wifi_set_config()` |

### 配网超时（C11 关键）

```c
#define PROVISION_TIMEOUT_MS  120000  /* 2 分钟 */

void wifi_provision_task(void *arg) {
    wifi_prov_mgr_start_provisioning(...);
    TickType_t start = xTaskGetTickCount();
    while (!wifi_prov_mgr_is_provisioned()) {
        if ((xTaskGetTickCount() - start) > pdMS_TO_TICKS(PROVISION_TIMEOUT_MS)) {
            LOG_W(TAG, "Provision timeout, fallback to SoftAP");
            switch_to_softap_mode();
            break;
        }
        vTaskDelay(pdMS_TO_TICKS(500));
    }
}
```

---

## 安全启动 / Flash 加密 / OTA 安全

### 安全启动（Secure Boot v2）

```
# sdkconfig
CONFIG_SECURE_BOOT=y
CONFIG_SECURE_BOOT_V2_RSA=y
CONFIG_SECURE_SIGNED_APPS_RSA=y
```

- 首次烧录 `bootloader` + `partition-table` + 应用固件
- 后续 OTA 须用相同 RSA 私钥签名

### Flash 加密

```
CONFIG_FLASH_ENCRYPTION_ENABLED=y
CONFIG_FLASH_ENCRYPTION_MODE_DEVELOPMENT=y  # 开发阶段
```

- 开发模式：可多次烧写明文固件自动加密
- 生产模式（`RELEASE`）：首次烧写后 Flash 自动加密，后续只能烧写加密固件

### OTA 安全（C9 联动）

- OTA 固件**必须签名验证**（Secure Boot 或 `esp_app_desc` 校验）
- OTA 回滚：`CONFIG_BOOTLOADER_APP_ROLLBACK_ENABLE=y`
- OTA 分区：确保 `partitions.csv` 含 `ota_0` / `ota_1`

---

## FreeRTOS 配置（sdkconfig 关键项）

```
CONFIG_FREERTOS_HZ=1000
CONFIG_FREERTOS_CHECK_STACKOVERFLOW_CANARY=y
CONFIG_FREERTOS_CHECK_MUTEX_GIVEN_BY_OWNER=y
CONFIG_ESP_MAIN_TASK_STACK_SIZE=3584
CONFIG_ESP_SYSTEM_EVENT_TASK_STACK_SIZE=4096
CONFIG_ESP_TIMER_TASK_STACK_SIZE=4096
CONFIG_FREERTOS_TIMER_TASK_STACK_DEPTH=4096
```

---

## SDK 深度裁剪（ESP-IDF）

> **以下仅为候选项**，须在产品需求问卷确认「不需要」后再关闭（C6.1）。

### 配置入口

```bash
idf.py menuconfig
```

### 优先关闭项

| 类别 | menuconfig 路径 | 未用时关闭 |
|------|----------------|-----------|
| 蓝牙 | Component config → Bluetooth | `CONFIG_BT_ENABLED=n` |
| OTA | Component config → App update | 无 OTA 则关 |
| HTTP Server | Component config → HTTP Server | 无本地配网页则关 |
| mDNS | Component config → mDNS | 无局域网发现则关 |
| 多余 log | Component config → Log | `CONFIG_LOG_DEFAULT_LEVEL_WARN` |
| TLS cipher | mbedTLS → TLS Key Exchange | 仅留 ECDHE-RSA + AES-GCM |
| LVGL | Component config → LVGL | 关 demo、缩 `CONFIG_LV_MEM_SIZE` |
| WiFi | 保留 STA，关 AP/SoftAP（若不用） | |
| 分区 | Partition Table | 自定义 `partitions.csv` 缩 app/缩小 spiffs |

### 裁剪验证

```bash
idf.py size              # Flash/RAM 组件占比
idf.py size-components   # 逐项对比
```

记录 `idf.py size` 裁剪前后对比；堆峰值用 `heap_caps_get_minimum_free_size()` 观测。

---

## 文件归属惯例（ESP-IDF 工程）

```
main/
├── app_main.c              # 入口，创建任务
├── include/app_mvp.h       # net_evt_t / ui_evt_t
├── app_test_config.h       # APP_TEST_MODE_* 宏
├── network_wss_task.c      # Model — WSS
├── app_presenter.c         # Presenter — Looper
├── ui_view_manager.c       # View — LVGL / lv_async_call
└── audio_capture.c         # Model — I2S DMA
components/
└── my_board/               # 板级驱动
sdkconfig / sdkconfig.defaults
partitions.csv              # 按需自定义分区
```

---

## 编译与产物

```bash
idf.py set-target esp32s3    # 依芯片
idf.py build
idf.py flash monitor
idf.py size                  # Flash/RAM 组件占比
idf.py size-components
```

产物：`build/<project>.elf`、`build/<project>.map`

---

## Crash 定位（addr2line）

```bash
# Guru Meditation Backtrace 中的 PC
xtensa-esp32-elf-addr2line -pfiaC -e build/your_project.elf 0x400d1234

# 多核 SoC 注意选对应 toolchain：xtensa-esp32s3-elf-addr2line 等
```

| 日志关键词 | 优先对照 |
|-----------|----------|
| `STACK OVERFLOW` + WssTask | [mbedtls_wss_memory.txt](../prompts/mbedtls_wss_memory.txt)、增大栈 |
| `LoadProhibited` + network | 完整版 `examples/bad_lvgl_cross_thread.c` |
| `task watchdog` | [deadlock_lock_order.txt](../prompts/deadlock_lock_order.txt) |
| TLS 握手 fail | SNTP 未同步、证书、cipher 不匹配 |

---

## MVP 集成要点（ESP-IDF 特有）

1. **WSS 回调在 esp_event 任务** — 等同 Model 短路径：`parse → Queue`，禁止 `lv_obj_*`
2. **Core 绑定**：WiFi/LwIP 默认 Core0；LVGL + 音频可绑 Core1，降低跨核竞态
3. **堆**：TLS 握手峰值用 `heap_caps_get_minimum_free_size(MALLOC_CAP_8BIT)` 观测
4. **事件总线**：见 [queue_event_bus.txt](../prompts/queue_event_bus.txt)
5. **同步原语**：ISR 用 Notification/Queue FromISR — [freertos_sync_primitives.txt](../prompts/freertos_sync_primitives.txt)
6. **NVS**：状态持久化用 `nvs_*` API — 见上方 NVS 章节

---

## 共享引擎：prompt + 云端 uplink（C10）

ESP-IDF 常见组合：I2S RX/TX + esp-sr AEC 或自定义 ref 注入。

| 项 | ESP32 做法 |
|----|------------|
| prompt 播放 | I2S TX / `esp_audio` 播放器；结束须 stop writer 并释放 AEC ref |
| 开麦 | prompt `PLAYER_EVENT_FINISHED` 或 I2S TX idle 后再 `start_uplink` |
| settle | 80–150ms + 检查 AEC 状态（esp-sr `afe` reset 若 API 提供） |
| 任务 | 音频回调在独立 task — 禁止 `lv_obj_*`；用 Queue → Presenter |
| 诊断 | `uxTaskGetStackHighWaterMark` on voice task；peak 日志对比两轮 |

深细节 → [voice_asr_uplink.txt](../prompts/voice_asr_uplink.txt)

---

## 快速参考路径

```
WSS 组件:     components/esp_websocket_client/
TLS:          components/mbedtls/
LVGL port:    components/esp_lvgl_port/ 或 managed_components
FreeRTOS:     components/freertos/
NVS:          components/nvs_flash/
OTA:          components/esp_https_ota/
menuconfig:   idf.py menuconfig