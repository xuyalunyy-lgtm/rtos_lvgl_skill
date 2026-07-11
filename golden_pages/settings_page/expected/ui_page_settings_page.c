#include "lvgl.h"
#include "ui_page_settings_page.h"

#ifndef UI_COLOR_BACKGROUND_COLOR
#define UI_COLOR_BACKGROUND_COLOR 0xE0E0E0
#endif
#ifndef UI_COLOR_PRIMARY_COLOR
#define UI_COLOR_PRIMARY_COLOR 0xC0E0C0
#endif

/* ── Static widget handles ── */
static lv_obj_t *s_root = NULL;
static lv_obj_t *s_region_0 = NULL;
static lv_obj_t *s_region_1 = NULL;
static lv_obj_t *s_region_2 = NULL;
static lv_obj_t *s_region_3 = NULL;
static lv_obj_t *s_region_4 = NULL;
static lv_obj_t *s_region_5 = NULL;
static lv_obj_t *s_region_6 = NULL;
static lv_obj_t *s_region_7 = NULL;
static lv_obj_t *s_region_8 = NULL;
static lv_obj_t *s_region_9 = NULL;
static lv_obj_t *s_region_10 = NULL;
static lv_obj_t *s_region_11 = NULL;
static lv_obj_t *s_region_12 = NULL;
static lv_obj_t *s_region_13 = NULL;
static lv_obj_t *s_region_14 = NULL;
static lv_obj_t *s_region_15 = NULL;
static lv_obj_t *s_region_16 = NULL;

/* ── Page create ── */
lv_obj_t *ui_page_settings_page_create(lv_obj_t *parent)
{
    lv_obj_t *root = lv_obj_create(parent);
    lv_obj_set_size(root, 480, 800);

    s_root = lv_obj_create(NULL);

    s_region_0 = lv_obj_create(s_root);

    s_region_1 = lv_obj_create(s_root);

    s_region_2 = lv_obj_create(s_root);

    s_region_3 = lv_obj_create(s_root);

    s_region_4 = lv_obj_create(s_root);

    s_region_5 = lv_obj_create(s_root);

    s_region_6 = lv_obj_create(s_root);

    s_region_7 = lv_obj_create(s_root);

    s_region_8 = lv_obj_create(s_root);

    s_region_9 = lv_obj_create(s_root);

    s_region_10 = lv_obj_create(s_root);

    s_region_11 = lv_obj_create(s_root);

    s_region_12 = lv_obj_create(s_root);

    s_region_13 = lv_obj_create(s_root);

    s_region_14 = lv_obj_create(s_root);

    s_region_15 = lv_obj_create(s_root);

    s_region_16 = lv_obj_create(s_root);

    return root;
}