/**
 * 反例 — C21 低功耗管理违规
 *
 * 违反约束:
 *   C21.1 — 深睡眠前未保存状态
 *   C21.4 — 深睡眠前未关闭外设电源
 *
 * 对照正例: low_power_management.txt
 */

#include "app_mvp.h"
#include "esp_sleep.h"
#include "nvs_flash.h"

/* ========== 反例 1: 深睡眠前未保存状态 (C21.1) ========== */

/* ❌ 直接进入深睡眠，唤醒后丢失所有运行状态 */
static void bad_enter_deep_sleep(uint32_t sleep_sec)
{
    esp_sleep_enable_timer_wakeup(sleep_sec * 1000000ULL);
    esp_deep_sleep_start();  /* 当前状态未保存到 NVS */
}

/* ========== 反例 2: 深睡眠前未关闭外设 (C21.4) ========== */

/* ❌ LCD/音频/WiFi 仍在工作，功耗不降 */
static void bad_enter_sleep_with_peripherals(void)
{
    /* 未关闭 LCD 背光 */
    /* 未关闭音频 DAC */
    /* 未关闭 WiFi */

    esp_sleep_enable_timer_wakeup(60 * 1000000ULL);
    esp_deep_sleep_start();  /* 外设仍在耗电 */
}

/* ========== 反例 3: 唤醒后无条件重新初始化 (C21.2) ========== */

/* ❌ 唤醒后不检查原因，全部重新初始化 */
void bad_app_main(void)
{
    full_init();  /* 唤醒后也走完整初始化，浪费时间 */
}

/* ========== 正例对照 ========== */

/* ✅ 正确: 深睡眠前保存状态 + 关闭外设 */
static void good_enter_deep_sleep(uint32_t sleep_sec)
{
    /* 1. 保存运行状态到 NVS */
    nvs_handle_t h;
    nvs_open("state", NVS_READWRITE, &h);
    nvs_set_u8(h, "last_state", current_state);
    nvs_set_u32(h, "playback_pos", current_pos);
    nvs_commit(h);
    nvs_close(h);

    /* 2. 关闭外设电源 */
    gpio_set_level(LCD_BL_PIN, 0);           /* LCD 背光 */
    i2s_channel_disable(rx_handle);           /* 音频 */
    esp_wifi_stop();                          /* WiFi */
    vTaskDelay(pdMS_TO_TICKS(100));           /* 等待外设就绪 */

    /* 3. 配置唤醒源 */
    esp_sleep_enable_timer_wakeup(sleep_sec * 1000000ULL);
    esp_sleep_enable_ext0_wakeup(WAKE_BTN_PIN, 0);  /* 按键唤醒 */

    /* 4. 进入深睡眠 */
    LOG_I(TAG, "Entering deep sleep for %us", sleep_sec);
    esp_deep_sleep_start();
}

/* ✅ 正确: 唤醒后检查原因 */
void good_app_main(void)
{
    esp_sleep_wakeup_cause_t cause = esp_sleep_get_wakeup_cause();

    if (cause == ESP_SLEEP_WAKEUP_TIMER) {
        LOG_I(TAG, "Timer wakeup, resuming");
        resume_from_sleep();
    } else if (cause == ESP_SLEEP_WAKEUP_EXT0) {
        LOG_I(TAG, "Button wakeup, full init");
        full_init();
    } else {
        LOG_I(TAG, "Power-on reset, full init");
        full_init();
    }
}
