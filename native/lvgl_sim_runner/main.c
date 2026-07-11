/**
 * LVGL Headless Simulator Runner
 *
 * Reads scene.bin (compiled from UI Spec), renders using real LVGL API,
 * outputs PPM screenshot and object_tree.bin.
 *
 * No SDL, no window, no external dependencies beyond LVGL.
 *
 * Usage:
 *   lvgl_sim_v9 --scene scene.bin --output out/ --width 480 --height 800
 *   lvgl_sim_v9 --scene scene.bin --assets asset.pack --output out/
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

#include "lvgl.h"
#include "scene_decoder.h"
#include "framebuffer_display.h"
#include "object_tree_dump.h"

/* ── Command line parsing ──────────────────────────────────────── */

typedef struct {
    const char *scene_path;
    const char *asset_path;
    const char *output_dir;
    int width;
    int height;
    int render_time_ms;
} sim_args_t;

static int parse_args(int argc, char *argv[], sim_args_t *args) {
    args->scene_path = NULL;
    args->asset_path = NULL;
    args->output_dir = "artifacts/render";
    args->width = 480;
    args->height = 800;
    args->render_time_ms = 100;

    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--scene") == 0 && i + 1 < argc) {
            args->scene_path = argv[++i];
        } else if (strcmp(argv[i], "--assets") == 0 && i + 1 < argc) {
            args->asset_path = argv[++i];
        } else if (strcmp(argv[i], "--output") == 0 && i + 1 < argc) {
            args->output_dir = argv[++i];
        } else if (strcmp(argv[i], "--width") == 0 && i + 1 < argc) {
            args->width = atoi(argv[++i]);
        } else if (strcmp(argv[i], "--height") == 0 && i + 1 < argc) {
            args->height = atoi(argv[++i]);
        } else if (strcmp(argv[i], "--render-time") == 0 && i + 1 < argc) {
            args->render_time_ms = atoi(argv[++i]);
        } else if (strcmp(argv[i], "--help") == 0) {
            fprintf(stderr, "Usage: %s --scene scene.bin [--assets asset.pack] [--output dir] [--width W] [--height H]\n", argv[0]);
            return 1;
        }
    }

    if (!args->scene_path) {
        fprintf(stderr, "ERROR: --scene required\n");
        return 1;
    }
    return 0;
}

/* ── File I/O helpers ──────────────────────────────────────────── */

static uint8_t *read_file(const char *path, size_t *size) {
    FILE *f = fopen(path, "rb");
    if (!f) {
        fprintf(stderr, "ERROR: Cannot open %s\n", path);
        return NULL;
    }
    fseek(f, 0, SEEK_END);
    *size = (size_t)ftell(f);
    fseek(f, 0, SEEK_SET);
    uint8_t *buf = (uint8_t *)malloc(*size);
    if (!buf) {
        fclose(f);
        return NULL;
    }
    fread(buf, 1, *size, f);
    fclose(f);
    return buf;
}

static int write_ppm(const char *path, const uint8_t *fb, int width, int height) {
    FILE *f = fopen(path, "wb");
    if (!f) return -1;
    fprintf(f, "P6\n%d %d\n255\n", width, height);
    /* Convert RGB565 to RGB888 */
    for (int i = 0; i < width * height; i++) {
        uint16_t pixel = ((uint16_t *)fb)[i];
        uint8_t r = (pixel >> 11) << 3;
        uint8_t g = ((pixel >> 5) & 0x3F) << 2;
        uint8_t b = (pixel & 0x1F) << 3;
        fputc(r, f);
        fputc(g, f);
        fputc(b, f);
    }
    fclose(f);
    return 0;
}

/* ── Main ──────────────────────────────────────────────────────── */

int main(int argc, char *argv[]) {
    sim_args_t args;
    if (parse_args(argc, argv, &args)) {
        return 1;
    }

    /* Read scene file */
    size_t scene_size = 0;
    uint8_t *scene_data = read_file(args.scene_path, &scene_size);
    if (!scene_data) return 1;

    fprintf(stderr, "Scene: %s (%zu bytes)\n", args.scene_path, scene_size);
    fprintf(stderr, "Display: %dx%d\n", args.width, args.height);

    /* Initialize LVGL */
    lv_init();

    /* Create framebuffer display */
    fb_display_t *display = fb_display_create(args.width, args.height);
    if (!display) {
        fprintf(stderr, "ERROR: Failed to create framebuffer\n");
        free(scene_data);
        return 1;
    }

    /* Decode and execute scene */
    int result = scene_decode_and_execute(scene_data, scene_size, display);
    free(scene_data);

    if (result != 0) {
        fprintf(stderr, "ERROR: Scene decode failed (%d)\n", result);
        fb_display_destroy(display);
        return 1;
    }

    /* Render */
    fprintf(stderr, "Rendering %d ms...\n", args.render_time_ms);
    for (int elapsed = 0; elapsed < args.render_time_ms; elapsed += 5) {
        lv_tick_inc(5);
        lv_timer_handler();
    }

    /* Create output directory */
    char cmd[512];
    snprintf(cmd, sizeof(cmd), "mkdir -p %s", args.output_dir);
    system(cmd);

    /* Write PPM screenshot */
    char ppm_path[512];
    snprintf(ppm_path, sizeof(ppm_path), "%s/render.ppm", args.output_dir);
    if (write_ppm(ppm_path, display->framebuffer, args.width, args.height) == 0) {
        fprintf(stderr, "Screenshot: %s\n", ppm_path);
    } else {
        fprintf(stderr, "ERROR: Failed to write PPM\n");
    }

    /* Write object tree */
    char tree_path[512];
    snprintf(tree_path, sizeof(tree_path), "%s/object_tree.bin", args.output_dir);
    int tree_result = object_tree_dump(tree_path, args.width, args.height);
    if (tree_result == 0) {
        fprintf(stderr, "Object tree: %s\n", tree_path);
    } else {
        fprintf(stderr, "WARNING: Object tree dump failed (%d)\n", tree_result);
    }

    /* Write status */
    fprintf(stdout, "{\"ok\":true,\"render\":\"%s\",\"tree\":\"%s\",\"width\":%d,\"height\":%d}\n",
            ppm_path, tree_path, args.width, args.height);

    fb_display_destroy(display);
    return 0;
}
