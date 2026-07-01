/**
 * @file good_boot_sequence.c
 * @brief C8 启动顺序 self-test 正例 fixture
 */
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"
#include "esp_event.h"
#include "esp_log.h"

static QueueHandle_t s_event_queue;

/* 正例: Queue 先创建，再注册网络回调 */
void app_main(void)
{
    /* C8.1: Queue 先于网络回调 */
    s_event_queue = xQueueCreate(8, sizeof(int));
    if (s_event_queue == NULL) {
        return;
    }

    /* C8.1: 网络回调在 Queue 之后注册 */
    esp_event_handler_register(IP_EVENT, IP_EVENT_STA_GOT_IP, NULL, NULL);
}
