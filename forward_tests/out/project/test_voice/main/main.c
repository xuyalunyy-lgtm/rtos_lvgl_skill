/**
 * @file main.c
 * @brief test_voice main entry
 *
 * Constraints: C1, C2, C3, C4, C7, C8, C9, C11, ... (+2 more)
 */

#include <stdio.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"
#include "esp_log.h"

static const char *TAG = "test_voice";

/* ── 队列（C8.1: 先于回调创建）── */
static QueueHandle_t s_ui_cmd_queue = NULL;
static QueueHandle_t s_audio_frame_queue = NULL;

/* ── 任务句柄（C33: 生命周期对称）── */
static TaskHandle_t s_main_task_handle = NULL;
static TaskHandle_t s_ui_task_handle = NULL;
static TaskHandle_t s_audio_task_handle = NULL;
static TaskHandle_t s_network_task_handle = NULL;
static TaskHandle_t s_ota_task_handle = NULL;

/* C8.1: Queue before callback */
static esp_err_t init_communication(void)
{
    s_ui_cmd_queue = xQueueCreate(8, sizeof(int));
    if (s_ui_cmd_queue == NULL) {
        ESP_LOGE(TAG, "Failed to create ui_cmd_queue");
        return ESP_FAIL;
    }
    s_audio_frame_queue = xQueueCreate(8, sizeof(int));
    if (s_audio_frame_queue == NULL) {
        ESP_LOGE(TAG, "Failed to create audio_frame_queue");
        return ESP_FAIL;
    }
    ESP_LOGI(TAG, "Communication initialized");
    return ESP_OK;
}

void app_main(void)
{
    ESP_LOGI(TAG, "test_voice starting...");

    esp_err_t err = init_communication();
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Communication init failed");
        return;
    }

    ESP_LOGI(TAG, "test_voice initialized successfully");
}