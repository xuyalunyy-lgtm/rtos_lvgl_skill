/**
 * @file bad_boot_sequence.c
 * @brief C8 启动顺序 self-test 反例 fixture
 */
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "esp_event.h"
#include "esp_log.h"

static QueueHandle_t s_event_queue;

/* 反例 C8.1: 网络回调在 Queue 创建之前注册 */
void app_main(void)
{
    /* C8.1 违规: 回调先于 Queue */
    esp_event_handler_register(IP_EVENT, IP_EVENT_STA_GOT_IP, NULL, NULL);

    /* Queue 在回调之后才创建 */
    s_event_queue = xQueueCreate(8, sizeof(int));
}
