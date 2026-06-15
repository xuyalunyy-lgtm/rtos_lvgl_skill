/**
 * @file bad_isr_blocking.c
 * @brief ❌ 反例：ISR / HAL 回调中使用阻塞 FreeRTOS API — 严禁模仿
 *
 * 文件归属: audio_capture.c / stm32xx_it.c（错误写法示范）
 *
 * 典型后果:
 *   - 系统整体卡死（ISR 永不返回，调度器停摆）
 *   - 音频爆音、DMA 丢帧
 *   - configASSERT 触发或 HardFault
 *
 * 正确做法: 见 prompts/audio_dma_pingpong.txt
 *   → ISR 仅用 *FromISR API + portYIELD_FROM_ISR
 *   → 耗时处理放 audio_process_task
 */

#include "FreeRTOS.h"
#include "task.h"
#include "semphr.h"
#include "queue.h"
#include "cJSON.h"
#include <stdio.h>

/* ── 全局资源 ─────────────────────────────────────────── */

static SemaphoreHandle_t s_dma_done_sem  = NULL;
static QueueHandle_t     s_audio_queue     = NULL;
static TaskHandle_t      s_audio_task_hdl  = NULL;

/* ══════════════════════════════════════════════════════════
 *  ❌ 错误 1：DMA 完成回调中使用阻塞信号量
 * ══════════════════════════════════════════════════════════ */

void HAL_I2S_RxCpltCallback(I2S_HandleTypeDef *hi2s)
{
    (void)hi2s;

    /* ❌ 致命：ISR 中调用非 FromISR 版本，且无限等待 */
    xSemaphoreGive(s_dma_done_sem);   /* 应使用 xSemaphoreGiveFromISR */

    /* ❌ 致命：在 ISR 中阻塞等待 */
    xSemaphoreTake(s_dma_done_sem, portMAX_DELAY);  /* 系统永远卡死 */
}

/* ══════════════════════════════════════════════════════════
 *  ❌ 错误 2：ISR 中 vTaskDelay / 任务通知误用
 * ══════════════════════════════════════════════════════════ */

void HAL_I2S_RxHalfCpltCallback(I2S_HandleTypeDef *hi2s)
{
    (void)hi2s;

    /* ❌ 致命：ISR 中禁止 vTaskDelay */
    vTaskDelay(pdMS_TO_TICKS(1));

    /* ❌ 错误：未使用 FromISR 版本，未调用 portYIELD_FROM_ISR */
    xTaskNotify(s_audio_task_hdl, 0x01, eSetBits);
}

/* ══════════════════════════════════════════════════════════
 *  ❌ 错误 3：ISR 中向 Queue 阻塞发送
 * ══════════════════════════════════════════════════════════ */

void DMA1_Stream3_IRQHandler(void)
{
    int16_t audio_sample = 0;

    /* ❌ 致命：ISR 中用非 FromISR 版本 + 非零超时 */
    xQueueSend(s_audio_queue, &audio_sample, pdMS_TO_TICKS(10));

    /* ❌ 致命：ISR 中无限等待队列空间 */
    xQueueSend(s_audio_queue, &audio_sample, portMAX_DELAY);
}

/* ══════════════════════════════════════════════════════════
 *  ❌ 错误 4：ISR 中执行耗时操作
 * ══════════════════════════════════════════════════════════ */

void HAL_I2S_RxCpltCallback_v2(I2S_HandleTypeDef *hi2s)
{
    (void)hi2s;
    char json_stub[] = "{\"level\":80}";

    /* ❌ 致命：ISR 中动态分配 */
    int16_t *buf = (int16_t *)pvPortMalloc(512);
    if (buf == NULL) {
        return;
    }

    /* ❌ 致命：ISR 中 printf（依赖锁，可能阻塞） */
    printf("DMA complete, samples=%d\n", 256);

    /* ❌ 致命：ISR 中 JSON 解析（malloc 链、耗时长） */
    cJSON *root = cJSON_Parse(json_stub);
    if (root != NULL) {
        cJSON_Delete(root);
    }

    vPortFree(buf);
}

/* ══════════════════════════════════════════════════════════
 *  ❌ 错误 5：ISR 中调用带互斥锁的 LVGL / 网络 API
 * ══════════════════════════════════════════════════════════ */

extern SemaphoreHandle_t g_lvgl_mutex;

void HAL_GPIO_EXTI_Callback(uint16_t GPIO_Pin)
{
    (void)GPIO_Pin;

    /* ❌ 致命：ISR 中获取互斥锁，若锁被 LVGL 任务持有则死锁 */
    xSemaphoreTake(g_lvgl_mutex, portMAX_DELAY);
    /* ... 操作 UI ... */
    xSemaphoreGive(g_lvgl_mutex);
}

/* ══════════════════════════════════════════════════════════
 *  ✅ 正确写法对照（同一 ISR 的修复版）
 * ══════════════════════════════════════════════════════════ */

void HAL_I2S_RxCpltCallback_FIXED(I2S_HandleTypeDef *hi2s)
{
    (void)hi2s;
    BaseType_t xHigherPriorityTaskWoken = pdFALSE;

    if (s_audio_task_hdl != NULL) {
        xTaskNotifyFromISR(s_audio_task_hdl, 0x02, eSetBits, &xHigherPriorityTaskWoken);
    }

    portYIELD_FROM_ISR(xHigherPriorityTaskWoken);
}

/*
 * ══════════════════════════════════════════════════════════
 *  修复清单（Code Review 时逐条对照）
 * ══════════════════════════════════════════════════════════
 *
 *  [ ] 所有 ISR/HAL_CpltCallback 中无 vTaskDelay / portMAX_DELAY
 *  [ ] 信号量：xSemaphoreGiveFromISR + portYIELD_FROM_ISR
 *  [ ] 队列：xQueueSendFromISR（超时参数只能是 0）
 *  [ ] 任务通知：xTaskNotifyFromISR + portYIELD_FROM_ISR
 *  [ ] ISR 中无 malloc/printf/cJSON_Parse/LVGL 调用
 *  [ ] 耗时处理（解码、JSON、UI）全部移到 audio_process_task
 *  [ ] 参照 prompts/audio_dma_pingpong.txt 方案 A
 */
