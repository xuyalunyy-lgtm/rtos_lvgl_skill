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
 *   lvgl_sim_v9 --version
 *   lvgl_sim_v9 --self-test
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <errno.h>

#ifdef _WIN32
#include <direct.h>
#define mkdir(path, mode) _mkdir(path)
#else
#include <sys/stat.h>
#endif

#include "lvgl.h"
#include "scene_decoder.h"
#include "framebuffer_display.h"
#include "object_tree_dump.h"

/* ── Version ───────────────────────────────────────────────────── */

#define SIM_VERSION "1.0.0"
#define SIM_LVGL_VERSION "9.x"

/* ── Limits ────────────────────────────────────────────────────── */

#define MIN_WIDTH       1
#define MAX_WIDTH       4096
#define MIN_HEIGHT      1
#define MAX_HEIGHT      4096
#define MIN_RENDER_MS   1
#define MAX_RENDER_MS   10000
#define MAX_PATH_LEN    1024

/* ── Platform directory creation ───────────────────────────────── */

static int mkdir_p(const char *path) {
    char tmp[MAX_PATH_LEN];
    snprintf(tmp, sizeof(tmp), "%s", path);

    for (char *p = tmp + 1; *p; p++) {
        if (*p == '/' || *p == '\\') {
            char c = *p;
            *p = '\0';
            if (mkdir(tmp, 0755) != 0 && errno != EEXIST) {
                return -1;
            }
            *p = c;
        }
    }
    if (mkdir(tmp, 0755) != 0 && errno != EEXIST) {
        return -1;
    }
    return 0;
}

/* ── Command line parsing ──────────────────────────────────────── */

typedef struct {
    const char *scene_path;
    const char *output_dir;
    int width;
    int height;
    int render_time_ms;
    int self_test;
    int version;
} sim_args_t;

static int parse_int(const char *str, const char *name, int min_val, int max_val) {
    char *endptr;
    errno = 0;
    long val = strtol(str, &endptr, 10);
    if (errno != 0 || *endptr != '\0' || val < min_val || val > max_val) {
        fprintf(stderr, "ERROR: %s must be integer %d-%d, got '%s'\n", name, min_val, max_val, str);
        return -1;
    }
    return (int)val;
}

static int parse_args(int argc, char *argv[], sim_args_t *args) {
    args->scene_path = NULL;
    args->output_dir = "artifacts/render";
    args->width = 480;
    args->height = 800;
    args->render_time_ms = 100;
    args->self_test = 0;
    args->version = 0;

    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--scene") == 0 && i + 1 < argc) {
            args->scene_path = argv[++i];
        } else if (strcmp(argv[i], "--output") == 0 && i + 1 < argc) {
            args->output_dir = argv[++i];
        } else if (strcmp(argv[i], "--width") == 0 && i + 1 < argc) {
            int v = parse_int(argv[++i], "width", MIN_WIDTH, MAX_WIDTH);
            if (v < 0) return 1;
            args->width = v;
        } else if (strcmp(argv[i], "--height") == 0 && i + 1 < argc) {
            int v = parse_int(argv[++i], "height", MIN_HEIGHT, MAX_HEIGHT);
            if (v < 0) return 1;
            args->height = v;
        } else if (strcmp(argv[i], "--render-time") == 0 && i + 1 < argc) {
            int v = parse_int(argv[++i], "render-time", MIN_RENDER_MS, MAX_RENDER_MS);
            if (v < 0) return 1;
            args->render_time_ms = v;
        } else if (strcmp(argv[i], "--self-test") == 0) {
            args->self_test = 1;
        } else if (strcmp(argv[i], "--version") == 0) {
            args->version = 1;
        } else if (strcmp(argv[i], "--help") == 0 || strcmp(argv[i], "-h") == 0) {
            fprintf(stderr, "LVGL Headless Simulator v%s (LVGL %s)\n", SIM_VERSION, SIM_LVGL_VERSION);
            fprintf(stderr, "Usage: %s --scene scene.bin [--output dir] [--width W] [--height H]\n", argv[0]);
            fprintf(stderr, "       %s --version\n", argv[0]);
            fprintf(stderr, "       %s --self-test\n", argv[0]);
            return 1;
        }
    }

    return 0;
}

