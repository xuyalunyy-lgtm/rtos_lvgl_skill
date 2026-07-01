/* fixture: short bounded critical sections - expect pass */

#include <stdint.h>

extern void taskENTER_CRITICAL(void);
extern void taskEXIT_CRITICAL(void);
extern void vTaskNotifyGiveFromISR(void *task, int *woken);
extern void portYIELD_FROM_ISR(int woken);

static volatile uint32_t s_flags;
static volatile uint32_t s_count;

void set_flags(uint32_t mask)
{
    /* critical_budget: max_irq_off_us=3; register/state update only */
    taskENTER_CRITICAL();
    s_flags |= mask;
    s_count++;
    taskEXIT_CRITICAL();
}

void DMA_IRQHandler(void)
{
    int woken = 0;
    vTaskNotifyGiveFromISR(0, &woken);
    portYIELD_FROM_ISR(woken);
}
