        #ifndef UI_PAGE_SETTINGS_PAGE_H
        #define UI_PAGE_SETTINGS_PAGE_H

        #include "lvgl.h"

        /* ── Macros ── */
        #ifndef UI_COLOR_BACKGROUND_COLOR
#define UI_COLOR_BACKGROUND_COLOR 0xE0E0E0
#endif
#ifndef UI_COLOR_PRIMARY_COLOR
#define UI_COLOR_PRIMARY_COLOR 0xC0E0C0
#endif

        /* ── Page lifecycle ── */
        lv_obj_t *ui_page_settings_page_create(lv_obj_t *parent);

        /* ── Update functions ── */


        #endif /* UI_PAGE_SETTINGS_PAGE_H */
