#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <time.h>
#ifdef _WIN32
#include <direct.h>
#else
#include <sys/stat.h>
#include <sys/types.h>
#endif

#include "lvgl.h"
#include "ui_under_test_default.h"
#include "lvgl/drivers/sdl/lv_sdl_mouse.h"
#include "lvgl/drivers/sdl/lv_sdl_window.h"

#ifndef REGRESSION_WIDTH
#define REGRESSION_WIDTH 480
#endif
#ifndef REGRESSION_HEIGHT
#define REGRESSION_HEIGHT 800
#endif
#ifndef REGRESSION_OUTPUT_DIR
#define REGRESSION_OUTPUT_DIR "regression"
#endif

static void make_output_dir(void)
{
#ifdef _WIN32
    _mkdir(REGRESSION_OUTPUT_DIR);
#else
    mkdir(REGRESSION_OUTPUT_DIR, 0775);
#endif
}

static void write_probe_ppm(const char *path)
{
    FILE *fp = fopen(path, "wb");
    if(fp == NULL) return;
    fprintf(fp, "P6\n2 2\n255\n");
    fputc(0x20, fp); fputc(0x24, fp); fputc(0x2A, fp);
    fputc(0x21, fp); fputc(0x96, fp); fputc(0xF3, fp);
    fputc(0xFF, fp); fputc(0x98, fp); fputc(0x00, fp);
    fputc(0xFF, fp); fputc(0xFF, fp); fputc(0xFF, fp);
    fclose(fp);
}

static int write_screen_ppm(const char *path, lv_obj_t *screen)
{
#if LV_USE_SNAPSHOT
    lv_obj_update_layout(screen);
    lv_draw_buf_t *snapshot = lv_snapshot_take(screen, LV_COLOR_FORMAT_RGB888);
    if(snapshot == NULL) {
        fprintf(stderr, "LVGL snapshot failed; using probe image\n");
        return 0;
    }

    FILE *fp = fopen(path, "wb");
    if(fp == NULL) {
        lv_draw_buf_destroy(snapshot);
        return 0;
    }
    fprintf(fp, "P6\n%u %u\n255\n", (unsigned)snapshot->header.w, (unsigned)snapshot->header.h);
    for(uint32_t y = 0; y < snapshot->header.h; ++y) {
        const unsigned char *row = (const unsigned char *)lv_draw_buf_goto_xy(snapshot, 0, y);
        if(row == NULL) {
            fclose(fp);
            lv_draw_buf_destroy(snapshot);
            return 0;
        }
        fwrite(row, 3, snapshot->header.w, fp);
    }
    fclose(fp);
    lv_draw_buf_destroy(snapshot);
    return 1;
#else
    (void)path;
    (void)screen;
    fprintf(stderr, "LV_USE_SNAPSHOT is disabled; using probe image\n");
    return 0;
#endif
}

static void json_string(FILE *fp, const char *text)
{
    fputc('"', fp);
    if(text != NULL) {
        const unsigned char *p = (const unsigned char *)text;
        while(*p != '\0') {
            unsigned char c = *p++;
            if(c == '"' || c == '\\') {
                fputc('\\', fp);
                fputc(c, fp);
            }
            else if(c == '\n') fputs("\\n", fp);
            else if(c == '\r') fputs("\\r", fp);
            else if(c == '\t') fputs("\\t", fp);
            else if(c < 0x20) fprintf(fp, "\\u%04X", (unsigned)c);
            else fputc(c, fp);
        }
    }
    fputc('"', fp);
}

static const char *object_type(const lv_obj_t *obj)
{
#if LV_USE_LABEL
    if(lv_obj_check_type(obj, &lv_label_class)) return "label";
#endif
#if LV_USE_BUTTON
    if(lv_obj_check_type(obj, &lv_button_class)) return "button";
#endif
#if LV_USE_SLIDER
    if(lv_obj_check_type(obj, &lv_slider_class)) return "slider";
#endif
#if LV_USE_BAR
    if(lv_obj_check_type(obj, &lv_bar_class)) return "bar";
#endif
#if LV_USE_IMAGE
    if(lv_obj_check_type(obj, &lv_image_class)) return "image";
#endif
#if LV_USE_SWITCH
    if(lv_obj_check_type(obj, &lv_switch_class)) return "switch";
#endif
#if LV_USE_CHECKBOX
    if(lv_obj_check_type(obj, &lv_checkbox_class)) return "checkbox";
#endif
#if LV_USE_DROPDOWN
    if(lv_obj_check_type(obj, &lv_dropdown_class)) return "dropdown";
#endif
#if LV_USE_TEXTAREA
    if(lv_obj_check_type(obj, &lv_textarea_class)) return "textarea";
#endif
    return "obj";
}

