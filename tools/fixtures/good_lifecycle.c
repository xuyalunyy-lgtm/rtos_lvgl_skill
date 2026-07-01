/**
 * @file good_lifecycle.c
 * @brief C33 生命周期对称 self-test 正例 fixture
 */
#include "freertos/FreeRTOS.h"
#include "freertos/semaphore.h"
#include "freertos/queue.h"

static SemaphoreHandle_t s_mutex;
static QueueHandle_t s_queue;

/* 正例: create/delete 对称 */
void good_lifecycle_init(void)
{
    s_mutex = xSemaphoreCreateMutex();
    s_queue = xQueueCreate(8, sizeof(int));
}

void good_lifecycle_deinit(void)
{
    if (s_mutex != NULL) {
        vSemaphoreDelete(s_mutex);
        s_mutex = NULL;
    }
    if (s_queue != NULL) {
        vQueueDelete(s_queue);
        s_queue = NULL;
    }
}
