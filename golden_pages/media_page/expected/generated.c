/**
 * @file ui_media_page.c
 * @brief LVGL media player page (auto-generated golden page baseline)
 */

#include "lvgl.h"

static lv_obj_t *s_page = NULL;
static lv_obj_t *s_title = NULL;
static lv_obj_t *s_artist = NULL;
static lv_obj_t *s_progress = NULL;

lv_obj_t *ui_media_page_create(lv_obj_t *parent)
{
    s_page = lv_obj_create(parent);
    lv_obj_set_size(s_page, 480, 800);
    lv_obj_set_style_bg_color(s_page, lv_color_hex(0x121212), 0);

    /* Cover placeholder — LVGL_LAYOUT_EXCEPTION: absolute position */
    lv_obj_t *cover = lv_obj_create(s_page);
    lv_obj_set_size(cover, 300, 300);
    lv_obj_set_pos(cover, 90, 80);
    lv_obj_set_style_bg_color(cover, lv_color_hex(0x2A2A2A), 0);
    lv_obj_set_style_radius(cover, 20, 0);
    lv_obj_set_style_border_width(cover, 0, 0);

    /* Song title — LVGL_LAYOUT_EXCEPTION */
    s_title = lv_label_create(s_page);
    lv_obj_set_pos(s_title, 140, 410);
    lv_label_set_text(s_title, "Song Title");
    lv_obj_set_style_text_color(s_title, lv_color_hex(0xFFFFFF), 0);

    /* Artist — LVGL_LAYOUT_EXCEPTION */
    s_artist = lv_label_create(s_page);
    lv_obj_set_pos(s_artist, 170, 445);
    lv_label_set_text(s_artist, "Artist Name");
    lv_obj_set_style_text_color(s_artist, lv_color_hex(0x888888), 0);

    /* Progress bar — LVGL_LAYOUT_EXCEPTION */
    s_progress = lv_bar_create(s_page);
    lv_obj_set_size(s_progress, 380, 6);
    lv_obj_set_pos(s_progress, 50, 520);
    lv_bar_set_range(s_progress, 0, 100);
    lv_bar_set_value(s_progress, 35, LV_ANIM_OFF);
    lv_obj_set_style_bg_color(s_progress, lv_color_hex(0x333333), 0);
    lv_obj_set_style_bg_color(s_progress, lv_color_hex(0x2196F3), LV_PART_INDICATOR);

    /* Play button — LVGL_LAYOUT_EXCEPTION: centered */
    lv_obj_t *play = lv_btn_create(s_page);
    lv_obj_set_size(play, 70, 70);
    lv_obj_set_pos(play, 205, 600);
    lv_obj_set_style_bg_color(play, lv_color_hex(0x2196F3), 0);
    lv_obj_set_style_radius(play, 35, 0);

    /* Prev — LVGL_LAYOUT_EXCEPTION */
    lv_obj_t *prev = lv_btn_create(s_page);
    lv_obj_set_size(prev, 50, 50);
    lv_obj_set_pos(prev, 100, 610);
    lv_obj_set_style_bg_color(prev, lv_color_hex(0x333333), 0);
    lv_obj_set_style_radius(prev, 25, 0);

    /* Next — LVGL_LAYOUT_EXCEPTION */
    lv_obj_t *next = lv_btn_create(s_page);
    lv_obj_set_size(next, 50, 50);
    lv_obj_set_pos(next, 330, 610);
    lv_obj_set_style_bg_color(next, lv_color_hex(0x333333), 0);
    lv_obj_set_style_radius(next, 25, 0);

    return s_page;
}

void ui_media_page_set_title(const char *text)
{
    if (s_title != NULL && text != NULL) lv_label_set_text(s_title, text);
}

void ui_media_page_set_artist(const char *text)
{
    if (s_artist != NULL && text != NULL) lv_label_set_text(s_artist, text);
}

void ui_media_page_set_progress(int32_t value)
{
    if (s_progress != NULL) lv_bar_set_value(s_progress, value, LV_ANIM_ON);
}
