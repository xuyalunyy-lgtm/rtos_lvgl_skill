/* fixture: ISR 仅用 FromISR — 期望 isr_safety_checker 通过 */
#include "FreeRTOS.h"
#include "task.h"

static TaskHandle_t s_hdl;

void HAL_I2S_RxCpltCallback(void)
{
    BaseType_t woken = pdFALSE;
    vTaskNotifyGiveFromISR(s_hdl, &woken);
    portYIELD_FROM_ISR(woken);
}
