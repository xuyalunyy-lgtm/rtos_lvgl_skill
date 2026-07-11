        #ifndef UI_PAGE_SENSOR_PAGE_H
        #define UI_PAGE_SENSOR_PAGE_H

        #include "lvgl.h"

        /* ── Macros ── */
        #ifndef UI_COLOR_BACKGROUND_COLOR
#define UI_COLOR_BACKGROUND_COLOR 0x002020
#endif
#ifndef UI_COLOR_TEXT_COLOR
#define UI_COLOR_TEXT_COLOR 0x204040
#endif
#ifndef UI_COLOR_PRIMARY_COLOR
#define UI_COLOR_PRIMARY_COLOR 0x206080
#endif

        /* ── Page lifecycle ── */
        lv_obj_t *ui_page_sensor_page_create(lv_obj_t *parent);

        /* ── Update functions ── */


        #endif /* UI_PAGE_SENSOR_PAGE_H */
