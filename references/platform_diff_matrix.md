# 平台差异矩阵（L2+ 按需加载）

Agent 做跨平台 review 或迁移时读取本文件，快速了解各平台差异。

> ESP32 / STM32 / JL / BK / Zephyr 五大平台横向对比。

---

## 架构对比

| 维度 | ESP32 | STM32 | JL (AC79) | BK (BK7258) | Zephyr |
|------|-------|-------|-----------|-------------|--------|
| CPU 架构 | Xtensa LX6/双核 | Cortex-M4/M7/M33 | Cortex-M33 | ARM968/三核 | 多架构 |
| RTOS | FreeRTOS (ESP-IDF) | FreeRTOS (CubeMX) | FreeRTOS (JL SDK) | FreeRTOS (Armino) | Zephyr Kernel |
| 优先级方向 | 数字越大越高 | 数字越大越高 | 数字越大越高 | 数字越大越高 | 数字越大越高 |
| 栈单位 | bytes | words (4B) | bytes | bytes | bytes |
| 双核 | 是 | 否 | 否 | 是(三核) | AMP 支持 |
| PSRAM | 是 (SPI) | 否 | 否 | 否 | 平台相关 |

## 内存对比

| 维度 | ESP32 | STM32 | JL (AC79) | BK (BK7258) | Zephyr |
|------|-------|-------|-----------|-------------|--------|
| 典型 Flash | 4MB | 1-2MB | 4MB | 4MB | 平台相关 |
| 典型 RAM | 520KB | 192KB-1MB | 512KB | 256KB | 平台相关 |
| PSRAM | 最大 8MB | 无 | 无 | 无 | 平台相关 |
| DMA 内存 | 专用 DMA 区域 | 任意 SRAM | 专用区域 | 专用区域 | 平台相关 |
| 堆管理 | 多堆 (internal/PSRAM) | 单堆 | 多堆 | 多堆 | k_malloc / pool |

## 网络对比

| 维度 | ESP32 | STM32 | JL (AC79) | BK (BK7258) | Zephyr |
|------|-------|-------|-----------|-------------|--------|
| WiFi | 内置 | 外接模块 | 内置 | 内置 | 驱动模型 |
| TLS | mbedTLS | mbedTLS | mbedTLS | mbedTLS | mbedTLS |
| WSS 栈建议 | 6144B | 8192B | 6144B | 6144B | 4096B |
| SNTP | esp_sntp | LwIP SNTP | 自带 | 自带 | 内置 |

## 显示 / LVGL 对比

| 维度 | ESP32 | STM32 | JL (AC79) | BK (BK7258) | Zephyr |
|------|-------|-------|-----------|-------------|--------|
| LCD 驱动 | esp_lcd | HAL LTDC | 自带 | 自带 | 设备模型 |
| LVGL 版本 | v8/v9 | v8/v9 | v8 | v8 | v8/v9 |
| 帧缓冲 | PSRAM 双缓冲 | SRAM 部分刷新 | SRAM | SRAM | 平台相关 |
| TE 同步 | GPIO TE | LTDC TE | 自带 | 自带 | 平台相关 |

## 音频对比

| 维度 | ESP32 | STM32 | JL (AC79) | BK (BK7258) | Zephyr |
|------|-------|-------|-----------|-------------|--------|
| I2S | esp_i2s | HAL I2S | audio_server | audio_server | 设备模型 |
| DMA | 专用 DMA | DMA1/DMA2 | 专用 | 专用 | DMA API |
| AEC | 软件 AEC | 外部芯片 | 内置 | 内置 | 平台相关 |
| ASR | 云端 | 云端 | 云端 | 云端 | 云端 |

## OTA 对比

| 维度 | ESP32 | STM32 | JL (AC79) | BK (BK7258) | Zephyr |
|------|-------|-------|-----------|-------------|--------|
| 分区表 | ota_0 + ota_1 | 自定义 | 自带 | 自带 | MCUboot |
| 签名验证 | esp_secure_boot | HAL CRC | 自带 | 自带 | MCUboot |
| 回滚 | mark_valid | 自定义 | 自带 | 自带 | MCUboot |
| 差分升级 | 支持 | 第三方 | 支持 | 支持 | 支持 |

## 看门狗对比

| 维度 | ESP32 | STM32 | JL (AC79) | BK (BK7258) | Zephyr |
|------|-------|-------|-----------|-------------|--------|
| Task WDT | esp_task_wdt | IWDG | 自带 | 自带 | 看门狗 API |
| 超时配置 | CONFIG_ESP_TASK_WDT_TIMEOUT_S | IWDG 预分频 | 配置文件 | 配置文件 | DTS/Kconfig |
| 暂停模式 | 可配置 | 可配置 | 可配置 | 可配置 | 可配置 |

## 低功耗对比

