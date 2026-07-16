# 铁律约束分片：平台与外设驱动（Platform）

本文件包含外设驱动安全（GPIO/I2C/SPI/DMA/ADC/PWM）、Flash/NVS 状态持久化、网络韧性、低功耗管理、显示驱动安全、板级资源契约、传感器集成契约等约束。

> 对应约束 ID：C18–C21, C23, C42, C45
> 其他分片：[constraint_review.md](constraint_review.md) | [constraint_memory.md](constraint_memory.md) | [constraint_rtos.md](constraint_rtos.md) | [constraint_media.md](constraint_media.md) | [constraint_ota.md](constraint_ota.md) | [constraint_recover.md](constraint_recover.md) | [constraint_bluetooth_protocol.md](constraint_bluetooth_protocol.md)

---

## 严重度定义

| 级别 | 含义 | 处理 |
|------|------|------|
| P0 | 必崩 / 必泄漏 / 必死锁 | 阻塞合并，须附修复 diff 或范例引用 |
| P1 | 高概率量产问题 | 本迭代必须修复或登记风险 |
| P2 | 可维护性 / 可测试性 | 建议修复，可排期 |

---

## C18 — 外设驱动安全

| ID | 约束 | 严重度 | 验证 | 正例 | 反例 |
|----|------|--------|------|------|------|
| C18.1 | GPIO 方向必须在使用前配置（gpio_config 先于 gpio_set_level） | P0 | `peripheral_driver_checker.py` | `gpio_config()` [GPIO_CONFIG] → `gpio_set_level()` [GPIO_SET] | 未 config 直接 set_level |
| C18.2 | I2C 设备地址必须来自 datasheet，禁止硬编码猜测 | P1 | `peripheral_driver_checker.py` | `#define OLED_ADDR 0x3C /* datasheet */` | `#define OLED_ADDR 0x60` 无依据 |
| C18.3 | SPI 时钟模式（CPOL/CPHA）必须匹配从设备 datasheet | P1 | 人工 | `.mode = 0` 与 Flash 匹配 | `.mode = 2` 与 Flash 不匹配 |
| C18.4 | DMA 通道分配须文档化，同一通道不可被两个外设同时使用 | P1 | 人工 | DMA 通道分配表 | I2S 和 SPI 共享 DMA 通道 |
| C18.5 | ADC 引脚必须配置为模拟输入模式，禁用上拉/下拉 | P2 | 人工 | `adc1_config_channel_atten()` | ADC 引脚同时配置为数字输出 |
| C18.6 | PWM 频率与分辨率互斥，须根据应用选择 | P2 | 人工 | 5kHz/13-bit（电机） | 100kHz/7-bit（亮度不够） |
| C18.7 | Zephyr `DEVICE_DT_GET*()` 得到的设备在同一初始化路径使用前必须 `device_is_ready()` | P0 | `zephyr_pattern_checker.py` | `if (!device_is_ready(dev)) return -ENODEV;` | 直接 I2C/GPIO 调用 |

---

## C19 — Flash / NVS / 状态持久化

| ID | 约束 | 严重度 | 验证 | 正例 | 反例 |
|----|------|--------|------|------|------|
| C19.1 | NVS 写入后必须 `nvs_commit()` [NVS_COMMIT] + 检查返回值 | P0 | `flash_nvs_checker.py` | `nvs_set_str` [NVS_WRITE] → `nvs_commit` [NVS_COMMIT] → `nvs_close` | 不 commit 不检查返回值 |
| C19.2 | Flash 擦写期间禁止读取同分区 | P1 | 人工 | 擦写前关闭读句柄 | 同时 erase + read NVS |
| C19.3 | OTA 首次启动必须调用 `mark_valid_cancel_rollback` [OTA_MARK_VALID] | P1 | 人工 | `app_main` 中调用 | 未调用，重启后回滚 |
| C19.4 | OTA 产品分区表须含 `ota_0` + `ota_1`；NVS 分区不可删除 | P1 | 人工 | `partitions.csv` 含 ota_0/ota_1 | 缺 ota_1 分区 |
| C19.5 | Flash 高频写入场景须做磨损均衡（NVS blob API / 缓冲写入） | P2 | 人工 | 每 5 分钟批量写入 | 每秒写 NVS |

---

## C20 — 网络韧性

