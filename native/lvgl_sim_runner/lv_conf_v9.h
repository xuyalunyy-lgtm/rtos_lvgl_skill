/**
 * LVGL v9 Configuration for Headless Simulator
 *
 * Minimal config for framebuffer rendering without display hardware.
 */

#ifndef LV_CONF_H
#define LV_CONF_H

/* ── Color settings ────────────────────────────────────────────── */

#define LV_COLOR_DEPTH          16
#define LV_COLOR_16_SWAP        0
#define LV_COLOR_SCREEN_TRANSP  0

/* ── Memory settings ───────────────────────────────────────────── */

#define LV_MEM_CUSTOM           0
#define LV_MEM_SIZE             (256 * 1024)  /* 256KB */

/* ── Display settings ──────────────────────────────────────────── */

#define LV_DPI_DEF              130

/* ── Tick settings ─────────────────────────────────────────────── */

/* We provide our own tick via lv_tick_set_cb() */
#define LV_TICK_CUSTOM          0

/* ── Timer handler ─────────────────────────────────────────────── */

#define LV_USE_TIMER            1
#define LV_TIMER_HANDLER_TICK   5

/* ── Widget usage ──────────────────────────────────────────────── */

#define LV_USE_LABEL            1
#define LV_USE_BTN              1
#define LV_USE_IMG              1
#define LV_USE_BAR              1
#define LV_USE_SLIDER           1
#define LV_USE_SWITCH           1
#define LV_USE_CHECKBOX         1
#define LV_USE_DROPDOWN         1
#define LV_USE_ROLLER           1
#define LV_USE_TEXTAREA         1
#define LV_USE_SPINNER          1
#define LV_USE_ARC              1
#define LV_USE_CANVAS           0
#define LV_USE_CHART            0
#define LV_USE_TABLE            0
#define LV_USE_TABVIEW          0
#define LV_USE_TILEVIEW         0
#define LV_USE_WIN             0
#define LV_USE_MENU            0
#define LV_USE_MSGBOX          0
#define LV_USE_SPAN           0

/* ── Layout ────────────────────────────────────────────────────── */

#define LV_USE_FLEX             1
#define LV_USE_GRID             1

/* ── Fonts ─────────────────────────────────────────────────────── */

#define LV_FONT_MONTSERRAT_14   1
#define LV_FONT_MONTSERRAT_16   1
#define LV_FONT_MONTSERRAT_20   1
#define LV_FONT_MONTSERRAT_24   1
#define LV_FONT_DEFAULT         &lv_font_montserrat_14

/* ── Image decoder ─────────────────────────────────────────────── */

#define LV_USE_PNG              0
#define LV_USE_SJPG            0
#define LV_USE_GIF             0
#define LV_USE_QRCODE          0

/* ── Logging ───────────────────────────────────────────────────── */

#define LV_USE_LOG              0

/* ── Assertions ────────────────────────────────────────────────── */

#define LV_USE_ASSERT_NULL          1
#define LV_USE_ASSERT_MALLOC        1
#define LV_USE_ASSERT_STYLE         0
#define LV_USE_ASSERT_MEM_INTEGRITY 0
#define LV_USE_ASSERT_OBJ           0

/* ── Compiler settings ─────────────────────────────────────────── */

#define LV_ATTRIBUTE_MEM_ALIGN
#define LV_ATTRIBUTE_LARGE_CONST

#endif /* LV_CONF_H */
