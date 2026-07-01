/**
 * @file good_nvs_commit.c
 * @brief C19 Flash/NVS 安全正例：NVS commit + 返回值检查
 *
 * 约束覆盖：
 *   C19.1 — NVS 写入后必须 nvs_commit() + 检查返回值
 */

#include "nvs_flash.h"
#include "nvs.h"
#include "esp_log.h"

static const char *TAG = "nvs_commit";

/**
 * @brief C19.1 — NVS 写入 + commit + 返回值检查
 */
esp_err_t good_nvs_save_config(const char *key, uint32_t value)
{
    nvs_handle_t handle;
    esp_err_t err;

    /* 打开 NVS */
    err = nvs_open("config", NVS_READWRITE, &handle);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "NVS open failed: %s", esp_err_to_name(err));
        return err;
    }

    /* 写入 */
    err = nvs_set_u32(handle, key, value);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "NVS set failed: %s", esp_err_to_name(err));
        nvs_close(handle);
        return err;
    }

    /* C19.1: commit + 检查返回值 */
    err = nvs_commit(handle);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "NVS commit failed: %s", esp_err_to_name(err));
        nvs_close(handle);
        return err;
    }

    ESP_LOGI(TAG, "Saved %s = %u", key, (unsigned)value);
    nvs_close(handle);
    return ESP_OK;
}

/**
 * @brief C19.1 — NVS 读取 + 返回值检查
 */
esp_err_t good_nvs_load_config(const char *key, uint32_t *out_value)
{
    nvs_handle_t handle;
    esp_err_t err;

    err = nvs_open("config", NVS_READONLY, &handle);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "NVS open failed: %s", esp_err_to_name(err));
        return err;
    }

    err = nvs_get_u32(handle, key, out_value);
    nvs_close(handle);

    if (err == ESP_ERR_NVS_NOT_FOUND) {
        ESP_LOGW(TAG, "Key %s not found, using default", key);
        *out_value = 0;
        return ESP_OK;
    }

    return err;
}
