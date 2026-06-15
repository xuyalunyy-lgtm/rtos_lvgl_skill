/* fixture: View 层文件名 — 期望 lvgl_thread_checker 通过 */
#include "lvgl.h"

void ui_view_set_status(lv_obj_t *label, const char *text)
{
    if (label != NULL && text != NULL) {
        lv_label_set_text(label, text);
    }
}
