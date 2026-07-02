/**
 * @file modules_init.c
 * @brief 多模块初始化入口（自动生成）
 *
 * 初始化顺序按模块依赖拓扑排序：
 *   1. 基础设施（通信、存储）
 *   2. 驱动层（传感器、显示、音频）
 *   3. 业务层（UI、ASR、网络）
 */

#include <stdio.h>
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#include "audio_player_contract.h"
#include "display_mgr_contract.h"

static const char *TAG = "modules_init";

esp_err_t modules_init_all(void)
{
    esp_err_t err;

    /* audio_player */
    err = audio_player_init();
    if (err != AUDIO_PLAYER_OK) {
        ESP_LOGE(TAG, "audio_player_init failed: %d", err);
        return err;
    }

    /* display_mgr */
    err = display_mgr_init();
    if (err != DISPLAY_MGR_OK) {
        ESP_LOGE(TAG, "display_mgr_init failed: %d", err);
        return err;
    }

    ESP_LOGI(TAG, "All modules initialized");
    return ESP_OK;
}

esp_err_t modules_start_all(void)
{
    esp_err_t err;

    err = audio_player_start();
    if (err != AUDIO_PLAYER_OK) {
        ESP_LOGE(TAG, "audio_player_start failed: %d", err);
    }

    err = display_mgr_start();
    if (err != DISPLAY_MGR_OK) {
        ESP_LOGE(TAG, "display_mgr_start failed: %d", err);
    }

    return ESP_OK;
}

void modules_stop_all(void)
{
    display_mgr_stop();
    audio_player_stop();
}

void modules_deinit_all(void)
{
    display_mgr_deinit();
    audio_player_deinit();
}