| 维度 | ESP32 | STM32 | JL (AC79) | BK (BK7258) | Zephyr |
|------|-------|-------|-----------|-------------|--------|
| Deep Sleep | esp_deep_sleep | STOP/STANDBY | 自带 | 自带 | PM 框架 |
| 唤醒源 | Timer/GPIO/Touch | RTC/EXTI/WKUP | 自带 | 自带 | DTS 配置 |
| Tickless | 支持 | 支持 | 支持 | 支持 | 自动管理 |

## Crash 诊断对比

| 维度 | ESP32 | STM32 | JL (AC79) | BK (BK7258) | Zephyr |
|------|-------|-------|-----------|-------------|--------|
| addr2line | xtensa-esp32-elf-addr2line | arm-none-eabi-addr2line | 自带工具 | 自带工具 | arm-none-eabi-addr2line |
| ELF 路径 | build/project.elf | build/Project.elf | build/app.elf | build/app.elf | build/zephyr/zephyr.elf |
| Core dump | esp_core_dump | 自定义 | 自带 | 自带 | 追踪 API |
| 日志格式 | ESP_LOG | LOG/printf | LOG | LOG | LOG |

## 构建系统对比

| 维度 | ESP32 | STM32 | JL (AC79) | BK (BK7258) | Zephyr |
|------|-------|-------|-----------|-------------|--------|
| 构建工具 | idf.py (CMake) | CMake + Make | Make | Make | west (CMake) |
| 配置系统 | Kconfig | .ioc + Kconfig | Kconfig | Kconfig | Kconfig + DTS |
| 包管理 | 组件注册 | CubeMX 包 | SDK 内含 | SDK 内含 | west manifest |

## SDK 裁剪对比

| 维度 | ESP32 | STM32 | JL (AC79) | BK (BK7258) | Zephyr |
|------|-------|-------|-----------|-------------|--------|
| 裁剪方式 | Kconfig 组件开关 | CubeMX 模块勾选 | Kconfig + Makefile | Kconfig | Kconfig + DTS |
| 裁剪前扫描 | 组件列表 | HAL 模块列表 | SDK 模块地图 | SDK 模块地图 | west list |
| 回滚方案 | git + sdkconfig 备份 | .ioc 备份 | git tag | git tag | git + west.yml |

---

## 迁移注意事项

### ESP32 → STM32

1. FreeRTOS Task 优先级方向不变（数字越大越高）；但 NVIC 中断优先级是数字越小越高，需注意区分
2. 栈单位变更（bytes → words）
3. PSRAM 不可用，需要重新规划内存
4. WiFi/TLS 需要外接模块或手动集成
5. `esp_xxx` API 改为 `HAL_xxx` 或 CMSIS-RTOS

### STM32 → ESP32

1. FreeRTOS Task 优先级方向不变（数字越大越高）
2. 栈单位变更
3. 可利用 PSRAM 扩展内存
4. WiFi/TLS 内置，简化网络开发
5. `HAL_xxx` 改为 `esp_xxx` API

### 任意平台 → Zephyr

1. 设备驱动改为 Device Tree 模型
2. 线程 API 改为 `k_thread_create`
3. 同步原语改为 `k_sem` / `k_mutex` / `k_msgq`
4. 配置改为 Kconfig + DTS overlay
5. 构建改为 `west build`

---

## 约束域平台适用性

| 约束域 | ESP32 | STM32 | JL | BK | Zephyr | 说明 |
|--------|-------|-------|-----|-----|--------|------|
| C1 LVGL | ✅ | ✅ | ✅ | ✅ | ✅ | 通用 |
| C2 Queue | ✅ | ✅ | ✅ | ✅ | ✅ | 通用 |
| C3 cJSON | ✅ | ✅ | ✅ | ✅ | ✅ | 通用 |
| C4 ISR/DMA | ✅ | ✅ | ✅ | ✅ | ✅ | 通用 |
| C7 内存 | ✅ | ✅ | ✅ | ✅ | ✅ | PSRAM 仅 ESP32 |
| C8 启动 | ✅ | ✅ | ✅ | ✅ | ✅ | 通用 |
| C9 密钥 | ✅ | ✅ | ✅ | ✅ | ✅ | 通用 |
| C10 语音 | ✅ | ✅ | ✅ | ✅ | ✅ | 共享引擎模式 |
| C17 多核 | ✅ | ❌ | ❌ | ✅ | ✅ | 仅多核平台 |
| C18 外设 | ✅ | ✅ | ✅ | ✅ | ✅ | API 不同 |
| C19 Flash | ✅ | ✅ | ✅ | ✅ | ✅ | API 不同 |
| C20 网络 | ✅ | ✅ | ✅ | ✅ | ✅ | 通用 |
| C21 低功耗 | ✅ | ✅ | ✅ | ✅ | ✅ | 机制不同 |
| C22 OTA | ✅ | ✅ | ✅ | ✅ | ✅ | MCUboot for Zephyr |
| C23 显示 | ✅ | ✅ | ✅ | ✅ | ✅ | 驱动不同 |
| C25-C28 A/V | ✅ | ✅ | ✅ | ✅ | ✅ | 通用 |
| C29-C45 效率 | ✅ | ✅ | ✅ | ✅ | ✅ | 通用 |
