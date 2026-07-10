# STM32 / CubeMX + HAL Platform Guide

Agent reads this file when confirming target platform is STM32 series.

## Key Differences Overview

| Item | STM32 + CubeMX Convention | Note |
|------|---------------------|------|
| Task priority | CMSIS-RTOS v1/v2: `osPriorityXxx`; native FreeRTOS: **数字越大越高**（0 最低）。`osPriorityXxx` 是抽象枚举，内部映射到 FreeRTOS 高优先级数值 | 所有平台统一：FreeRTOS Task 优先级数字越大越高 |
| Task creation | CubeMX generates `MX_FREERTOS_Init()` + `osThreadNew` / `xTaskCreate` | Prefer configuring in CubeMX before manual changes |
| Heap memory | `pvPortMalloc` / `configTOTAL_HEAP_SIZE` | Default heap is small, TLS+LVGL need to increase to 32KB+ |
| Stack unit | `xTaskCreate`'s `usStackDepth` unit is **word** (32-bit = 4 bytes) | 2048 words = 8192 bytes |
| Network | LwIP + mbedTLS (manual integration or Mongoose) | WSS need to assemble TLS layer yourself |
| HAL callback | `HAL_XXX_CpltCallback` in interrupt context | Must use `*FromISR` API |

## Recommended Task Priority (CMSIS-RTOS v2 / FreeRTOS)

```c
/* FreeRTOS: 数字越大越高优先级。osPriorityXxx 是 CMSIS-RTOS 抽象枚举，
   内部映射到 FreeRTOS 的高数值（如 osPriorityRealtime → 24）。
   注意：Cortex-M NVIC 中断优先级是数字越小越高，与 Task 优先级方向相反。 */
#define AUDIO_TASK_PRIO      (osPriorityRealtime)    /* highest — maps to 24 */
#define WSS_TASK_PRIO        (osPriorityAboveNormal) /* above normal */
#define LVGL_TASK_PRIO       (osPriorityNormal)
#define PRESENTER_TASK_PRIO  (osPriorityBelowNormal)
```

CubeMX generated `osPriority_t` mapping:

| CMSIS enum | Value | Applicable |
|-----------|------|------|
| `osPriorityRealtime` | 48+ | I2S DMA audio |
| `osPriorityAboveNormal` | 32+ | WSS + TLS |
| `osPriorityNormal` | 24 | LVGL |
| `osPriorityBelowNormal` | 16 | Presenter |

When outputting priority table **provide both CMSIS enum and relative order**.

## Task Creation Template

```c
/* CubeMX generated osThreadAttr_t method (recommended) */
const osThreadAttr_t audio_task_attributes = {
    .name       = "audio",
    .stack_size = 1024 * 4,   /* bytes, CMSIS uses bytes not words */
    .priority   = (osPriority_t) osPriorityRealtime,
};
osThreadId_t audio_task_hdl = osThreadNew(audio_process_task, NULL, &audio_task_attributes);

/* native FreeRTOS method (manually written Model task) */
xTaskCreate(wss_task, "wss", 1536, NULL, WSS_TASK_PRIO, &s_wss_hdl);
/* Note: 1536 = words → 6144 bytes */
```

**Stack unit pitfall**: `xTaskCreate` uses **words**, `osThreadNew` uses **bytes**. Must annotate when mixing.

## WSS / Network (Model layer)

STM32 WSS typically combines: LwIP `raw`/`netconn` + mbedTLS + manual WebSocket frame parsing, or third-party library (Mongoose, wolfSSL).

```c
/* Model task main loop — do not use lv_obj_* */
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

- mbedTLS `mbedtls_ssl_handshake` stack overhead is large, `usStackDepth` ≥ 1536 words.
- LwIP shares heap with FreeRTOS, `configTOTAL_HEAP_SIZE` recommended ≥ 32768.

## LVGL Integration (STM32)

- Driver: ST7789/SPI, RGB parallel, LTDC (F4/F7/H7)
- `lv_timer_handler()` in dedicated `lvgl_task`, with `vTaskDelay(5)` or timer interrupt
- Double buffering: `lv_disp_draw_buf_init(&draw_buf, buf1, buf2, LV_HOR_RES * 10)`
- Cross-task refresh: `lv_async_call()` or `g_lvgl_mutex` (see prompts/lvgl_thread_safety.txt)

## I2S / DMA Audio

```c
/* CubeMX configure I2S + DMA Circular Mode */
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

- DMA buffer placed in `.dma_buffer` section or `__attribute__((aligned(4)))`
- F4/F7: Note D-Cache coherency, set DMA buffer region as Non-Cacheable or manual `SCB_CleanInvalidateDCache`

## FreeRTOSConfig.h Key Items

