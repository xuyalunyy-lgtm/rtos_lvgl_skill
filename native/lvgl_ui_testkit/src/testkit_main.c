#include "lvgl_ui_testkit.h"
#include "framebuffer_display.h"
#include "object_tree_dump.h"

#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifdef _WIN32
#include <direct.h>
#define mkdir(path, mode) _mkdir(path)
#else
#include <sys/stat.h>
#endif

#define TESTKIT_VERSION "1.0.0"
#define MAX_PATH_LEN 1024

static int mkdir_p(const char *path)
{
    char tmp[MAX_PATH_LEN];
    snprintf(tmp, sizeof(tmp), "%s", path);
    for (char *cursor = tmp + 1; *cursor; ++cursor) {
        if (*cursor == '/' || *cursor == '\\') {
            char saved = *cursor;
            *cursor = '\0';
            if (mkdir(tmp, 0755) != 0 && errno != EEXIST) return -1;
            *cursor = saved;
        }
    }
    return (mkdir(tmp, 0755) == 0 || errno == EEXIST) ? 0 : -1;
}

static int write_ppm(const char *path, const uint8_t *framebuffer, int width, int height)
{
    FILE *stream = fopen(path, "wb");
    if (stream == NULL) return -1;
    fprintf(stream, "P6\n%d %d\n255\n", width, height);
    const uint16_t *pixels = (const uint16_t *)framebuffer;
    for (int index = 0; index < width * height; ++index) {
        uint16_t pixel = pixels[index];
        fputc((pixel >> 11) << 3, stream);
        fputc(((pixel >> 5) & 0x3F) << 2, stream);
        fputc((pixel & 0x1F) << 3, stream);
    }
    fclose(stream);
    return 0;
}

static double changed_from_first_ratio(const uint8_t *framebuffer, int width, int height)
{
    const uint16_t *pixels = (const uint16_t *)framebuffer;
    const int count = width * height;
    if (count <= 0) return 0.0;
    uint16_t first = pixels[0];
    int changed = 0;
    for (int index = 1; index < count; ++index) {
        if (pixels[index] != first) ++changed;
    }
    return (double)changed / (double)count;
}

int main(int argc, char **argv)
{
    const char *output_dir = argc > 1 ? argv[1] : "artifacts/ui_testkit/native";
    int width = argc > 2 ? atoi(argv[2]) : 480;
    int height = argc > 3 ? atoi(argv[3]) : 800;
    int settle_frames = argc > 4 ? atoi(argv[4]) : 20;
    if (width <= 0 || height <= 0 || settle_frames <= 0 || mkdir_p(output_dir) != 0) return 2;

    lv_init();
    fb_display_t *display = fb_display_create(width, height);
    if (display == NULL) return 3;
    lv_obj_t *screen = lv_display_get_screen_active(lv_display_get_default());
    lv_obj_t *page = ui_test_page_create(screen);
    if (page == NULL) {
        fb_display_destroy(display);
        return 4;
    }

    for (int frame = 0; frame < settle_frames; ++frame) {
        lv_tick_inc(5);
        lv_timer_handler();
    }

    char screenshot_path[MAX_PATH_LEN];
    char tree_path[MAX_PATH_LEN];
    char report_path[MAX_PATH_LEN];
    snprintf(screenshot_path, sizeof(screenshot_path), "%s/render.ppm", output_dir);
    snprintf(tree_path, sizeof(tree_path), "%s/object_tree.bin", output_dir);
    snprintf(report_path, sizeof(report_path), "%s/native_execution_report.json", output_dir);
    int screenshot_ok = write_ppm(screenshot_path, display->framebuffer, width, height) == 0;
    int tree_ok = object_tree_dump(tree_path, width, height) == 0;
    double changed_ratio = changed_from_first_ratio(display->framebuffer, width, height);
    int not_blank = changed_ratio >= 0.01;

    ui_test_page_destroy();
    lv_tick_inc(5);
    lv_timer_handler();

    FILE *report = fopen(report_path, "wb");
    if (report == NULL) {
        fb_display_destroy(display);
        return 5;
    }
    fprintf(report,
        "{\n"
        "  \"schema_version\": \"1.0\",\n"
        "  \"testkit_version\": \"%s\",\n"
        "  \"lvgl_version\": \"%s\",\n"
        "  \"page_name\": \"%s\",\n"
        "  \"width\": %d,\n"
        "  \"height\": %d,\n"
        "  \"settle_frames\": %d,\n"
        "  \"create_success\": true,\n"
        "  \"destroy_called\": true,\n"
        "  \"screenshot_written\": %s,\n"
        "  \"object_tree_written\": %s,\n"
        "  \"changed_from_first_pixel_ratio\": %.6f,\n"
        "  \"not_blank\": %s,\n"
        "  \"framebuffer_bytes\": %d\n"
        "}\n",
        TESTKIT_VERSION, LV_VERSION_INFO, ui_test_page_name(), width, height,
        settle_frames, screenshot_ok ? "true" : "false", tree_ok ? "true" : "false",
        changed_ratio, not_blank ? "true" : "false", width * height * 2);
    fclose(report);
    fb_display_destroy(display);
    return screenshot_ok && tree_ok && not_blank ? 0 : 6;
}

