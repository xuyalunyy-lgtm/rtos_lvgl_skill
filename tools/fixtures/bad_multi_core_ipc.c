#include <stdint.h>

static volatile uint32_t g_sample_count;

void producer_task(void)
{
    g_sample_count++;
}

uint32_t consumer_task(void)
{
    return g_sample_count;
}
