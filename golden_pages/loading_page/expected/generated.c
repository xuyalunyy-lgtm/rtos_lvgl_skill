/**
 * @file ui_loading_page.c
 * @brief LVGL loading page (auto-generated golden page baseline)
 * @warning Modify layout only via analysis_report.json update
 */

#include "lvgl.h"

/* ── Page root ──────────────────────── */
static lv_obj_t *s_page = NULL;

/* ── Component handles ──────────────── */
static lv_obj_t *s_loading_text = NULL;

lv_obj_t *ui_loading_page_create(lv_obj_t *parent)
{
    s_page = lv_obj_create(parent);
    lv_obj_set_size(s_page, 480, 800);
    lv_obj_set_style_bg_color(s_page, lv_color_hex(0x1A1A2E), 0);

    /* Glass circle — LVGL_LAYOUT_EXCEPTION: frosted glass effect */
    lv_obj_t *circle = lv_obj_create(s_page);
    lv_obj_set_size(circle, 84, 84);
    lv_obj_set_pos(circle, 198, 358);
    lv_obj_set_style_radius(circle, 42, 0);
    lv_obj_set_style_bg_color(circle, lv_color_hex(0xFFFFFF), 0);
    lv_obj_set_style_bg_opa(circle, LV_OPA_30, 0);
    lv_obj_set_style_border_width(circle, 0, 0);

    /* Loading text — LVGL_LAYOUT_EXCEPTION: centered below circle */
    s_loading_text = lv_label_create(s_page);
    lv_obj_set_pos(s_loading_text, 190, 460);
    lv_label_set_text(s_loading_text, "Loading...");
    lv_obj_set_style_text_color(s_loading_text, lv_color_hex(0xFFFFFF), 0);

    /* Time label — LVGL_LAYOUT_EXCEPTION: status bar position */
    lv_obj_t *time_label = lv_label_create(s_page);
    lv_obj_set_pos(time_label, 20, 12);
    lv_label_set_text(time_label, "12:30");
    lv_obj_set_style_text_color(time_label, lv_color_hex(0xFFFFFF), 0);

    return s_page;
}

void ui_loading_page_set_text(const char *text)
{
    if (s_loading_text != NULL && text != NULL) {
        lv_label_set_text(s_loading_text, text);
    }
}
