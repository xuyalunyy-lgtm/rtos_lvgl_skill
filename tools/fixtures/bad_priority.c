/**
 * @file bad_priority.c
 * @brief C15 优先级 self-test 反例 fixture
 */
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semaphore.h"

static int s_shared_state = 0;
static SemaphoreHandle_t s_sem;

/* 反例 C15.2: Binary semaphore 用于共享资源保护 */
void bad_priority_init(void)
{
    s_sem = xSemaphoreCreateBinary();
    xSemaphoreGive(s_sem);
}

void bad_priority_access(void)
{
    /* C15.2 违规: binary semaphore 无优先级继承 */
    xSemaphoreTake(s_sem, portMAX_DELAY);
    s_shared_state++;
    xSemaphoreGive(s_sem);
}
