/* Good C11.5: function under 80 lines */
#include "lvgl.h"

static void create_button(lv_obj_t *parent, const char *text, int x, int y)
{
    lv_obj_t *btn = lv_btn_create(parent);
    lv_obj_set_size(btn, 100, 40);
    lv_obj_set_pos(btn, x, y);
    lv_label_set_text(lv_label_create(btn), text);
}

void good_function_length(lv_obj_t *parent)
{
    create_button(parent, "Btn1", 0, 0);
    create_button(parent, "Btn2", 110, 0);
    create_button(parent, "Btn3", 220, 0);
    create_button(parent, "Btn4", 0, 50);
    create_button(parent, "Btn5", 110, 50);
    create_button(parent, "Btn6", 220, 50);
}