| ID | 约束 | 严重度 | 验证 | 正例 | 反例 |
|----|------|--------|------|------|------|
| C20.1 | WiFi/WSS 断线重连必须有指数退避（1s→2s→…→60s cap） | P0 | `network_resilience_checker.py` | `WIFI_RECONNECT_BASE_MS * (1 << retry)` | 立即 `esp_wifi_connect()` tight loop |
| C20.2 | 所有阻塞网络操作（recv [SOCKET_RECV]/send [SOCKET_SEND]/connect [SOCKET_CONNECT]）必须有有限超时 | P0 | `network_resilience_checker.py` | `setsockopt(SO_RCVTIMEO, 10s)` | `recv(sock, buf, len, 0)` [SOCKET_RECV] 无超时 |
| C20.3 | DNS 解析失败必须处理，不可直接崩溃 | P1 | 人工 | `getaddrinfo` 返回值检查 + 重试 | `getaddrinfo` 失败直接 HardFault |
| C20.4 | TLS 握手失败须区分错误类型（证书无效 vs 超时 vs 服务端拒绝） | P1 | 人工 | 按 mbedTLS 错误码分类处理 | 所有 TLS 错误统一重试 |
| C20.5 | 网络断线时业务必须有降级策略（离线模式） | P1 | 人工 | `NET_MODE_OFFLINE` + 本地功能继续 | 断线后产品完全不可用 |
| C20.6 | 同一执行上下文内必须遵守 WiFi connect → MQTT connect/start → subscribe；跨事件回调链应显式由 IP/MQTT-connected 事件衔接 | P0 | `api_sequence_checker.py` | WiFi 获 IP 后再启动 MQTT 并订阅 | MQTT 未连接就 subscribe |

---

## C21 — 低功耗管理

| ID | 约束 | 严重度 | 验证 | 正例 | 反例 |
|----|------|--------|------|------|------|
| C21.1 | 深度睡眠前必须保存运行状态到 NVS/Flash（`nvs_commit` [NVS_COMMIT] + 检查返回值） | P0 | `low_power_checker.py` | `nvs_set_u8` [NVS_WRITE] → `nvs_commit` [NVS_COMMIT] → `esp_deep_sleep_start` [DEEP_SLEEP] | 直接 `esp_deep_sleep_start` [DEEP_SLEEP] 丢失状态 |
| C21.2 | 唤醒后须检查 `wakeup_cause`，恢复状态而非重新初始化 | P1 | 人工 | `esp_sleep_get_wakeup_cause()` 分支处理 | 唤醒后无条件 full_init |
| C21.3 | Tickless Idle 配置须确认高频任务不受唤醒延迟影响 | P1 | 人工 | `CONFIG_FREERTOS_USE_TICKLESS_IDLE=y` + 高频任务用独立定时器 | 盲开 tickless 导致音频 tick 漂移 |
| C21.4 | 深度睡眠前必须逐个关闭外设电源（LCD 背光/音频 DAC/WiFi/PSRAM） | P1 | `low_power_checker.py` | `power_down_peripherals()` 逐个关闭 | 仅 `esp_deep_sleep_start` 不关外设 |
| C21.5 | 多唤醒源（timer/ext0/ext1/PIR）同时配置时须确认 GPIO 无冲突 | P2 | 人工 | 唤醒源分配表 + GPIO 唯一性检查 | 同一 GPIO 配 ext0 + ext1 冲突 |

---

## C23 — 显示驱动安全

