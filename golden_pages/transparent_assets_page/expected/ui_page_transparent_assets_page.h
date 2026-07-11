        #ifndef UI_PAGE_TRANSPARENT_ASSETS_PAGE_H
        #define UI_PAGE_TRANSPARENT_ASSETS_PAGE_H

        #include "lvgl.h"

        /* ── Macros ── */
        #ifndef UI_COLOR_BACKGROUND_COLOR
#define UI_COLOR_BACKGROUND_COLOR 0x60A0E0
#endif
#ifndef UI_COLOR_PRIMARY_COLOR
#define UI_COLOR_PRIMARY_COLOR 0xC0C0C0
#endif

        /* ── Page lifecycle ── */
        lv_obj_t *ui_page_transparent_assets_page_create(lv_obj_t *parent);

        /* ── Update functions ── */


        #endif /* UI_PAGE_TRANSPARENT_ASSETS_PAGE_H */
