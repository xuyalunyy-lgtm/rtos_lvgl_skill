/**
 * @file good_checked_return.c
 * @brief C12 错误处理正例：FreeRTOS API 返回值检查 + goto cleanup
 *
 * 约束覆盖：
 *   C12.1 — FreeRTOS API 返回值必须检查
 *   C12.2 — malloc 失败须有 fallback
 *   C12.4 — 多资源函数用 goto cleanup 统一释放
 */

#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"
#include "freertos/semaphore.h"
#include "esp_log.h"

static const char *TAG = "checked_return";

/**
 * @brief C12.1 + C12.4 — 多资源创建，统一 cleanup
 */
esp_err_t create_communication_infrastructure(QueueHandle_t *out_queue,
                                               SemaphoreHandle_t *out_mutex,
                                               TaskHandle_t *out_task)
{
    QueueHandle_t queue = NULL;
    SemaphoreHandle_t mutex = NULL;
    TaskHandle_t task = NULL;

    /* C12.1: 检查 xQueueCreate 返回值 */
    queue = xQueueCreate(8, sizeof(int));
    if (queue == NULL) {
        ESP_LOGE(TAG, "Failed to create queue");
        goto cleanup;
    }

    /* C12.1: 检查 xSemaphoreCreateMutex 返回值 */
    mutex = xSemaphoreCreateMutex();
    if (mutex == NULL) {
        ESP_LOGE(TAG, "Failed to create mutex");
        goto cleanup;
    }

    /* C12.1: 检查 xTaskCreate 返回值 */
    BaseType_t ret = xTaskCreate(
        NULL, /* task function placeholder */
        "comm_task",
        4096,
        NULL,
        5,
        &task
    );
    if (ret != pdPASS) {
        ESP_LOGE(TAG, "Failed to create task");
        goto cleanup;
    }

    /* 成功：输出资源 */
    *out_queue = queue;
    *out_mutex = mutex;
    *out_task = task;
    return ESP_OK;

cleanup:
    /* C12.4: 统一释放已创建的资源 */
    if (task != NULL) {
        vTaskDelete(task);
    }
    if (mutex != NULL) {
        vSemaphoreDelete(mutex);
    }
    if (queue != NULL) {
        vQueueDelete(queue);
    }
    return ESP_FAIL;
}

/**
 * @brief C12.2 — malloc 失败有 fallback
 */
esp_err_t allocate_buffer(size_t size, void **out_buf)
{
    void *buf = pvPortMalloc(size);
    if (buf == NULL) {
        ESP_LOGE(TAG, "Failed to allocate %d bytes", (int)size);
        *out_buf = NULL;
        return ESP_ERR_NO_MEM; /* C12.2: 返回错误码，不崩溃 */
    }
    memset(buf, 0, size);
    *out_buf = buf;
    return ESP_OK;
}
