/**
 * @file good_backpressure.c
 * @brief C37 背压 self-test 正例 fixture
 */
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"

static QueueHandle_t s_event_queue;

void good_send_event(int event)
{
    /* 正例: 有限超时，满队列不阻塞 */
    xQueueSend(s_event_queue, &event, pdMS_TO_TICKS(10));
}

void good_send_overwrite(int state)
{
    /* 正例: overwrite 模式，总是成功 */
    xQueueOverwrite(s_event_queue, &state);
}
