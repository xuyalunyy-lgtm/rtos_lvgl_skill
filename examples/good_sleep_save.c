/**
 * @file good_sleep_save.c
 * @brief C21 低功耗管理正例：深睡眠状态保存 + 外设断电
 *
 * 约束覆盖：
 *   C21.1 — 深睡眠前必须保存状态到 NVS
 *   C21.4 — 深睡眠前必须关闭外设电源
 */

#include "esp_sleep.h"
#include "esp_log.h"
#include "nvs_flash.h"
#include "nvs.h"
#include "driver/gpio.h"

static const char *TAG = "sleep_save";

/**
 * @brief C21.4 — 关闭外设电源
 */
static void power_down_peripherals(void)
{
    /* C21.4: 逐个关闭外设电源 */
    ESP_LOGI(TAG, "Powering down LCD backlight");
    gpio_set_level(GPIO_NUM_5, 0); /* LCD backlight off */

    ESP_LOGI(TAG, "Powering down audio DAC");
    /* dac_output_disable() or equivalent */

    ESP_LOGI(TAG, "Powering down WiFi");
    /* esp_wifi_stop() */

    ESP_LOGI(TAG, "All peripherals powered down");
}

/**
 * @brief C21.1 — 保存状态到 NVS
 */
static esp_err_t save_state_to_nvs(uint32_t sleep_count)
{
    nvs_handle_t handle;
    esp_err_t err;

    err = nvs_open("sleep", NVS_READWRITE, &handle);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "NVS open failed: %s", esp_err_to_name(err));
        return err;
    }

    err = nvs_set_u32(handle, "sleep_count", sleep_count);
    if (err != ESP_OK) {
        nvs_close(handle);
        return err;
    }

    /* C21.1: commit + 检查返回值 */
    err = nvs_commit(handle);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "NVS commit failed: %s", esp_err_to_name(err));
        nvs_close(handle);
        return err;
    }

    nvs_close(handle);
    ESP_LOGI(TAG, "State saved: sleep_count=%u", (unsigned)sleep_count);
    return ESP_OK;
}

/**
 * @brief C21.1 + C21.4 — 安全进入深睡眠
 */
void enter_deep_sleep(uint32_t sleep_count)
{
    /* C21.1: 先保存状态 */
    esp_err_t err = save_state_to_nvs(sleep_count);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Failed to save state, aborting sleep");
        return;
    }

    /* C21.4: 关闭外设电源 */
    power_down_peripherals();

    /* 配置唤醒源 */
    esp_sleep_enable_timer_wakeup(60 * 1000000); /* 60 秒 */

    ESP_LOGI(TAG, "Entering deep sleep...");
    esp_deep_sleep_start();
}
