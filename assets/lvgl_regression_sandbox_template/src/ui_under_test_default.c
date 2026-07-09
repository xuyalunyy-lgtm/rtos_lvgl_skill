#include "ui_under_test_default.h"

lv_obj_t *ui_under_test_create(lv_obj_t *parent)
{
    lv_obj_t *root = lv_obj_create(parent);
    lv_obj_set_size(root, LV_PCT(100), LV_PCT(100));
    lv_obj_set_flex_flow(root, LV_FLEX_FLOW_COLUMN);
    lv_obj_set_flex_align(root, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);
    lv_obj_set_style_bg_color(root, lv_color_hex(0x20242A), 0);
    lv_obj_set_style_pad_all(root, 24, 0);
    lv_obj_set_style_pad_gap(root, 16, 0);

    lv_obj_t *title = lv_label_create(root);
    lv_label_set_text(title, "LVGL regression sandbox");
    lv_obj_set_style_text_color(title, lv_color_hex(0xFFFFFF), 0);

    lv_obj_t *button = lv_button_create(root);
    lv_obj_set_size(button, 180, 56);
    lv_obj_set_style_radius(button, 8, 0);
    lv_obj_set_style_bg_color(button, lv_color_hex(0x2196F3), 0);

    lv_obj_t *label = lv_label_create(button);
    lv_label_set_text(label, "READY");
    lv_obj_center(label);
    return root;
}
