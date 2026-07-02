/**
 * @file main.c
 * @brief Mini ESP32 project for RTOS model extraction testing
 */

#include <stdio.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"
#include "freertos/semphr.h"
#include "freertos/timers.h"
#include "esp_log.h"
#include "esp_wifi.h"

static const char *TAG = "mini_esp32";

/* ── IPC objects ── */
static QueueHandle_t s_sensor_queue = NULL;
static QueueHandle_t s_ui_cmd_queue = NULL;
static SemaphoreHandle_t s_config_mutex = NULL;
static SemaphoreHandle_t s_spi_done_sem = NULL;
static TimerHandle_t s_heartbeat_timer = NULL;

/* ── Task handles ── */
static TaskHandle_t s_sensor_task_hdl = NULL;
static TaskHandle_t s_ui_task_hdl = NULL;
static TaskHandle_t s_network_task_hdl = NULL;

/* ── Sensor task: period 100ms ── */
static void sensor_task(void *arg)
{
    ESP_LOGI(TAG, "sensor_task started");
    int data = 0;
    while (1) {
        data++;
        xQueueSend(s_sensor_queue, &data, pdMS_TO_TICKS(100));
        vTaskDelay(pdMS_TO_TICKS(100));
    }
}

/* ── UI task: event-driven ── */
static void ui_task(void *arg)
{
    ESP_LOGI(TAG, "ui_task started");
    int cmd;
    while (1) {
        if (xQueueReceive(s_ui_cmd_queue, &cmd, pdMS_TO_TICKS(500)) == pdTRUE) {
            ESP_LOGI(TAG, "ui cmd: %d", cmd);
        }
    }
}

/* ── Network task: event-driven ── */
static void network_task(void *arg)
{
    ESP_LOGI(TAG, "network_task started");
    while (1) {
        xSemaphoreTake(s_config_mutex, portMAX_DELAY);
        /* read config */
        xSemaphoreGive(s_config_mutex);
        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}

/* ── Heartbeat timer callback ── */
static void heartbeat_cb(TimerHandle_t timer)
{
    ESP_LOGI(TAG, "heartbeat");
}

void app_main(void)
{
    ESP_LOGI(TAG, "mini_esp32 starting");

    /* C8: Create IPC before tasks */
    s_sensor_queue = xQueueCreate(8, sizeof(int));
    s_ui_cmd_queue = xQueueCreate(4, sizeof(int));
    s_config_mutex = xSemaphoreCreateMutex();
    s_spi_done_sem = xSemaphoreCreateBinary();

    /* Create tasks */
    xTaskCreate(sensor_task, "sensor", 2048, NULL, 5, &s_sensor_task_hdl);
    xTaskCreate(ui_task, "ui", 4096, NULL, 3, &s_ui_task_hdl);
    xTaskCreate(network_task, "network", 4096, NULL, 4, &s_network_task_hdl);

    /* Create timer */
    s_heartbeat_timer = xTimerCreate("heartbeat", pdMS_TO_TICKS(1000),
                                     pdTRUE, NULL, heartbeat_cb);
    xTimerStart(s_heartbeat_timer, 0);

    ESP_LOGI(TAG, "mini_esp32 initialized");
}
