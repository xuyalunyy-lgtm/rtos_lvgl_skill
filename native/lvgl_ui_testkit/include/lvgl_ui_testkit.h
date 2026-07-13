#ifndef LVGL_UI_TESTKIT_H
#define LVGL_UI_TESTKIT_H

#include "lvgl.h"

/* Implemented by the generated per-case adapter. */
lv_obj_t *ui_test_page_create(lv_obj_t *parent);
void ui_test_page_destroy(void);
const char *ui_test_page_name(void);

#endif /* LVGL_UI_TESTKIT_H */

