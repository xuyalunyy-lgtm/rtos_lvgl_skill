#include "lvgl.h"

void ui_task(void)
{
    uint32_t next_delay_ms = lv_timer_handler();
    vTaskDelay(pdMS_TO_TICKS(next_delay_ms > 16U ? 16U : next_delay_ms));
}

void update_status(lv_obj_t *label)
{
    lv_label_set_text(label, "ready");
    lv_obj_invalidate(label);
}

static void lcd_flush_cb(lv_disp_drv_t *drv, const lv_area_t *area, lv_color_t *color_p)
{
    lcd_dma_submit(area, color_p);
    lv_disp_flush_ready(drv);
}

void display_init(void)
{
    lv_disp_drv_t disp_drv;
    lv_disp_drv_init(&disp_drv);
    disp_drv.hor_res = 240;
    disp_drv.ver_res = 320;
    disp_drv.draw_buf = &g_draw_buf;
    disp_drv.flush_cb = lcd_flush_cb;
    lv_disp_drv_register(&disp_drv);
}

/* LVGL_ASYNC_FLUSH_READY: lcd_dma_done_isr calls lv_disp_flush_ready(drv). */
static void async_lcd_flush_cb(lv_disp_drv_t *drv, const lv_area_t *area, lv_color_t *color_p)
{
    lcd_dma_submit(area, color_p);
}

void async_display_init(void)
{
    lv_disp_drv_t disp_drv;
    lv_disp_drv_init(&disp_drv);
    disp_drv.hor_res = 240;
    disp_drv.ver_res = 320;
    disp_drv.draw_buf = &g_draw_buf;
    disp_drv.flush_cb = async_lcd_flush_cb;
    lv_disp_drv_register(&disp_drv);
}

static void page_button_event_cb(lv_event_t *event)
{
    post_ui_nav_event(NAV_HOME);
}

void bind_page_button(lv_obj_t *button)
{
    lv_obj_add_event_cb(button, page_button_event_cb, LV_EVENT_CLICKED, NULL);
}
