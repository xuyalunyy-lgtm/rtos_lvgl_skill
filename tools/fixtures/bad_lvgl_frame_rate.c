#include "lvgl.h"

void ui_task(void)
{
    lv_timer_handler();
    vTaskDelay(pdMS_TO_TICKS(1));
}

void update_status(void)
{
    lv_obj_invalidate(lv_scr_act());
    lv_refr_now(NULL);
}

static void lcd_flush_cb(lv_disp_drv_t *drv, const lv_area_t *area, lv_color_t *color_p)
{
    lcd_dma_submit(area, color_p);
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
