/* fixture: ISR 阻塞 — 期望 isr_safety_checker 失败 */
#include "FreeRTOS.h"
#include "semphr.h"

static SemaphoreHandle_t s_sem;

void HAL_I2S_RxHalfCpltCallback(void)
{
    xSemaphoreTake(s_sem, portMAX_DELAY);
}
