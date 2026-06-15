/* fixture: Model 层跨线程 LVGL — 期望 lvgl_thread_checker 失败 */
#include "lvgl.h"

extern lv_obj_t *g_label;

void wss_on_message(const char *text)
{
    if (text != NULL) {
        lv_label_set_text(g_label, text);
    }
}
