/**
 * @file good_ota_update.c
 * @brief C22 OTA 安全正例：签名验证 + 回滚 + 超时 + 断电恢复
 *
 * 约束覆盖：
 *   C22.1 — 固件签名验证（esp_ota_verify + secure_version 检查）
 *   C22.2 — 回滚机制（mark_valid_cancel_rollback）
 *   C22.3 — 分区表含 ota_0 + ota_1
 *   C22.4 — 断电恢复（双分区，新固件写入非活动分区）
 *   C22.5 — OTA 超时与重试上限
 */

#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "esp_ota_ops.h"
#include "esp_http_client.h"
#include "esp_app_format.h"
#include "esp_image_format.h"

static const char *TAG = "ota_update";

#define OTA_MAX_RETRY       3
#define OTA_RETRY_DELAY_MS  2000
#define OTA_HTTP_TIMEOUT_MS 30000

/**
 * @brief OTA 升级上下文（C22.4: 双分区断电恢复）
 */
typedef struct {
    esp_ota_handle_t    ota_handle;
    const esp_partition_t *update_partition;
    size_t              total_size;
    size_t              downloaded;
    int                 retry_count;
} ota_context_t;

/**
 * @brief C22.1 — 验证新固件签名和版本
 */
static esp_err_t verify_firmware_image(const esp_partition_t *partition)
{
    esp_partition_pos_t partition_pos = {
        .offset = partition->address,
        .size = partition->size,
    };
    esp_image_metadata_t image_metadata = {0};
    esp_err_t err = esp_image_verify(ESP_IMAGE_VERIFY, &partition_pos, &image_metadata);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Firmware signature verification failed: %s", esp_err_to_name(err));
        return err;
    }

    esp_app_desc_t new_app_info;
    err = esp_ota_get_app_description(partition, &new_app_info);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Failed to read app description: %s", esp_err_to_name(err));
        return err;
    }

    /* C22.1: 版本降级检查（防 rollback 攻击） */
    const esp_partition_t *running = esp_ota_get_running_partition();
    esp_app_desc_t running_app_info;
    esp_ota_get_app_description(running, &running_app_info);

    if (new_app_info.secure_version < running_app_info.secure_version) {
        ESP_LOGE(TAG, "OTA rollback attack: new=%d < current=%d",
                 new_app_info.secure_version, running_app_info.secure_version);
        return ESP_ERR_OTA_DOWNGRADE;
    }

    ESP_LOGI(TAG, "Firmware verified: %s v%s (secure=%d)",
             new_app_info.project_name, new_app_info.version,
             new_app_info.secure_version);
    return ESP_OK;
}

/**
 * @brief C22.5 — HTTP 下载配置（含超时）
 */
static esp_err_t http_download_init(esp_http_client_handle_t *client, const char *url)
{
    /* C22.5: 必须配置超时 */
    esp_http_client_config_t config = {
        .url = url,
        .timeout_ms = OTA_HTTP_TIMEOUT_MS,
        .keep_alive_enable = true,
        .buffer_size = 4096,
        .buffer_size_tx = 2048,
    };

    *client = esp_http_client_init(&config);
    if (*client == NULL) {
        ESP_LOGE(TAG, "HTTP client init failed");
        return ESP_FAIL;
    }

    esp_err_t err = esp_http_client_open(*client, 0);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "HTTP open failed: %s", esp_err_to_name(err));
        esp_http_client_cleanup(*client);
        *client = NULL;
        return err;
    }

    return ESP_OK;
}

/**
 * @brief C22.4 — OTA 初始化（选择非活动分区）
 */
static esp_err_t ota_init(ota_context_t *ctx)
{
    /* C22.4: 写入非活动分区，断电后旧固件仍可运行 */
    ctx->update_partition = esp_ota_get_next_update_partition(NULL);
    if (ctx->update_partition == NULL) {
        ESP_LOGE(TAG, "No OTA partition found (C22.3: check partition table)");
        return ESP_FAIL;
    }

    ESP_LOGI(TAG, "Writing to partition: %s (offset=0x%x)",
             ctx->update_partition->label, ctx->update_partition->address);

    esp_err_t err = esp_ota_begin(ctx->update_partition, OTA_SIZE_UNKNOWN, &ctx->ota_handle);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "OTA begin failed: %s", esp_err_to_name(err));
        return err;
    }

    ctx->total_size = 0;
    ctx->downloaded = 0;
    ctx->retry_count = 0;
    return ESP_OK;
}

