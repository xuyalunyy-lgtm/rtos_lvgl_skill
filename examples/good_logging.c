/**
 * @file good_logging.c
 * @brief C14 日志规范正例：分级日志 + TAG + 脱敏 + 限频
 *
 * 约束覆盖：
 *   C14.1 — 分级日志 + TAG，禁止裸 printf
 *   C14.4 — 日志禁止打印密码/token 明文
 *   C14.6 — 高频日志必须限频
 */

#include <string.h>
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char *TAG = "app_auth";

/* C14.6: 限频宏 */
#define LOG_RATE_LIMIT_MS(ms) do { \
    static uint32_t last_log = 0; \
    uint32_t now = xTaskGetTickCount() * portTICK_PERIOD_MS; \
    if (now - last_log < (ms)) return; \
    last_log = now; \
} while(0)

/**
 * @brief C14.1 — 使用 LOG_* 宏 + TAG
 */
void good_log_example(int status)
{
    /* C14.1: 正确使用 LOGI/LOGE + TAG */
    ESP_LOGI(TAG, "Status updated: %d", status);

    if (status < 0) {
        ESP_LOGE(TAG, "Error occurred: %d", status);
    }
}

/**
 * @brief C14.4 — token 脱敏打印
 */
void good_log_token(const char *token)
{
    if (token == NULL) return;

    /* C14.4: 只打印前 4 个字符 + **** */
    size_t len = strlen(token);
    if (len > 4) {
        ESP_LOGI(TAG, "Token: %.4s**** (len=%d)", token, (int)len);
    } else {
        ESP_LOGI(TAG, "Token: **** (len=%d)", (int)len);
    }
}

/**
 * @brief C14.6 — 高频日志限频
 */
void good_log_periodic(int value)
{
    /* C14.6: 每秒最多打印一次 */
    LOG_RATE_LIMIT_MS(1000);
    ESP_LOGI(TAG, "Periodic value: %d", value);
}

/**
 * @brief C14.4 — WiFi 密码脱敏
 */
void good_log_wifi_config(const char *ssid, const char *password)
{
    ESP_LOGI(TAG, "WiFi SSID: %s", ssid);
    /* C14.4: 密码不打印 */
    ESP_LOGI(TAG, "WiFi password: [REDACTED]");
}