static int validate_args(const sim_args_t *args) {
    if (args->version || args->self_test) return 0;

    if (!args->scene_path) {
        fprintf(stderr, "ERROR: --scene required\n");
        return 1;
    }
    if (args->width < MIN_WIDTH || args->width > MAX_WIDTH) {
        fprintf(stderr, "ERROR: width must be %d-%d, got %d\n", MIN_WIDTH, MAX_WIDTH, args->width);
        return 1;
    }
    if (args->height < MIN_HEIGHT || args->height > MAX_HEIGHT) {
        fprintf(stderr, "ERROR: height must be %d-%d, got %d\n", MIN_HEIGHT, MAX_HEIGHT, args->height);
        return 1;
    }
    if (args->render_time_ms < MIN_RENDER_MS || args->render_time_ms > MAX_RENDER_MS) {
        fprintf(stderr, "ERROR: render-time must be %d-%d ms, got %d\n", MIN_RENDER_MS, MAX_RENDER_MS, args->render_time_ms);
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
    if (fseek(f, 0, SEEK_END) != 0) {
        fclose(f);
        return NULL;
    }
    long file_size = ftell(f);
    if (file_size <= 0) {
        fclose(f);
        return NULL;
    }
    if (fseek(f, 0, SEEK_SET) != 0) {
        fclose(f);
        return NULL;
    }
    *size = (size_t)file_size;
    uint8_t *buf = (uint8_t *)malloc(*size);
    if (!buf) {
        fclose(f);
        return NULL;
    }
    size_t read = fread(buf, 1, *size, f);
    fclose(f);
    if (read != *size) {
        free(buf);
        return NULL;
    }
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

/* ── Self-test ─────────────────────────────────────────────────── */

static int run_self_test(void) {
    int errors = 0;

    fprintf(stderr, "LVGL Simulator v%s self-test\n", SIM_VERSION);
    fprintf(stderr, "LVGL version: %s\n", LV_VERSION_INFO);
    fprintf(stderr, "Display: %dx%d RGB565\n", 480, 800);

    /* Initialize LVGL */
    lv_init();

    /* Create framebuffer display */
    fb_display_t *display = fb_display_create(480, 800);
    if (!display) {
        fprintf(stderr, "FAIL: Failed to create framebuffer\n");
        return 1;
    }
    if (!display->framebuffer) {
        fprintf(stderr, "FAIL: Framebuffer is NULL\n");
        fb_display_destroy(display);
        return 1;
    }
    fprintf(stderr, "  [PASS] Framebuffer created (%dx%d)\n", 480, 800);

    /* Create a simple test scene */
    lv_obj_t *scr = lv_display_get_screen_active(lv_display_get_default());
    if (!scr) {
        fprintf(stderr, "FAIL: No active screen\n");
        fb_display_destroy(display);
        return 1;
    }

    lv_obj_t *label = lv_label_create(scr);
    if (!label) {
        fprintf(stderr, "FAIL: Failed to create label\n");
        fb_display_destroy(display);
        return 1;
    }
    lv_label_set_text(label, "Self-Test OK");
    lv_obj_center(label);
    fprintf(stderr, "  [PASS] Test scene created (screen + label)\n");

    /* Render */
    for (int i = 0; i < 20; i++) {
        lv_tick_inc(5);
        lv_timer_handler();
    }

    /* Write test output */
    if (mkdir_p("artifacts/self_test") != 0) {
        fprintf(stderr, "FAIL: Cannot create output directory\n");
        fb_display_destroy(display);
        return 1;
    }

    int ppm_ok = write_ppm("artifacts/self_test/test.ppm", display->framebuffer, 480, 800) == 0;
    if (!ppm_ok) {
        fprintf(stderr, "FAIL: write_ppm failed\n");
        errors++;
    }

    int tree_ok = object_tree_dump("artifacts/self_test/test_tree.bin", 480, 800) == 0;
    if (!tree_ok) {
        fprintf(stderr, "FAIL: object_tree_dump failed\n");
        errors++;
    }

    /* Check file sizes */
    FILE *f_ppm = fopen("artifacts/self_test/test.ppm", "rb");
    if (f_ppm) {
        fseek(f_ppm, 0, SEEK_END);
        long ppm_size = ftell(f_ppm);
        fclose(f_ppm);
        if (ppm_size < 100) {
            fprintf(stderr, "FAIL: test.ppm too small (%ld bytes)\n", ppm_size);
            errors++;
        } else {
            fprintf(stderr, "  [PASS] test.ppm (%ld bytes)\n", ppm_size);
        }
    } else {
        fprintf(stderr, "FAIL: Cannot open test.ppm\n");
        errors++;
    }

    FILE *f_tree = fopen("artifacts/self_test/test_tree.bin", "rb");
    if (f_tree) {
        fseek(f_tree, 0, SEEK_END);
        long tree_size = ftell(f_tree);
        fclose(f_tree);
        if (tree_size < 20) {
            fprintf(stderr, "FAIL: test_tree.bin too small (%ld bytes)\n", tree_size);
            errors++;
        } else {
            fprintf(stderr, "  [PASS] test_tree.bin (%ld bytes)\n", tree_size);
        }
    } else {
        fprintf(stderr, "FAIL: Cannot open test_tree.bin\n");
        errors++;
    }

    fb_display_destroy(display);

    if (errors > 0) {
        fprintf(stderr, "FAIL: %d errors\n", errors);
        return 1;
    }

    fprintf(stderr, "PASS: Self-test completed\n");
    fprintf(stdout, "{\"ok\":true,\"version\":\"%s\",\"lvgl\":\"%s\"}\n", SIM_VERSION, LV_VERSION_INFO);
    return 0;
}

/* ── Main ──────────────────────────────────────────────────────── */

int main(int argc, char *argv[]) {
    sim_args_t args;
    if (parse_args(argc, argv, &args)) {
        return 1;
    }

    /* Handle --version */
    if (args.version) {
        fprintf(stdout, "{\"version\":\"%s\",\"lvgl\":\"%s\"}\n", SIM_VERSION, LV_VERSION_INFO);
        return 0;
    }

    /* Handle --self-test */
    if (args.self_test) {
        return run_self_test();
    }

    /* Validate args */
    if (validate_args(&args)) {
        return 1;
    }

    /* Read scene file */
    size_t scene_size = 0;
    uint8_t *scene_data = read_file(args.scene_path, &scene_size);
    if (!scene_data) return 1;

    /* Validate scene header */
    if (scene_size < 32) {
        fprintf(stderr, "ERROR: Scene file too small (%zu bytes)\n", scene_size);
        free(scene_data);
        return 1;
    }

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
    mkdir_p(args.output_dir);

    /* Write PPM screenshot */
    char ppm_path[MAX_PATH_LEN];
    snprintf(ppm_path, sizeof(ppm_path), "%s/render.ppm", args.output_dir);
    if (write_ppm(ppm_path, display->framebuffer, args.width, args.height) == 0) {
        fprintf(stderr, "Screenshot: %s\n", ppm_path);
    } else {
        fprintf(stderr, "ERROR: Failed to write PPM\n");
    }

    /* Write object tree */
    char tree_path[MAX_PATH_LEN];
    snprintf(tree_path, sizeof(tree_path), "%s/object_tree.bin", args.output_dir);
    int tree_result = object_tree_dump(tree_path, args.width, args.height);
    if (tree_result == 0) {
        fprintf(stderr, "Object tree: %s\n", tree_path);
    } else {
        fprintf(stderr, "WARNING: Object tree dump failed (%d)\n", tree_result);
    }

    /* Write status JSON to stdout */
    fprintf(stdout, "{\"ok\":true,\"render\":\"%s\",\"tree\":\"%s\",\"width\":%d,\"height\":%d,\"version\":\"%s\"}\n",
            ppm_path, tree_path, args.width, args.height, SIM_VERSION);

    fb_display_destroy(display);
    return 0;
}
