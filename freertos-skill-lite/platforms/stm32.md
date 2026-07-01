# STM32 / CubeMX + HAL 平台专档

Agent 确认目标平台为 STM32 系列时读取本文件。

## 关键差异速览

| 项目 | STM32 + CubeMX 惯例 | 注意 |
|------|---------------------|------|
| 任务优先级 | CMSIS-RTOS v1/v2：`osPriorityXxx`；原生 FreeRTOS：**数字越小越高** | 与 ESP-IDF **相反** |
| 任务创建 | CubeMX 生成 `MX_FREERTOS_Init()` + `osThreadNew` / `xTaskCreate` | 优先在 CubeMX 配好再手改 |
| 堆内存 | `pvPortMalloc` / `configTOTAL_HEAP_SIZE` | 默认堆小，TLS+LVGL 需调大至 32KB+ |
| 栈单位 | `xTaskCreate` 的 `usStackDepth` 单位是 **word**（32-bit = 4 bytes） | 2048 words = 8192 bytes |
| 网络 | LwIP + mbedTLS（手动集成或 Mongoose） | WSS 需自行拼 TLS 层 |
| HAL 回调 | `HAL_XXX_CpltCallback` 在中断上下文 | 必须用 `*FromISR` API |

## 推荐任务优先级（CMSIS-RTOS v2 / FreeRTOS）

```c
/* 数字越小优先级越高 */
#define AUDIO_TASK_PRIO      (osPriorityRealtime)    /* 最高 — 24 */
#define WSS_TASK_PRIO        (osPriorityAboveNormal) /* 高于普通 */
#define LVGL_TASK_PRIO       (osPriorityNormal)
#define PRESENTER_TASK_PRIO  (osPriorityBelowNormal)
```

CubeMX 生成的 `osPriority_t` 映射：

| CMSIS 枚举 | 数值 | 适用 |
|-----------|------|------|
| `osPriorityRealtime` | 48+ | I2S DMA 音频 |
| `osPriorityAboveNormal` | 32+ | WSS + TLS |
| `osPriorityNormal` | 24 | LVGL |
| `osPriorityBelowNormal` | 16 | Presenter |

输出优先级表时**同时给出 CMSIS 枚举和相对顺序**。

## 任务创建模板

```c
/* CubeMX 生成 osThreadAttr_t 方式（推荐） */
const osThreadAttr_t audio_task_attributes = {
    .name       = "audio",
    .stack_size = 1024 * 4,   /* bytes，CMSIS 用字节非 word */
    .priority   = (osPriority_t) osPriorityRealtime,
};
osThreadId_t audio_task_hdl = osThreadNew(audio_process_task, NULL, &audio_task_attributes);

/* 原生 FreeRTOS 方式（手写的 Model 任务） */
xTaskCreate(wss_task, "wss", 1536, NULL, WSS_TASK_PRIO, &s_wss_hdl);
/* 注意：1536 = words → 6144 bytes */
```

**栈单位陷阱**：`xTaskCreate` 用 **words**，`osThreadNew` 用 **bytes**。混用时必须标注。

## WSS / 网络（Model 层）

STM32 上 WSS 通常组合：LwIP `raw`/`netconn` + mbedTLS + 手动 WebSocket 帧解析，或第三方库（Mongoose, wolfSSL）。

```c
/* Model 任务主循环 — 禁止 lv_obj_* */
static void wss_task(void *arg)
{
    for (;;) {
        int n = wss_recv(recv_buf, sizeof(recv_buf), 5000);
        if (n > 0) {
            char *text = parse_message_text(recv_buf);
            if (text != NULL) {
                net_emit_event(NET_EVT_DATA, text, strlen(text));
            }
        }
    }
}
```

- mbedTLS `mbedtls_ssl_handshake` 栈开销大，`usStackDepth` ≥ 1536 words。
- LwIP 与 FreeRTOS 共用堆，`configTOTAL_HEAP_SIZE` 建议 ≥ 32768。

## LVGL 集成（STM32）

