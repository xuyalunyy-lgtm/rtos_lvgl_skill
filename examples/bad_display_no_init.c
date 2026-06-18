/**
 * 反例 — C23 显示驱动安全违规
 *
 * 违反约束:
 *   C23.1 — LCD 初始化时序错误
 *   C23.5 — 帧缓冲分配未检查返回值
 *   C23.6 — lv_disp_drv_t 缺少必要字段
 *
 * 对照正例: lcd_display_driver.txt
 */

#include "app_mvp.h"
#include "lvgl.h"
#include "esp_lcd_panel_ops.h"

/* ========== 反例 1: LCD 初始化时序错误 (C23.1) ========== */

/* ❌ 复位后立即发送命令，LCD 未就绪 */
static void bad_lcd_init(void)
{
    gpio_set_level(LCD_RST_PIN, 1);
    lcd_send_cmd(0x11);  /* 太早，LCD 可能无响应 */
    lcd_send_cmd(0x29);  /* Display On */
}

/* ❌ Sleep Out 后未等待 120ms */
static void bad_lcd_init2(void)
{
    gpio_set_level(LCD_RST_PIN, 0);
    vTaskDelay(pdMS_TO_TICKS(10));
    gpio_set_level(LCD_RST_PIN, 1);
    vTaskDelay(pdMS_TO_TICKS(120));

    lcd_send_cmd(0x11);  /* Sleep Out */
    /* 遗漏: vTaskDelay(pdMS_TO_TICKS(120)) */
    lcd_send_cmd(0x29);  /* Display On — LCD 可能还在 sleep */
}

/* ========== 反例 2: 帧缓冲分配未检查 (C23.5) ========== */

/* ❌ PSRAM 分配可能失败，未检查 */
static void bad_framebuf_init(void)
{
    size_t fb_size = LCD_WIDTH * LCD_HEIGHT * sizeof(lv_color_t) * 2;
    lv_color_t *buf1 = heap_caps_malloc(fb_size, MALLOC_CAP_SPIRAM);
    lv_color_t *buf2 = heap_caps_malloc(fb_size, MALLOC_CAP_SPIRAM);
    /* buf1/buf2 可能为 NULL → LVGL 崩溃 */

    static lv_disp_draw_buf_t draw_buf;
    lv_disp_draw_buf_init(&draw_buf, buf1, buf2, LCD_WIDTH * LCD_HEIGHT);
}

/* ========== 反例 3: lv_disp_drv_t 缺少必要字段 (C23.6) ========== */

/* ❌ 未设置 hor_res/ver_res，渲染区域错误 */
static void bad_disp_drv_register(void)
{
    static lv_disp_draw_buf_t draw_buf;
    lv_disp_draw_buf_init(&draw_buf, buf1, buf2, buf_size);

    static lv_disp_drv_t disp_drv;
    lv_disp_drv_init(&disp_drv);
    disp_drv.flush_cb = lcd_flush_cb;
    /* 缺少: disp_drv.hor_res = LCD_WIDTH; */
    /* 缺少: disp_drv.ver_res = LCD_HEIGHT; */
    lv_disp_drv_register(&disp_drv);
}

/* ========== 正例对照 ========== */

/* ✅ 正确: LCD 初始化时序 */
static void good_lcd_init(void)
{
    /* 1. 硬件复位 */
    gpio_set_level(LCD_RST_PIN, 0);
    vTaskDelay(pdMS_TO_TICKS(10));
    gpio_set_level(LCD_RST_PIN, 1);
    vTaskDelay(pdMS_TO_TICKS(120));  /* datasheet 要求 */

    /* 2. Sleep Out + 等待 */
    lcd_send_cmd(0x11);
    vTaskDelay(pdMS_TO_TICKS(120));  /* 必须等待 */

    /* 3. Display On */
    lcd_send_cmd(0x29);
    vTaskDelay(pdMS_TO_TICKS(20));
}

/* ✅ 正确: 帧缓冲分配检查 */
static void good_framebuf_init(void)
{
    size_t fb_size = LCD_WIDTH * LCD_HEIGHT * sizeof(lv_color_t) * 2;
    lv_color_t *buf1 = heap_caps_malloc(fb_size, MALLOC_CAP_SPIRAM);
    lv_color_t *buf2 = heap_caps_malloc(fb_size, MALLOC_CAP_SPIRAM);

    if (buf1 == NULL || buf2 == NULL) {
        LOG_E(TAG, "Framebuf alloc failed (%u bytes), using partial refresh",
              fb_size);
        /* 降级: 使用部分刷新 */
        static lv_color_t partial_buf[LCD_WIDTH * (LCD_HEIGHT / 10)];
        static lv_disp_draw_buf_t draw_buf;
        lv_disp_draw_buf_init(&draw_buf, partial_buf, NULL,
                              LCD_WIDTH * (LCD_HEIGHT / 10));
        return;
    }

    static lv_disp_draw_buf_t draw_buf;
    lv_disp_draw_buf_init(&draw_buf, buf1, buf2, LCD_WIDTH * LCD_HEIGHT);
}

/* ✅ 正确: 完整 lv_disp_drv_t 注册 */
static void good_disp_drv_register(void)
{
    static lv_disp_drv_t disp_drv;
    lv_disp_drv_init(&disp_drv);
    disp_drv.draw_buf = &draw_buf;
    disp_drv.flush_cb = lcd_flush_cb;
    disp_drv.hor_res = LCD_WIDTH;
    disp_drv.ver_res = LCD_HEIGHT;
    disp_drv.full_refresh = 0;
    disp_drv.direct_mode = 0;
    lv_disp_drv_register(&disp_drv);
}
