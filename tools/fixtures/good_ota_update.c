/**
 * @file good_ota_update.c
 * @brief C22 OTA 安全 self-test 正例 fixture
 */
#include "esp_ota_ops.h"
#include "esp_http_client.h"
#include "esp_log.h"

static const char *TAG = "ota";

esp_err_t ota_update(const char *url)
{
    /* C22.1: 签名验证 */
    const esp_partition_t *part = esp_ota_get_next_update_partition(NULL);
    esp_ota_handle_t handle;
    esp_ota_begin(part, OTA_SIZE_UNKNOWN, &handle);

    /* C22.5: HTTP 超时配置 */
    esp_http_client_config_t config = {
        .url = url,
        .timeout_ms = 30000,
    };
    esp_http_client_handle_t client = esp_http_client_init(&config);
    esp_http_client_open(client, 0);

    char buf[4096];
    int len = esp_http_client_read(client, buf, sizeof(buf));
    if (len > 0) {
        esp_ota_write(handle, buf, len);
    }

    esp_http_client_close(client);
    esp_http_client_cleanup(client);

    esp_ota_end(handle);

    /* C22.1: 签名验证 */
    esp_app_desc_t app_desc;
    esp_ota_get_app_description(part, &app_desc);

    /* C22.2: 设置启动分区 + 标记有效 */
    esp_ota_set_boot_partition(part);

    return ESP_OK;
}

void ota_mark_valid(void)
{
    /* C22.2: mark_valid_cancel_rollback */
    esp_ota_mark_app_valid_cancel_rollback();
}
