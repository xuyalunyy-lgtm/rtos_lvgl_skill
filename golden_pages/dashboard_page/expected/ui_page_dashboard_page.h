        #ifndef UI_PAGE_DASHBOARD_PAGE_H
        #define UI_PAGE_DASHBOARD_PAGE_H

        #include "lvgl.h"

        /* ── Macros ── */
        #ifndef UI_COLOR_BACKGROUND_COLOR
#define UI_COLOR_BACKGROUND_COLOR 0xE0E0E0
#endif
#ifndef UI_COLOR_PRIMARY_COLOR
#define UI_COLOR_PRIMARY_COLOR 0xA0A0A0
#endif

        /* ── Page lifecycle ── */
        lv_obj_t *ui_page_dashboard_page_create(lv_obj_t *parent);

        /* ── Update functions ── */


        #endif /* UI_PAGE_DASHBOARD_PAGE_H */