static void write_object_json(FILE *fp, const lv_obj_t *obj)
{
    uint32_t child_count = lv_obj_get_child_count(obj);
    uint32_t bg = lv_color_to_u32(lv_obj_get_style_bg_color(obj, LV_PART_MAIN)) & 0xFFFFFFU;
    uint32_t text = lv_color_to_u32(lv_obj_get_style_text_color(obj, LV_PART_MAIN)) & 0xFFFFFFU;
    fprintf(fp,
            "{\"type\":");
    json_string(fp, object_type(obj));
    fprintf(fp,
            ",\"x\":%d,\"y\":%d,\"w\":%d,\"h\":%d,"
            "\"computed_styles\":{\"bg_color\":\"#%06X\",\"bg_opa\":%u,\"text_color\":\"#%06X\",\"radius\":%d}",
            (int)lv_obj_get_x(obj), (int)lv_obj_get_y(obj),
            (int)lv_obj_get_width(obj), (int)lv_obj_get_height(obj),
            (unsigned)bg, (unsigned)lv_obj_get_style_bg_opa(obj, LV_PART_MAIN),
            (unsigned)text, (int)lv_obj_get_style_radius(obj, LV_PART_MAIN));
#if LV_USE_LABEL
    if(lv_obj_check_type(obj, &lv_label_class)) {
        fprintf(fp, ",\"text\":");
        json_string(fp, lv_label_get_text(obj));
    }
#endif
    fprintf(fp, ",\"children\":[");
    for(uint32_t i = 0; i < child_count; ++i) {
        if(i > 0) fputc(',', fp);
        write_object_json(fp, lv_obj_get_child(obj, (int32_t)i));
    }
    fputs("]}", fp);
}

static void write_object_tree_json(const char *path, lv_obj_t *screen)
{
    FILE *fp = fopen(path, "wb");
    if(fp == NULL) return;
    lv_obj_update_layout(screen);
    fprintf(fp,
            "{\"schema\":\"freertos-embedded-architect.lvgl.object-tree.v1\","
            "\"source\":\"lvgl-sandbox\","
            "\"display\":{\"width\":%d,\"height\":%d},"
            "\"introspection\":{\"available\":true},"
            "\"tree\":",
            REGRESSION_WIDTH, REGRESSION_HEIGHT);
    write_object_json(fp, screen);
    fputs("}\n", fp);
    fclose(fp);
}

int main(void)
{
    make_output_dir();
    lv_init();

    lv_display_t *disp = lv_sdl_window_create(REGRESSION_WIDTH, REGRESSION_HEIGHT);
    if(disp == NULL) {
        fprintf(stderr, "SDL display initialization failed\n");
        return 2;
    }
    lv_display_set_default(disp);

    lv_indev_t *mouse = lv_sdl_mouse_create();
    if(mouse != NULL) {
        lv_indev_set_display(mouse, disp);
    }

    lv_obj_t *screen = lv_screen_active();
    if(screen == NULL) {
        fprintf(stderr, "LVGL screen unavailable\n");
        return 3;
    }

    lv_obj_remove_flag(screen, LV_OBJ_FLAG_SCROLLABLE);
    ui_under_test_create(screen);

    const clock_t start = clock();
    for(int i = 0; i < 120; ++i) {
        lv_timer_handler();
        lv_tick_inc(16);
    }
    const clock_t end = clock();
    const double elapsed = (double)(end - start) / (double)CLOCKS_PER_SEC;

    char screen_path[512];
    char probe_path[512];
    char tree_path[512];
    snprintf(screen_path, sizeof(screen_path), "%s/%s", REGRESSION_OUTPUT_DIR, "screen.ppm");
    snprintf(probe_path, sizeof(probe_path), "%s/%s", REGRESSION_OUTPUT_DIR, "probe.ppm");
    snprintf(tree_path, sizeof(tree_path), "%s/%s", REGRESSION_OUTPUT_DIR, "object_tree.json");
    if(!write_screen_ppm(screen_path, screen)) {
        write_probe_ppm(screen_path);
    }
    write_probe_ppm(probe_path);
    write_object_tree_json(tree_path, screen);
    printf("lvgl_regression frames=120 elapsed=%.3f screenshot=%s object_tree=%s\n", elapsed, screen_path, tree_path);
    return 0;
}