- 驱动：ST7789/SPI、RGB parallel、LTDC（F4/F7/H7）
- `lv_timer_handler()` 在专用 `lvgl_task` 中，配合 `vTaskDelay(5)` 或定时器中断
- 双缓冲：`lv_disp_draw_buf_init(&draw_buf, buf1, buf2, LV_HOR_RES * 10)`
- 跨任务刷新：`lv_async_call()` 或 `g_lvgl_mutex`（见 prompts/lvgl_thread_safety.txt）

## I2S / DMA 音频

```c
/* CubeMX 配置 I2S + DMA Circular Mode */
void HAL_I2S_RxHalfCpltCallback(I2S_HandleTypeDef *hi2s)
{
    BaseType_t woken = pdFALSE;
    xTaskNotifyFromISR(s_audio_hdl, 0x01, eSetBits, &woken);
    portYIELD_FROM_ISR(woken);
}

void HAL_I2S_RxCpltCallback(I2S_HandleTypeDef *hi2s)
{
    BaseType_t woken = pdFALSE;
    xTaskNotifyFromISR(s_audio_hdl, 0x02, eSetBits, &woken);
    portYIELD_FROM_ISR(woken);
}
```

- DMA 缓冲放 `.dma_buffer` 段或 `__attribute__((aligned(4)))`
- F4/F7：注意 D-Cache 一致性，DMA 缓冲所在区域设 Non-Cacheable 或手动 `SCB_CleanInvalidateDCache`

## FreeRTOSConfig.h 关键项

```c
#define configTOTAL_HEAP_SIZE       ((size_t)(32 * 1024))
#define configCHECK_FOR_STACK_OVERFLOW  2   /* 方式 2：Canary */
#define configUSE_MALLOC_FAILED_HOOK    1
#define configASSERT(x)  if((x)==0){taskDISABLE_INTERRUPTS();for(;;);}
#define configMINIMAL_STACK_SIZE        ((uint16_t)128)
```

## 常见 Crash 定位

| 现象 | STM32 特有原因 |
|------|---------------|
| HardFault @ `BX r3` | 野指针、栈溢出、FPU 上下文未保存 |
| `configASSERT` 在 `prvCheckTasksWaitingTermination` | 堆耗尽，`pvPortMalloc` 失败 |
| LTDC 花屏 | DMA2D 与 CPU 访问显存竞态，Cache 未 invalidate |
| I2S 爆音 | HAL 回调中 `xSemaphoreTake` 阻塞（见 bad_isr_blocking.c） |
| LwIP `ERR_MEM` | `MEM_SIZE` / `configTOTAL_HEAP_SIZE` 不足 |

## SDK 深度裁剪（STM32 + CubeMX）

> **以下仅为候选项**，须在产品需求问卷确认「不需要」后再关闭；禁止未询问用户直接套用。

### 配置入口

- CubeMX `.ioc` → 取消未用 IP（USB/SDIO/CAN/ETH 等）
- `FreeRTOSConfig.h` / `lwipopts.h` / `mbedtls_config.h`

### 优先关闭项

| 类别 | 位置 | 未用时操作 |
|------|------|-----------|
| 外设 IP | CubeMX Pinout | 禁用未用 UART/SPI/I2C/USB/SDIO |
| HAL 模块 | `stm32xx_hal_conf.h` | `#undef HAL_XXX_MODULE_ENABLED` |
| LwIP | `lwipopts.h` | 缩 `MEM_SIZE`、`MEMP_NUM_PBUF`、`TCPIP_THREAD_STACKSIZE` |
| mbedTLS | `mbedtls_config.h` | 仅留 WSS 必需 cipher + 关 debug |
| LVGL | `lv_conf.h` | 关未用 widget、demo、`LV_USE_FONT_SUBPX` 等 |
| FreeRTOS | `FreeRTOSConfig.h` | 缩 `configTOTAL_HEAP_SIZE`、关 trace |
| Middlewares | 工程目录 | 无 BT 则删 `STM32_WPAN` 等 |

### 任务裁剪

