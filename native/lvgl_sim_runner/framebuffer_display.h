/**
 * Framebuffer Display — in-memory display driver for headless LVGL.
 *
 * No SDL, no window. Pixels go to RAM framebuffer.
 */

#ifndef FRAMEBUFFER_DISPLAY_H
#define FRAMEBUFFER_DISPLAY_H

#include <stdint.h>
#include "lvgl.h"

typedef struct {
    uint8_t *framebuffer;      /* RGB565 pixel data */
    int width;
    int height;
    int stride;                /* bytes per row */
    lv_display_t *lv_display;  /* LVGL display handle */
} fb_display_t;

/**
 * Create a framebuffer display.
 *
 * @param width   Display width in pixels.
 * @param height  Display height in pixels.
 * @return Display context, or NULL on failure.
 */
fb_display_t *fb_display_create(int width, int height);

/**
 * Destroy a framebuffer display.
 *
 * @param display  Display context to destroy.
 */
void fb_display_destroy(fb_display_t *display);

#endif /* FRAMEBUFFER_DISPLAY_H */
