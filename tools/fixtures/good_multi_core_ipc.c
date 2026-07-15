#include <stdint.h>

static volatile uint32_t g_sample_count;

void sample_task(void)
{
    portENTER_CRITICAL();
    g_sample_count++;
    portEXIT_CRITICAL();
}

uint32_t sample_count_get(void)
{
    uint32_t value;
    portENTER_CRITICAL();
    value = g_sample_count;
    portEXIT_CRITICAL();
    return value;
}
