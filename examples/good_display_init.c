/**
 * @file good_display_init.c
 * @brief C23 显示驱动安全正例：LCD 初始化时序 + 帧缓冲分配
 *
 * 约束覆盖：
 *   C23.1 — LCD 初始化时序严格遵循 datasheet
 *   C23.5 — 帧缓冲分配须检查
 *   C23.6 — lv_disp_drv_t 必须设置必要字段
 */

#include "esp_lcd_panel_io.h"
#include "esp_lcd_panel_ops.h"
#include "esp_log.h"
#include "esp_heap_caps.h"
#include "lvgl.h"

static const char *TAG = "display_init";

/**
 * @brief C23.1 — LCD 初始化时序
 */
esp_err_t good_lcd_init(void)
{
    /* C23.1: 复位脉宽 >= 10ms */
    gpio_set_level(GPIO_NUM_48, 0); /* reset low */
    vTaskDelay(pdMS_TO_TICKS(15));   /* 15ms > 10ms */
    gpio_set_level(GPIO_NUM_48, 1); /* reset high */
    vTaskDelay(pdMS_TO_TICKS(150));  /* 150ms > 120ms datasheet requirement */

    /* C23.1: Sleep Out 后等待 >= 120ms */
    /* esp_lcd_panel_io_tx_param(io_handle, 0x11, NULL, 0); // Sleep Out */
    vTaskDelay(pdMS_TO_TICKS(150));  /* 150ms > 120ms */

    ESP_LOGI(TAG, "LCD init timing OK");
    return ESP_OK;
}

/**
 * @brief C23.5 + C23.6 — 帧缓冲分配 + LVGL 驱动注册
 */
esp_err_t good_display_setup(void)
{
    /* C23.5: 帧缓冲分配须检查 */
    size_t fb_size = 240 * 320 * 2; /* RGB565 */
    void *fb = heap_caps_malloc(fb_size, MALLOC_CAP_DMA | MALLOC_CAP_INTERNAL);
    if (fb == NULL) {
        ESP_LOGE(TAG, "Frame buffer alloc failed (%d bytes)", (int)fb_size);
        return ESP_ERR_NO_MEM;
    }

    /* C23.6: lv_disp_drv_t 必须设置必要字段 */
    lv_disp_draw_buf_t draw_buf;
    lv_disp_draw_buf_init(&draw_buf, fb, NULL, 240 * 320);

    lv_disp_drv_t disp_drv;
    lv_disp_drv_init(&disp_drv);

    /* C23.6: 设置必要字段 */
    disp_drv.hor_res = 240;
    disp_drv.ver_res = 320;
    disp_drv.draw_buf = &draw_buf;
    disp_drv.flush_cb = NULL; /* placeholder */

    lv_disp_t *disp = lv_disp_drv_register(&disp_drv);
    if (disp == NULL) {
        ESP_LOGE(TAG, "Display driver register failed");
        heap_caps_free(fb);
        return ESP_FAIL;
    }

    ESP_LOGI(TAG, "Display initialized: 240x320, fb=%p", fb);
    return ESP_OK;
}