| ID | 约束 | 严重度 | 验证 | 正例 | 反例 |
|----|------|--------|------|------|------|
| C23.1 | LCD 初始化时序必须严格遵循 datasheet（复位脉宽≥10ms、复位后等待≥120ms、Sleep Out 后等待≥120ms） | P0 | 人工 | [lcd_display_driver.txt](../prompts/lcd_display_driver.txt) | 复位后立即发命令 |
| C23.2 | 背光控制必须用 PWM（非 GPIO 开关），支持亮度调节和渐变；低功耗时关闭背光电源 | P1 | 人工 | `ledc_set_duty` + `gpio_set_level(BL_EN, 0)` | `gpio_set_level(BL_PIN, 1)` 仅开/关 |
| C23.3 | `lv_timer_handler` [TIMER_HANDLER] 调用频率必须匹配面板刷新率（60Hz→16ms，30Hz→33ms）；禁止过快调用浪费 CPU | P1 | `lvgl_frame_rate_checker.py` + 人工 | `vTaskDelay(1000/REFRESH_RATE)` [TASK_DELAY] | `vTaskDelay(1)` [TASK_DELAY] 1ms 调用 |
| C23.4 | 显示刷新必须有撕裂防护（TE 信号同步 / 双缓冲 / 直接模式）；禁止单缓冲无同步写入 | P1 | 人工 | `esp_lcd_panel_io_tx_param(0x35)` TE 信号 | 单缓冲直接写入 |
| C23.5 | 帧缓冲大小必须根据 RAM 可用性选择：PSRAM 可用→全屏双缓冲；RAM 不足→部分刷新（1/5 或 1/10 屏）；分配失败必须检查 | P0 | `display_driver_checker.py` | `heap_caps_malloc` [HEAP_ALLOC] 返回值检查 | 未检查 `malloc` [HEAP_ALLOC] 返回 |
| C23.6 | `lv_disp_drv_t` 注册必须设置 `hor_res`、`ver_res`、`draw_buf`、`flush_cb`；已注册的 flush 回调必须在传输安全后调用 ready API，或声明异步完成者 | P1 | `display_driver_checker.py` + `lvgl_frame_rate_checker.py` | 完整 `lv_disp_drv_init` + 字段赋值 + transfer 后 ready | 缺少字段或回调不归还 draw buffer |
| C23.7 | 同一执行上下文内 camera init/open 必须先于 capture/start；跨任务时必须以显式 ready 状态或事件衔接 | P0 | `api_sequence_checker.py` | init 成功后再启动采集 | 未初始化就取帧/启动采集 |

**症状表**：

| 症状 | 可能约束 |
|------|----------|
| LCD 白屏 / 无显示 | C23.1 初始化时序错误 |
| 画面撕裂 | C23.4 无 TE 同步 |
| UI 渲染区域错误 | C23.6 `hor_res`/`ver_res` 未设置 |
| 背光无法调节 | C23.2 GPIO 直接控制无 PWM |
| 内存不足崩溃 | C23.5 帧缓冲分配失败 |

---

## C42 — 板级资源契约

| ID | 约束 | 严重度 | 验证 | 正例 | 反例 |
|----|------|--------|------|------|------|
| C42.1 | GPIO、DMA、clock、IRQ、cache、heap、PSRAM 资源必须声明 owner | P0 | 人工 | `i2s0 owned by audio` | 两模块抢 DMA |
| C42.2 | 板级资源冲突必须有检查方式或审查表 | P0 | 人工 | pinmux/resource table | 到板上才发现冲突 |
| C42.3 | DMA/cache/heap capability 必须声明对齐、cacheability 和分配域 | P1 | 人工 + C28 | DMA buffer internal aligned | PSRAM buffer 给 DMA |
| C42.4 | IRQ priority、ISR-safe API、跨核访问边界必须明确 | P1 | 人工 + C4/C17 | ISR only notify | ISR 调非安全 API |
| C42.5 | clock/power domain 生命周期与低功耗约束必须进入 platform/profile | P2 | 人工 | sleep 前关 clock | 低功耗后外设不恢复 |

**症状表**：

| 症状 | 可能约束 |
|------|----------|
| 换板后 GPIO/DMA 冲突 | C42.1/C42.2 缺 resource owner |
| DMA 偶发数据错 | C42.3 cache/heap capability 不清 |
| 低功耗唤醒后外设异常 | C42.5 clock/power domain 未建模 |

---

## C45 — 传感器集成契约

