/* fixture: bounded lock budget and explicit lock order - expect pass */

#include <stdint.h>

typedef void * SemaphoreHandle_t;
typedef int BaseType_t;
#define pdTRUE 1
#define pdFALSE 0
#define pdMS_TO_TICKS(x) (x)

extern BaseType_t xSemaphoreTake(SemaphoreHandle_t sem, uint32_t ticks);
extern void xSemaphoreGive(SemaphoreHandle_t sem);
extern void vTaskNotifyGiveFromISR(void *task, BaseType_t *woken);
extern void portYIELD_FROM_ISR(BaseType_t woken);

static SemaphoreHandle_t s_state_mutex;
static SemaphoreHandle_t s_net_mutex;
static uint32_t s_state;

int state_update(uint32_t value)
{
    /* lock_budget: max_hold_us=50; no IO while locked */
    if (xSemaphoreTake(s_state_mutex, pdMS_TO_TICKS(2)) != pdTRUE) {
        return -1;
    }

    s_state = value;
    xSemaphoreGive(s_state_mutex);
    return 0;
}

int update_net_state(uint32_t value)
{
    /* lock_order: NET -> STATE, both bounded */
    if (xSemaphoreTake(s_net_mutex, pdMS_TO_TICKS(3)) != pdTRUE) {
        return -1;
    }
    if (xSemaphoreTake(s_state_mutex, pdMS_TO_TICKS(2)) != pdTRUE) {
        xSemaphoreGive(s_net_mutex);
        return -2;
    }

    s_state = value;
    xSemaphoreGive(s_state_mutex);
    xSemaphoreGive(s_net_mutex);
    return 0;
}

void DMA_IRQHandler(void)
{
    BaseType_t woken = pdFALSE;
    vTaskNotifyGiveFromISR(0, &woken);
    portYIELD_FROM_ISR(woken);
}
