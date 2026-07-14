// Edge case: Correct ISR usage with FromISR APIs
// Tests that isr_safety_checker does not false-positive on correct FromISR patterns
#include "FreeRTOS.h"
#include "task.h"
#include "semphr.h"

static SemaphoreHandle_t data_sem;
static TaskHandle_t processing_task;

// Correct task: waits for ISR notification (not an ISR, uses portMAX_DELAY correctly)
void data_processing_task(void *param)
{
    (void)param;
    while (1) {
        ulTaskNotifyTake(pdTRUE, pdMS_TO_TICKS(1000));
        // process data
    }
}

// Correct ISR: uses FromISR API + portYIELD_FROM_ISR
void DMA1_Stream0_IRQHandler(void)
{
    BaseType_t xHigherPriorityTaskWoken = pdFALSE;

    // Clear interrupt flag
    volatile uint32_t *status = (volatile uint32_t *)0x40026000;
    *status = 0;

    // Notify processing task using FromISR API
    xSemaphoreGiveFromISR(data_sem, &xHigherPriorityTaskWoken);

    // Yield if higher priority task was woken
    portYIELD_FROM_ISR(xHigherPriorityTaskWoken);
}

// Correct ISR: uses TaskNotifyFromISR
void UART_IRQHandler(void)
{
    BaseType_t xHigherPriorityTaskWoken = pdFALSE;

    // Read data register
    volatile uint32_t *data_reg = (volatile uint32_t *)0x40011000;
    (void)*data_reg;

    // Notify task
    xTaskNotifyFromISR(processing_task, 0, eNoAction, &xHigherPriorityTaskWoken);
    portYIELD_FROM_ISR(xHigherPriorityTaskWoken);
}