/**
 * @brief C22.2 — OTA 完成并切换分区
 */
static esp_err_t ota_finalize(ota_context_t *ctx)
{
    esp_err_t err = esp_ota_end(ctx->ota_handle);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "OTA end failed: %s", esp_err_to_name(err));
        return err;
    }

    /* C22.1: 切换前验证签名 */
    err = verify_firmware_image(ctx->update_partition);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Firmware verification failed, aborting OTA");
        return err;
    }

    err = esp_ota_set_boot_partition(ctx->update_partition);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Set boot partition failed: %s", esp_err_to_name(err));
        return err;
    }

    ESP_LOGI(TAG, "OTA successful, rebooting to new firmware...");
    esp_restart();
    return ESP_OK; /* unreachable */
}

/**
 * @brief OTA 下载循环（含重试）
 */
static esp_err_t ota_download_loop(ota_context_t *ctx, esp_http_client_handle_t client)
{
    char buf[4096];
    bool image_header_checked = false;

    while (1) {
        int read_len = esp_http_client_read(client, buf, sizeof(buf));
        if (read_len < 0) {
            ESP_LOGE(TAG, "HTTP read error");
            return ESP_FAIL;
        }
        if (read_len == 0) {
            ESP_LOGI(TAG, "Download complete: %d bytes", ctx->downloaded);
            break;
        }

        /* C22.1: 首包检查固件头 */
        if (!image_header_checked && read_len >= sizeof(esp_image_header_t)) {
            esp_image_header_t *header = (esp_image_header_t *)buf;
            if (header->magic != ESP_IMAGE_HEADER_MAGIC) {
                ESP_LOGE(TAG, "Invalid firmware image header (magic=0x%02x)", header->magic);
                return ESP_ERR_OTA_VALIDATE_FAILED;
            }
            image_header_checked = true;
            ESP_LOGI(TAG, "Image header validated (magic=0x%02x)", header->magic);
        }

        esp_err_t err = esp_ota_write(ctx->ota_handle, buf, read_len);
        if (err != ESP_OK) {
            ESP_LOGE(TAG, "OTA write failed: %s", esp_err_to_name(err));
            return err;
        }

        ctx->downloaded += read_len;
    }

    return ESP_OK;
}

/**
 * @brief C22.5 — 带重试的 OTA 升级主流程
 */
esp_err_t ota_update_from_url(const char *firmware_url)
{
    ota_context_t ctx = {0};

    /* C22.5: 重试循环（有上限） */
    while (ctx.retry_count < OTA_MAX_RETRY) {
        ESP_LOGI(TAG, "OTA attempt %d/%d", ctx.retry_count + 1, OTA_MAX_RETRY);

        esp_err_t err = ota_init(&ctx);
        if (err != ESP_OK) {
            ctx.retry_count++;
            vTaskDelay(pdMS_TO_TICKS(OTA_RETRY_DELAY_MS * ctx.retry_count));
            continue;
        }

        esp_http_client_handle_t client = NULL;
        err = http_download_init(&client, firmware_url);
        if (err != ESP_OK) {
            esp_ota_abort(ctx.ota_handle);
            ctx.retry_count++;
            vTaskDelay(pdMS_TO_TICKS(OTA_RETRY_DELAY_MS * ctx.retry_count));
            continue;
        }

        err = ota_download_loop(&ctx, client);
        esp_http_client_close(client);
        esp_http_client_cleanup(client);

        if (err != ESP_OK) {
            esp_ota_abort(ctx.ota_handle);
            ctx.retry_count++;
            vTaskDelay(pdMS_TO_TICKS(OTA_RETRY_DELAY_MS * ctx.retry_count));
            continue;
        }

        /* C22.2: 最终化（含签名验证 + 设置启动分区） */
        return ota_finalize(&ctx);
    }

    ESP_LOGE(TAG, "OTA failed after %d retries", OTA_MAX_RETRY);
    return ESP_ERR_OTA_SELECT_INVALID_APP;
}

/**
 * @brief C22.2 — 首次启动标记有效（在 app_main 中调用）
 *
 * 新固件启动后必须调用此函数，否则下次重启会回滚到旧固件。
 * 仅在自检通过后调用。
 */
void ota_mark_valid_on_startup(void)
{
    esp_err_t err = esp_ota_mark_app_valid_cancel_rollback();
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Failed to mark OTA valid: %s", esp_err_to_name(err));
    } else {
        ESP_LOGI(TAG, "OTA image marked valid, rollback cancelled");
    }
}