```c
#define configTOTAL_HEAP_SIZE       ((size_t)(32 * 1024))
#define configCHECK_FOR_STACK_OVERFLOW  2   /* method 2: Canary */
#define configUSE_MALLOC_FAILED_HOOK    1
#define configASSERT(x)  if((x)==0){taskDISABLE_INTERRUPTS();for(;;);}
#define configMINIMAL_STACK_SIZE        ((uint16_t)128)
```

## Common Crash Diagnosis

| Symptom | STM32 specific cause |
|------|---------------|
| HardFault @ `BX r3` | Wild pointer, stack overflow, FPU context not saved |
| `configASSERT` in `prvCheckTasksWaitingTermination` | Heap exhausted, `pvPortMalloc` failure |
| LTDC screen corruption | DMA2D and CPU memory access race condition, Cache not invalidated |
| I2S audio pop/click | HAL callback `xSemaphoreTake` blocking (see bad_isr_blocking.c) |
| LwIP `ERR_MEM` | `MEM_SIZE` / `configTOTAL_HEAP_SIZE` insufficient |

## SDK Deep Trimming (STM32 + CubeMX)

> **The following are only candidates**, must confirm with product requirements questionnaire before disabling; do not apply without asking the user.

### Configuration Entry

- CubeMX `.ioc` → cancel unused IP (USB/SDIO/CAN/ETH etc.)
- `FreeRTOSConfig.h` / `lwipopts.h` / `mbedtls_config.h`

### Priority Disable Items

| Category | Location | Action when unused |
|------|------|-----------|
| Peripheral IP | CubeMX Pinout | Disable unused UART/SPI/I2C/USB/SDIO |
| HAL Module | `stm32xx_hal_conf.h` | `#undef HAL_XXX_MODULE_ENABLED` |
| LwIP | `lwipopts.h` | Reduce `MEM_SIZE`, `MEMP_NUM_PBUF`, `TCPIP_THREAD_STACKSIZE` |
| mbedTLS | `mbedtls_config.h` | Keep only WSS required cipher + disable debug |
| LVGL | `lv_conf.h` | Disable unused widget, demo, `LV_USE_FONT_SUBPX` etc. |
| FreeRTOS | `FreeRTOSConfig.h` | Reduce `configTOTAL_HEAP_SIZE`, disable trace |
| Middlewares | Project directory | Delete if no BT `STM32_WPAN` etc.

### Task Trimming

```
Core/Src/freertos.c   → delete unused CubeMX generated osThread
MX_LWIP_Init()        → don't initialize at all if no network
```

### STM32 Trimming Verification

- Check `.map` file after build: `arm-none-eabi-nm --print-size --size-sort firmware.elf`
- Heap peak: `xPortGetMinimumEverFreeHeapSize()`
- Stack watermark: `uxTaskGetStackHighWaterMark()` test per task

## File Ownership Convention (CubeMX Project)

```
Core/
├── Src/
│   ├── main.c              # HAL_Init → osKernelStart
│   ├── freertos.c          # CubeMX generated, task definition entry
│   ├── app_presenter.c     # Presenter — Looper
│   ├── network_wss_task.c  # Model — WSS + mbedTLS
│   ├── ui_view_manager.c   # View — LVGL
│   └── audio_capture.c     # Model — I2S DMA
├── Inc/
│   ├── app_mvp.h           # net_evt_t / ui_evt_t (see examples/app_mvp.h)
│   └── app_test_config.h   # APP_TEST_MODE_*
Middlewares/
└── Third_Party/
    ├── FreeRTOS/
    ├── LwIP/
    ├── mbedTLS/
    └── LVGL/
```

## Build and Artifacts

```bash
# CubeMX generates Makefile project
make -j$(nproc)

# or CMake / IAR / Keil depending on project type
```

Artifacts: `build/firmware.elf`, `build/firmware.map` (path varies by project)

## Crash Diagnosis (addr2line / map)

```bash
# PC in HardFault log
arm-none-eabi-addr2line -pfiaC -e build/firmware.elf 0x08001234

# .map sort by size to find large modules
arm-none-eabi-nm --print-size --size-sort build/firmware.elf | tail -20
```

| Log keyword | First check against |
|-----------|----------|
| HardFault @ WssTask | Insufficient stack words — [mbedtls_wss_memory.txt](../prompts/mbedtls_wss_memory.txt) |
| `configASSERT` + malloc | Increase `configTOTAL_HEAP_SIZE` / LwIP `MEM_SIZE` |
| I2S callback stuck | [bad_isr_blocking.c](../examples/bad_isr_blocking.c) |
| UI frozen | [deadlock_lock_order.txt](../prompts/deadlock_lock_order.txt) |

## MVP Integration Key Points (STM32 specific)

