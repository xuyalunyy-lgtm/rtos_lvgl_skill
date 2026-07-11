/**
 * Framebuffer Display Implementation
 */

#include "framebuffer_display.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* ── Draw buffer ───────────────────────────────────────────────── */

#define DRAW_BUF_LINES  40  /* Partial render: 40 lines at a time */

static uint8_t *g_draw_buf = NULL;

/* ── Flush callback ────────────────────────────────────────────── */

static void flush_cb(lv_display_t *disp, const lv_area_t *area, uint8_t *px_map) {
    fb_display_t *fb = (fb_display_t *)lv_display_get_user_data(disp);
    if (!fb || !fb->framebuffer) {
        lv_display_flush_ready(disp);
        return;
    }

    int32_t x1 = area->x1;
    int32_t y1 = area->y1;
    int32_t x2 = area->x2;
    int32_t y2 = area->y2;

    /* Copy rendered area to framebuffer */
    for (int32_t y = y1; y <= y2; y++) {
        uint16_t *dst = (uint16_t *)(fb->framebuffer + y * fb->stride + x1 * 2);
        uint16_t *src = (uint16_t *)(px_map + (y - y1) * (x2 - x1 + 1) * 2);
        memcpy(dst, src, (x2 - x1 + 1) * 2);
    }

    lv_display_flush_ready(disp);
}

/* ── Tick handler (for simulated time) ─────────────────────────── */

static uint32_t g_tick = 0;

static uint32_t tick_get_cb(void) {
    return g_tick;
}

void lv_tick_inc_cb(uint32_t tick_period) {
    g_tick += tick_period;
}

/* ── Public API ────────────────────────────────────────────────── */

fb_display_t *fb_display_create(int width, int height) {
    if (width <= 0 || height <= 0 || width > 4096 || height > 4096) {
        fprintf(stderr, "ERROR: Invalid display size %dx%d\n", width, height);
        return NULL;
    }

    fb_display_t *fb = (fb_display_t *)calloc(1, sizeof(fb_display_t));
    if (!fb) return NULL;

    fb->width = width;
    fb->height = height;
    fb->stride = width * 2;  /* RGB565: 2 bytes per pixel */

    /* Allocate framebuffer */
    fb->framebuffer = (uint8_t *)calloc(1, fb->stride * height);
    if (!fb->framebuffer) {
        free(fb);
        return NULL;
    }

    /* Initialize LVGL tick */
    lv_tick_set_cb(tick_get_cb);

    /* Create LVGL display */
    fb->lv_display = lv_display_create(width, height);
    if (!fb->lv_display) {
        free(fb->framebuffer);
        free(fb);
        return NULL;
    }

    /* Allocate draw buffer */
    size_t draw_buf_size = width * DRAW_BUF_LINES * 2;  /* RGB565 */
    g_draw_buf = (uint8_t *)calloc(1, draw_buf_size);
    if (!g_draw_buf) {
        free(fb->framebuffer);
        free(fb);
        return NULL;
    }

    /* Configure display */
    lv_display_set_buffers(fb->lv_display, g_draw_buf, NULL, draw_buf_size, LV_DISPLAY_RENDER_MODE_PARTIAL);
    lv_display_set_flush_cb(fb->lv_display, flush_cb);
    lv_display_set_user_data(fb->lv_display, fb);

#if LVGL_VERSION_MAJOR >= 9
    lv_display_set_color_format(fb->lv_display, LV_COLOR_FORMAT_RGB565);
#endif

    fprintf(stderr, "Display: %dx%d RGB565 (stride=%d)\n", width, height, fb->stride);
    return fb;
}

void fb_display_destroy(fb_display_t *fb) {
    if (!fb) return;
    if (g_draw_buf) {
        free(g_draw_buf);
        g_draw_buf = NULL;
    }
    if (fb->framebuffer) {
        free(fb->framebuffer);
    }
    free(fb);
}
