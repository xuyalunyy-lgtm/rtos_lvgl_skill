/* fixture: unbounded locks and priority inversion risks - expect fail */

#include <stdint.h>

typedef void * SemaphoreHandle_t;
#define portMAX_DELAY 0xffffffffu

extern int xSemaphoreTake(SemaphoreHandle_t sem, uint32_t ticks);
extern void xSemaphoreGive(SemaphoreHandle_t sem);
extern SemaphoreHandle_t xSemaphoreCreateBinary(void);
extern int mbedtls_ssl_read(void *ssl, unsigned char *buf, unsigned long len);

static SemaphoreHandle_t s_config_mutex;
static SemaphoreHandle_t s_state_mutex;
static SemaphoreHandle_t s_shared_lock;
static unsigned char s_rx[128];

void init_locks(void)
{
    s_shared_lock = xSemaphoreCreateBinary();
}

int network_config_update(void *ssl)
{
    xSemaphoreTake(s_config_mutex, portMAX_DELAY);
    mbedtls_ssl_read(ssl, s_rx, sizeof(s_rx));
    xSemaphoreTake(s_state_mutex, portMAX_DELAY);

    xSemaphoreGive(s_state_mutex);
    xSemaphoreGive(s_config_mutex);
    return 0;
}

void HAL_DMA_RxCpltCallback(void)
{
    xSemaphoreTake(s_state_mutex, portMAX_DELAY);
    xSemaphoreGive(s_state_mutex);
}
