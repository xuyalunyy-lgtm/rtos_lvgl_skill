// C34 good: hot path only does lightweight operations
#include "FreeRTOS.h"
#include "task.h"
#include "queue.h"

static volatile uint32_t frame_count = 0;
static QueueHandle_t event_q;

// LVGL flush callback — only enqueue, no heavy work
static void my_lvgl_flush(lv_display_t *disp, const lv_area_t *area, uint8_t *px_map)
{
    frame_count++;
    // Only notify, no malloc/printf/blocking
    xTaskNotifyGive(render_task_handle);
}

// DMA callback — only set flag
static void audio_dma_Callback(void *ctx)
{
    BaseType_t xHigherPriorityTaskWoken = pdFALSE;
    xTaskNotifyFromISR(audio_task_handle, 0, eNoAction, &xHigherPriorityTaskWoken);
    portYIELD_FROM_ISR(xHigherPriorityTaskWoken);
}

// ISR handler — only increment counter
void TIMER0_IRQHandler(void)
{
    volatile uint32_t *status_reg = (volatile uint32_t *)0x40000100;
    *status_reg = 0;  // clear interrupt
    frame_count++;
}