1. **Stack unit**: `xTaskCreate` uses **words** (1536 words = 6144 bytes); `osThreadNew` uses **bytes** — must annotate when outputting
2. **WSS stack**: mbedTLS handshake `usStackDepth` ≥ 1536 words, recommend testing watermark
3. **LwIP shared heap with FreeRTOS**: WSS + cJSON + LVGL coexisting `configTOTAL_HEAP_SIZE` ≥ 32KB common
4. **D-Cache**: F4/F7/H7 DMA buffer Non-Cacheable or manual clean/invalidate
5. **Event bus**: [queue_event_bus.txt](../prompts/queue_event_bus.txt)
6. **HAL callback = ISR context**: Only `*FromISR` — [freertos_sync_primitives.txt](../prompts/freertos_sync_primitives.txt)

## Shared Engine: prompt + cloud uplink (C10)

STM32 common: HAL I2S duplex + software AEC or external codec.

| Item | STM32 Approach |
|----|------------|
| prompt playback | I2S TX DMA; must stop `HAL_I2S_Transmit_DMA` + wait for TC on end |
| Enable mic | Enable RX tap / uplink after TX idle; follow C10.4 serialization |
| Cache | F4/F7/H7 DMA buffer Non-Cacheable or clean/invalidate (C4 + C10) |
| settle | 80–150ms; confirm AEC ref buffer no longer being written |
| Diagnostics | Compare peaks across two rounds; HardFault check stack words |

For details → [voice_asr_uplink.txt](../prompts/voice_asr_uplink.txt)

## Quick Reference Paths

```
FreeRTOSConfig.h:     Core/Inc/FreeRTOSConfig.h
lwipopts.h:           LWIP/Target/lwipopts.h
mbedtls_config.h:     Middlewares/Third_Party/mbedTLS/include/mbedtls_config.h
lv_conf.h:            Middlewares/Third_Party/LVGL/lv_conf.h
stm32xx_hal_conf.h:   Core/Inc/stm32xx_hal_conf.h
```

## SDK Full Scan

Must complete the following scan before trimming (C6.2):

| Scan Item | Command/Method | Output |
|--------|----------|------|
| CubeMX module list | Project Manager → Advanced Settings | Enabled HAL module list |
| Middlewares list | `ls Middlewares/` | LwIP / mbedTLS / FreeRTOS / LVGL version |
| HAL driver list | `Drivers/STM32xx_HAL_Driver/Inc/` | Used HAL header file list |
| Linker script | `STM32xx_FLASH.ld` | Flash/RAM partition |
| .map file | `build/*.map` | Section usage |

## Typical Memory / Flash Values

| Chip | Flash | RAM | PSRAM | Description |
|------|-------|-----|-------|------|
| STM32F407 | 1MB | 192KB | None | Mainstream Cortex-M4 |
| STM32F746 | 1MB | 320KB | None | Cortex-M7 + LCD |
| STM32H743 | 2MB | 1MB | None | High performance Cortex-M7 |
| STM32U575 | 2MB | 780KB | None | Low power Cortex-M33 |
| STM32N6 | 4MB | 4.5MB | 64MB | NPU + large RAM |

## app_config.h Key Macros

```c
/* FreeRTOSConfig.h key configuration */
#define configTOTAL_HEAP_SIZE        (32*1024)   /* adjust based on TLS+LVGL */
#define configMAX_PRIORITIES          56
#define configMINIMAL_STACK_SIZE      128         /* words */
#define configCHECK_FOR_STACK_OVERFLOW 2          /* enable stack overflow detection */

/* HAL configuration */
#define HSE_VALUE                   8000000       /* external crystal frequency */
#define TICK_INT_PRIORITY           15            /* SysTick priority */
```

## Platform-Specific Crash Patterns

| Symptom | Possible Cause | Diagnosis |
|------|----------|------|
| HardFault @ 0x00000000 | NULL function pointer | Check LR/PC register |
| Usage Fault (UNALIGNED) | Unaligned access | Check packed struct |
| Bus Fault (BFAR) | Illegal address access | Check BFAR register |
| MemManage (DACCVIOL) | Stack overflow/MPU violation | Check MSP/PSP |
| WDT Reset | Task stuck | Check IWDG configuration |
| Intermittent HardFault | Priority inversion/stack overflow | Enable `configCHECK_FOR_STACK_OVERFLOW` |

### addr2line

```bash
arm-none-eabi-addr2line -e build/Project.elf -a <address>
arm-none-eabi-objdump -d build/Project.elf | grep -A5 <address>
```

## Encryption / Secure Boot

STM32 supports RDP (Read-Out Protection) and PCROP (Proprietary Code Readout Protection):

| Protection Level | RDP | Description |
|----------|-----|------|
| Level 0 | 0xAA | No protection |
| Level 1 | 0xCC | Read protection, JTAG restricted |
| Level 2 | 0xDD | Irreversible, completely disables debug |

```c
/* HAL configure RDP */
HAL_FLASH_OB_Unlock();
FLASH_OBProgramInitTypeDef ob;
ob.OptionType = OPTIONBYTE_RDP;
ob.RDPLevel = OB_RDP_LEVEL_1;
HAL_FLASHEx_OBProgram(&ob);
HAL_FLASH_OB_Launch();
```
