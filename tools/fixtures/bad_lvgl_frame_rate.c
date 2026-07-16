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
