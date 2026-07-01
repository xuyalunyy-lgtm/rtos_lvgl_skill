/**
 * @file good_priority.c
 * @brief C15 优先级 self-test 正例 fixture
 */
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semaphore.h"

/* 正例: 使用 mutex（优先级继承）保护共享资源 */
static SemaphoreHandle_t s_mutex;

void good_priority_init(void)
{
    s_mutex = xSemaphoreCreateMutex();
}

void good_priority_access(void)
{
    if (xSemaphoreTake(s_mutex, pdMS_TO_TICKS(100)) == pdTRUE) {
        /* 访问共享资源 */
        xSemaphoreGive(s_mutex);
    }
}
