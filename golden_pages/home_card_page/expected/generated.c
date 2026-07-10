/**
 * @file ui_home_card_page.c
 * @brief LVGL home card page (auto-generated golden page baseline)
 */

#include "lvgl.h"

static lv_obj_t *s_page = NULL;

lv_obj_t *ui_home_card_page_create(lv_obj_t *parent)
{
    s_page = lv_obj_create(parent);
    lv_obj_set_size(s_page, 480, 800);
    lv_obj_set_style_bg_color(s_page, lv_color_hex(0x0D1B2A), 0);

    /* Weather card — LVGL_LAYOUT_EXCEPTION: absolute position */
    lv_obj_t *card1 = lv_obj_create(s_page);
    lv_obj_set_size(card1, 440, 120);
    lv_obj_set_pos(card1, 20, 60);
    lv_obj_set_style_bg_color(card1, lv_color_hex(0x1B2838), 0);
    lv_obj_set_style_radius(card1, 16, 0);
    lv_obj_set_style_border_width(card1, 0, 0);

    lv_obj_t *title1 = lv_label_create(card1);
    lv_obj_set_pos(title1, 20, 15);
    lv_label_set_text(title1, "Weather");
    lv_obj_set_style_text_color(title1, lv_color_hex(0xFFFFFF), 0);

    lv_obj_t *sub1 = lv_label_create(card1);
    lv_obj_set_pos(sub1, 20, 45);
    lv_label_set_text(sub1, "25C Sunny");
    lv_obj_set_style_text_color(sub1, lv_color_hex(0x8899AA), 0);

    /* Schedule card — LVGL_LAYOUT_EXCEPTION: absolute position */
    lv_obj_t *card2 = lv_obj_create(s_page);
    lv_obj_set_size(card2, 440, 120);
    lv_obj_set_pos(card2, 20, 200);
    lv_obj_set_style_bg_color(card2, lv_color_hex(0x1B2838), 0);
    lv_obj_set_style_radius(card2, 16, 0);
    lv_obj_set_style_border_width(card2, 0, 0);

    lv_obj_t *title2 = lv_label_create(card2);
    lv_obj_set_pos(title2, 20, 15);
    lv_label_set_text(title2, "Schedule");
    lv_obj_set_style_text_color(title2, lv_color_hex(0xFFFFFF), 0);

    lv_obj_t *sub2 = lv_label_create(card2);
    lv_obj_set_pos(sub2, 20, 45);
    lv_label_set_text(sub2, "3 meetings today");
    lv_obj_set_style_text_color(sub2, lv_color_hex(0x8899AA), 0);

    /* Nav button — LVGL_LAYOUT_EXCEPTION: centered bottom */
    lv_obj_t *btn = lv_btn_create(s_page);
    lv_obj_set_size(btn, 60, 60);
    lv_obj_set_pos(btn, 210, 700);
    lv_obj_set_style_bg_color(btn, lv_color_hex(0x2196F3), 0);
    lv_obj_set_style_radius(btn, 30, 0);

    return s_page;
}
