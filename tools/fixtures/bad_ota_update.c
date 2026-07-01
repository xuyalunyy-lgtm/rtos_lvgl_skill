/**
 * @file bad_ota_update.c
 * @brief C22 OTA 安全 self-test 反例 fixture
 */
#include "esp_ota_ops.h"
#include "esp_http_client.h"
#include "esp_log.h"

static const char *TAG = "ota";

/* 反例 C22.1: 无签名验证 */
/* 反例 C22.2: 无 mark_valid */
/* 反例 C22.5: 无超时 */
esp_err_t bad_ota_update(const char *url)
{
    const esp_partition_t *part = esp_ota_get_next_update_partition(NULL);
    esp_ota_handle_t handle;
    esp_ota_begin(part, OTA_SIZE_UNKNOWN, &handle);

    /* C22.5 违规: 无 timeout_ms */
    esp_http_client_config_t config = {
        .url = url,
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

    /* C22.2 违规: 直接切换，未 mark_valid */
    esp_ota_end(handle);
    esp_ota_set_boot_partition(part);

    return ESP_OK;
}
