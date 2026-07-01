/**
 * @file bad_ota_no_rollback.c
 * @brief C22 OTA 安全反例：无签名验证 + 无回滚 + 无超时
 *
 * 违反约束：
 *   C22.1 — 未验证固件签名（直接写入 Flash）
 *   C22.2 — 未调用 mark_valid_cancel_rollback（断电后回滚不可控）
 *   C22.4 — 直接覆盖当前分区（断电 = 变砖）
 *   C22.5 — HTTP 无超时、重试无上限
 */

#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "esp_ota_ops.h"
#include "esp_http_client.h"

static const char *TAG = "ota_bad";

/* 反例 C22.5: HTTP 无超时 */
static esp_err_t bad_http_download(const char *url, esp_ota_handle_t *ota_handle)
{
    esp_http_client_config_t config = {
        .url = url,
        /* 缺少 .timeout_ms — C22.5 违规 */
    };

    esp_http_client_handle_t client = esp_http_client_init(&config);
    esp_http_client_open(client, 0);

    char buf[4096];
    int total = 0;
    while (1) {
        int len = esp_http_client_read(client, buf, sizeof(buf));
        if (len <= 0) break;

        /* 反例 C22.1: 未检查固件头/签名，直接写入 */
        esp_ota_write(*ota_handle, buf, len);
        total += len;
    }

    esp_http_client_close(client);
    esp_http_client_cleanup(client);
    ESP_LOGI(TAG, "Downloaded %d bytes", total);
    return ESP_OK;
}

/* 反例 C22.5: 重试无上限 */
static void bad_ota_retry_forever(const char *url)
{
    while (1) { /* 无退出条件 — C22.5 违规 */
        esp_ota_handle_t handle;
        const esp_partition_t *part = esp_ota_get_next_update_partition(NULL);

        /* 反例 C22.4: 如果 part 是当前运行分区，断电 = 变砖 */
        esp_ota_begin(part, OTA_SIZE_UNKNOWN, &handle);

        esp_err_t err = bad_http_download(url, &handle);
        if (err == ESP_OK) {
            /* 反例 C22.2: 直接切换，未验证签名 */
            esp_ota_end(handle);
            esp_ota_set_boot_partition(part);
            esp_restart();
        }

        /* 反例 C22.2: 失败后未 abort，OTA handle 泄漏 */
        ESP_LOGE(TAG, "OTA failed, retrying forever...");
        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}

/**
 * 反例 C22.2: app_main 中未调用 esp_ota_mark_app_valid_cancel_rollback()
 *
 * 若新固件有 bug，下次重启会回滚到旧固件。
 * 但若旧固件也没调用 mark_valid，回滚行为不确定。
 */
void app_main(void)
{
    ESP_LOGI(TAG, "Starting OTA update...");
    bad_ota_retry_forever("http://example.com/firmware.bin");
    /* 永远不会到达这里 */
}
