/* fixture: long IRQ-masked work - expect fail */

#include <stdint.h>

extern void taskENTER_CRITICAL(void);
extern void taskEXIT_CRITICAL(void);
extern void __disable_irq(void);
extern void __enable_irq(void);
extern void vTaskDelay(uint32_t ticks);
extern void *pvPortMalloc(unsigned long size);
extern void memcpy(void *dst, const void *src, unsigned long len);
extern int printf(const char *fmt, ...);

static uint8_t s_buf[128];
static volatile int s_ready;

int update_shared_bad(const uint8_t *src)
{
    taskENTER_CRITICAL();
    if (!src) {
        return -1;
    }
    void *tmp = pvPortMalloc(128);
    memcpy(s_buf, src, 128);
    printf("updated\n");
    vTaskDelay(1);
    while (!s_ready) {
    }
    taskEXIT_CRITICAL();
    return tmp ? 0 : -2;
}

void HAL_TIM_PeriodElapsedCallback(void)
{
    __disable_irq();
    s_ready++;
    __enable_irq();
}