```
Core/Src/freertos.c   → 删 CubeMX 生成的未用 osThread
MX_LWIP_Init()        → 无网络则整个不初始化
```

### STM32 裁剪验证

- 编译后看 `.map` 文件：`arm-none-eabi-nm --print-size --size-sort firmware.elf`
- 堆峰值：`xPortGetMinimumEverFreeHeapSize()`
- 栈水位：`uxTaskGetStackHighWaterMark()` 逐任务测

## 文件归属惯例（CubeMX 工程）

```
Core/
├── Src/
│   ├── main.c              # HAL_Init → osKernelStart
│   ├── freertos.c          # CubeMX 生成，任务定义入口
│   ├── app_presenter.c     # Presenter — Looper
│   ├── network_wss_task.c  # Model — WSS + mbedTLS
│   ├── ui_view_manager.c   # View — LVGL
│   └── audio_capture.c     # Model — I2S DMA
├── Inc/
│   ├── app_mvp.h           # net_evt_t / ui_evt_t（见 examples/app_mvp.h）
│   └── app_test_config.h   # APP_TEST_MODE_*
Middlewares/
└── Third_Party/
    ├── FreeRTOS/
    ├── LwIP/
    ├── mbedTLS/
    └── LVGL/
```

## 编译与产物

```bash
# CubeMX 生成 Makefile 工程
make -j$(nproc)

# 或 CMake / IAR / Keil 依工程类型
```

产物：`build/firmware.elf`、`build/firmware.map`（路径因工程而异）

## Crash 定位（addr2line / map）

```bash
# HardFault 日志中的 PC
arm-none-eabi-addr2line -pfiaC -e build/firmware.elf 0x08001234

# .map 按 size 排序找大模块
arm-none-eabi-nm --print-size --size-sort build/firmware.elf | tail -20
```

| 日志关键词 | 优先对照 |
|-----------|----------|
| HardFault @ WssTask | 栈 words 不足 — [mbedtls_wss_memory.txt](../prompts/mbedtls_wss_memory.txt) |
| `configASSERT` + malloc | 增大 `configTOTAL_HEAP_SIZE` / LwIP `MEM_SIZE` |
| I2S 回调卡死 | 完整版 `examples/bad_isr_blocking.c` |
| 界面 frozen | [deadlock_lock_order.txt](../prompts/deadlock_lock_order.txt) |

## MVP 集成要点（STM32 特有）

1. **栈单位**：`xTaskCreate` 用 **words**（1536 words = 6144 bytes）；`osThreadNew` 用 **bytes** — 输出时必须标注
2. **WSS 栈**：mbedTLS 握手 `usStackDepth` ≥ 1536 words，建议实测水位
3. **LwIP 与 FreeRTOS 共堆**：WSS + cJSON + LVGL 并存时 `configTOTAL_HEAP_SIZE` ≥ 32KB 常见
4. **D-Cache**：F4/F7/H7 DMA 缓冲 Non-Cacheable 或手动 clean/invalidate
5. **事件总线**：[queue_event_bus.txt](../prompts/queue_event_bus.txt)
6. **HAL 回调 = ISR 上下文**：仅 `*FromISR` — [freertos_sync_primitives.txt](../prompts/freertos_sync_primitives.txt)

## 共享引擎：prompt + 云端 uplink（C10）

STM32 常见：HAL I2S 双工 + 软件 AEC 或外置 codec。

| 项 | STM32 做法 |
|----|------------|
| prompt 播放 | I2S TX DMA；结束须 `HAL_I2S_Transmit_DMA` stop + 等 TC |
| 开麦 | TX idle 后再开 RX tap / uplink；遵守 C10.4 串行 |
| Cache | F4/F7/H7 DMA 缓冲 Non-Cacheable 或 clean/invalidate（C4 + C10） |
| settle | 80–150ms；确认 AEC ref 缓冲不再写入 |
| 诊断 | 对比两轮 peak；HardFault 查栈 words |

深细节 → [voice_asr_uplink.txt](../prompts/voice_asr_uplink.txt)

## 快速参考路径

