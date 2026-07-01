#include "FreeRTOS.h"
#include "queue.h"
#include "semphr.h"

static QueueHandle_t s_q;
static SemaphoreHandle_t s_mutex;

void bad_timeout_budget(void)
{
    int evt = 0;

    xQueueReceive(s_q, &evt, portMAX_DELAY);
    xSemaphoreTake(s_mutex, WAIT_FOREVER);
}

int bad_socket_wait(int sock, char *buf)
{
    return recv(sock, buf, sizeof(buf), 0);
}
