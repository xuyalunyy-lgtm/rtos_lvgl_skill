/** Runtime registry for LVGL binary fonts supplied to the headless runner. */
#ifndef FONT_REGISTRY_H
#define FONT_REGISTRY_H

#include <stdint.h>
#include "lvgl.h"

#define FONT_REGISTRY_MAX_FONTS 32
#define FONT_REGISTRY_ID_MAX 32
#define FONT_REGISTRY_PATH_MAX 1024

typedef struct {
    char id[FONT_REGISTRY_ID_MAX];
    /* lv_binfont_create retains this filesystem path for glyph reads. */
    char path[FONT_REGISTRY_PATH_MAX];
    lv_font_t *font;
} font_registry_entry_t;

typedef struct {
    font_registry_entry_t entries[FONT_REGISTRY_MAX_FONTS];
    uint32_t count;
} font_registry_t;

void font_registry_init(font_registry_t *registry);
int font_registry_load(font_registry_t *registry, const char *binding);
const lv_font_t *font_registry_find(const font_registry_t *registry, const char *id);
uint32_t font_registry_count(const font_registry_t *registry);
void font_registry_destroy(font_registry_t *registry);

#endif /* FONT_REGISTRY_H */