```
FreeRTOSConfig.h:     Core/Inc/FreeRTOSConfig.h
lwipopts.h:           LWIP/Target/lwipopts.h
mbedtls_config.h:     Middlewares/Third_Party/mbedTLS/include/mbedtls_config.h
lv_conf.h:            Middlewares/Third_Party/LVGL/lv_conf.h
stm32xx_hal_conf.h:   Core/Inc/stm32xx_hal_conf.h
```

## SDK 全景扫描

裁剪前必须完成以下扫描（C6.2）：

| 扫描项 | 命令/方法 | 输出 |
|--------|----------|------|
| CubeMX 模块列表 | Project Manager → Advanced Settings | 已启用 HAL 模块清单 |
| Middlewares 列表 | `ls Middlewares/` | LwIP / mbedTLS / FreeRTOS / LVGL 版本 |
| HAL 驱动列表 | `Drivers/STM32xx_HAL_Driver/Inc/` | 已用 HAL 头文件清单 |
| 链接脚本 | `STM32xx_FLASH.ld` | Flash/RAM 分区 |
| .map 文件 | `build/*.map` | 各段占用 |

## 内存 / Flash 典型值

| 芯片 | Flash | RAM | PSRAM | 说明 |
|------|-------|-----|-------|------|
| STM32F407 | 1MB | 192KB | 无 | 主流 Cortex-M4 |
| STM32F746 | 1MB | 320KB | 无 | Cortex-M7 + LCD |
| STM32H743 | 2MB | 1MB | 无 | 高性能 Cortex-M7 |
| STM32U575 | 2MB | 780KB | 无 | 低功耗 Cortex-M33 |
| STM32N6 | 4MB | 4.5MB | 64MB | NPU + 大 RAM |

## app_config.h 关键宏

```c
/* FreeRTOSConfig.h 关键配置 */
#define configTOTAL_HEAP_SIZE        (32*1024)   /* 根据 TLS+LVGL 调整 */
#define configMAX_PRIORITIES          56
#define configMINIMAL_STACK_SIZE      128         /* words */
#define configCHECK_FOR_STACK_OVERFLOW 2          /* 启用栈溢出检测 */

/* HAL 配置 */
#define HSE_VALUE                   8000000       /* 外部晶振频率 */
#define TICK_INT_PRIORITY           15            /* SysTick 优先级 */
```

## 平台特定 Crash 模式

| 症状 | 可能原因 | 诊断 |
|------|----------|------|
| HardFault @ 0x00000000 | NULL 函数指针 | 查 LR/PC 寄存器 |
| Usage Fault (UNALIGNED) | 未对齐访问 | 检查 packed struct |
| Bus Fault (BFAR) | 非法地址访问 | 查 BFAR 寄存器 |
| MemManage (DACCVIOL) | 栈溢出/MPU 违规 | 查 MSP/PSP |
| WDT Reset | 任务卡死 | 查 IWDG 配置 |
| 偶发 HardFault | 优先级反转/栈溢出 | 启用 `configCHECK_FOR_STACK_OVERFLOW` |

### addr2line

```bash
arm-none-eabi-addr2line -e build/Project.elf -a <address>
arm-none-eabi-objdump -d build/Project.elf | grep -A5 <address>
```

## Flash 加密 / 安全启动

STM32 支持 RDP（Read-Out Protection）和 PCROP（Proprietary Code Readout Protection）：

| 保护级别 | RDP | 说明 |
|----------|-----|------|
| Level 0 | 0xAA | 无保护 |
| Level 1 | 0xCC | 读保护，JTAG 受限 |
| Level 2 | 0xDD | 不可逆，完全禁用调试 |

```c
/* HAL 配置 RDP */
HAL_FLASH_OB_Unlock();
FLASH_OBProgramInitTypeDef ob;
ob.OptionType = OPTIONBYTE_RDP;
ob.RDPLevel = OB_RDP_LEVEL_1;
HAL_FLASHEx_OBProgram(&ob);
HAL_FLASH_OB_Launch();
```
