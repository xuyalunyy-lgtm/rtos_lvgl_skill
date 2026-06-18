/**
 * 反例 — C19 Flash/NVS 安全违规
 *
 * 违反约束:
 *   C19.1 — NVS 写入后未 commit，数据可能丢失
 *
 * 对照正例: flash_nvs_safety.txt
 */

#include "app_mvp.h"
#include "nvs_flash.h"
#include "nvs.h"

/* ========== 反例 1: NVS 写入后未 commit (C19.1) ========== */

/* ❌ 写入后直接关闭，数据可能还在 cache，未持久化到 Flash */
static void bad_save_wifi_config(const char *ssid, const char *password)
{
    nvs_handle_t h;
    nvs_open("wifi", NVS_READWRITE, &h);

    nvs_set_str(h, "ssid", ssid);
    nvs_set_str(h, "password", password);

    nvs_close(h);  /* 遗漏: nvs_commit(h) — 数据可能丢失 */
}

/* ❌ commit 返回值未检查 */
static void bad_save_state(uint8_t state)
{
    nvs_handle_t h;
    nvs_open("state", NVS_READWRITE, &h);

    nvs_set_u8(h, "last_state", state);
    nvs_commit(h);  /* 返回值未检查，commit 可能失败 */
    nvs_close(h);
}

/* ========== 反例 2: 深睡眠前未保存状态 (C21.1) ========== */

/* ❌ 直接进入深睡眠，唤醒后丢失所有运行状态 */
static void bad_enter_sleep(void)
{
    esp_sleep_enable_timer_wakeup(30 * 1000000ULL);
    esp_deep_sleep_start();  /* 当前状态未保存 */
}

/* ========== 正例对照 ========== */

/* ✅ 正确: 写入 → commit → 检查返回值 */
static void good_save_wifi_config(const char *ssid, const char *password)
{
    nvs_handle_t h;
    esp_err_t ret = nvs_open("wifi", NVS_READWRITE, &h);
    if (ret != ESP_OK) {
        LOG_E(TAG, "NVS open failed: %s", esp_err_to_name(ret));
        return;
    }

    nvs_set_str(h, "ssid", ssid);
    nvs_set_str(h, "password", password);

    ret = nvs_commit(h);
    if (ret != ESP_OK) {
        LOG_E(TAG, "NVS commit failed: %s", esp_err_to_name(ret));
    }
    nvs_close(h);
}

/* ✅ 正确: 深睡眠前保存状态 */
static void good_enter_sleep(void)
{
    nvs_handle_t h;
    nvs_open("state", NVS_READWRITE, &h);
    nvs_set_u8(h, "last_state", current_state);
    nvs_set_u32(h, "playback_pos", current_pos);
    nvs_commit(h);
    nvs_close(h);

    LOG_I(TAG, "State saved, entering deep sleep");
    esp_sleep_enable_timer_wakeup(30 * 1000000ULL);
    esp_deep_sleep_start();
}