| ID | 约束 | 严重度 | 验证 | 正例 | 反例 |
|----|------|--------|------|------|------|
| C45.1 | 传感器 `init/probe` 必须有 datasheet/register map 依据，并校验 `WHO_AM_I` / `chip_id` / `device_id` | P0 | `sensor_integration_checker.py` + 人工 | [good_sensor_integration.c](../tools/fixtures/good_sensor_integration.c) | [bad_sensor_integration.c](../tools/fixtures/bad_sensor_integration.c) |
| C45.2 | I2C/SPI 传感器事务必须有有限 timeout、retry/backoff 和错误分类；禁止默认永久等待或 silent fail | P0 | `sensor_integration_checker.py` + C31 | 同上 | 同上 |
| C45.3 | data-ready/DRDY/status/fifo 等待必须事件驱动或有界轮询；禁止 tight poll / magic delay | P1 | `sensor_integration_checker.py` + 人工 | `xTaskNotifyWait(..., pdMS_TO_TICKS(20))` [TASK_NOTIFY_TAKE] | `while (!(status & READY)) { read_reg(); }` |
| C45.4 | sample 输出必须携带 timestamp、单位、量程、scale/offset 或校准版本；禁止 raw register value 直接跨模块传播 | P1 | `sensor_integration_checker.py` + C32 | `value_milli_unit + timestamp_ms + scale_ppm` | `out->raw_value = raw16` |
| C45.5 | calibration/self-test/warm-up 必须有生命周期与失效策略，不得放在采样 hot path | P2 | `sensor_integration_checker.py` + C33/C34 | start 前校准，配置变更后失效重做 | 每次 read 都 `calibrate_sensor_offsets()` |

**症状表**：

| 症状 | 可能约束 |
|------|----------|
| I2C/SPI 偶发卡死或 WDT | C45.2 + C31/C44 |
| 传感器读数跳变、单位混乱、融合结果漂移 | C45.1/C45.4 |
| 采样周期抖动、控制环 jitter | C45.3/C45.5 + C34 |

---

## C46 -- Bluetooth Protocol Alignment

| ID | Constraint | Severity | Validation | Good pattern | Bad pattern |
|----|------------|----------|------------|--------------|-------------|
| C46.1 | BLE init/close must have a state machine and rollback path | P1 | `ble_protocol_checker.py` + integration log | `init -> configure -> start -> stop` is explicit | Direct BLE API calls with no state owner |
| C46.2 | ADV/reconnect parameters must come from profile or board config | P1 | Manual + fixtures | Config-driven ADV interval/timeout | Hard-coded interval values |
| C46.3 | GATT UUID/Service/Characteristic changes must match documents and route mapping | P1 | Manual | Doc mapping passes review | Service changes ship without doc update |
| C46.4 | BLE state machine must cover idle/connecting/connected/disconnecting | P1 | `ble_protocol_checker.py` + event replay | Illegal transitions recover cleanly | Pending state jumps directly to idle |
| C46.5 | Pairing/auth/encryption/bond lifecycle must be explicit and clean up on failure | P2 | Manual | Pairing context has clear lifetime | Plain pairing or stale bond residue |
| C46.6 | MTU and fragment settings must negotiate by device capability and support fallback | P1 | Manual + compatibility tests | MTU and payload size are negotiated | Fixed MTU causes compatibility failures |
| C46.7 | Error codes must distinguish recoverable/fatal and map to recovery actions | P1 | Manual + log aggregation | Retry/disable/alert mapping is visible | All failures log the same error |
| C46.8 | Platform capability mapping must cover ESP32/JL/BK/STM32/Zephyr boundaries | P1 | Manual + document alignment | Capability matrix is traceable | Platform capability is assumed globally |

**Symptom map**

| Symptom | Possible constraints |
|---------|----------------------|
| BLE connection fails | C46.1/C46.4 |
| Reconnect storm | C46.2/C46.7 |
| Pairing failure | C46.5 |
| Compatibility crash | C46.6/C46.8 |

---

## C47 — Tool Output and Log Hygiene

| ID | Constraint | Severity | Validation |
|----|------------|----------|------------|
| C47.1 | MCP tool output and logs MUST redact password/token/secret/API-key values before returning or sharing | P0 | `tool_log_hygiene_checker.py` + review |
| C47.2 | Redaction must occur before persistence/export as well as before display | P1 | Manual + serial export tests |

## C48 — AI-generated Firmware Code Review

| ID | Constraint | Severity | Validation |
|----|------------|----------|------------|
| C48.1 | AI-generated code MUST verify SDK APIs against the selected platform map | P0 | `ai_generated_code_checker.py` + review |
| C48.2 | AI-generated error paths MUST preserve cleanup/logging/propagation semantics | P1 | `ai_generated_code_checker.py` + C12 |
| C48.3 | Keep contract comments; remove line-by-line AI narration before merge | P2 | `ai_generated_code_checker.py` |
