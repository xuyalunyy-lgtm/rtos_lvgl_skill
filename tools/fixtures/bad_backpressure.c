/**
 * @file bad_backpressure.c
 * @brief C37 背压 self-test 反例 fixture
 */
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"

static QueueHandle_t s_event_queue;

/* 反例 C37.2: portMAX_DELAY 无限等待 */
void bad_send_event(int event)
{
    xQueueSend(s_event_queue, &event, portMAX_DELAY);
}

/* 反例 C37.2: 无超时参数 */
void bad_send_no_timeout(int event)
{
    xQueueSend(s_event_queue, &event, portMAX_DELAY);
}
