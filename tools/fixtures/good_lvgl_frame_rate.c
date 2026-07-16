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
