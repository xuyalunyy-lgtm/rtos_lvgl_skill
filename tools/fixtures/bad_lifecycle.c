/**
 * @file bad_lifecycle.c
 * @brief C33 生命周期对称 self-test 反例 fixture
 */
#include "freertos/FreeRTOS.h"
#include "freertos/semaphore.h"
#include "freertos/queue.h"

static SemaphoreHandle_t s_mutex;
static QueueHandle_t s_queue;

/* 反例 C33.2: create 后无 delete */
void bad_lifecycle_init(void)
{
    s_mutex = xSemaphoreCreateMutex();
    s_queue = xQueueCreate(8, sizeof(int));
}

/* 反例: 没有 deinit 函数，资源泄漏 */
void bad_lifecycle_do_work(void)
{
    if (s_mutex != NULL && xSemaphoreTake(s_mutex, pdMS_TO_TICKS(100)) == 1) {
        xSemaphoreGive(s_mutex);
    }
}
