#include "FreeRTOS.h"
#include "queue.h"
#include "semphr.h"

static QueueHandle_t s_q;
static SemaphoreHandle_t s_mutex;

void good_timeout_budget(void)
{
    int evt = 0;

    if (xQueueReceive(s_q, &evt, pdMS_TO_TICKS(20)) != pdPASS) {
        return;
    }

    if (xSemaphoreTake(s_mutex, pdMS_TO_TICKS(10)) != pdPASS) {
        return;
    }
    xSemaphoreGive(s_mutex);
}

int good_socket_timeout(int sock, char *buf, unsigned len)
{
    struct timeval tv = { .tv_sec = 0, .tv_usec = 20000 };

    setsockopt(sock, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));
    return recv(sock, buf, len, 0);
}
