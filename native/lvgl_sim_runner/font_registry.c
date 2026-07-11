/** Runtime loader for official LVGL .bin fonts. */
#include "font_registry.h"

#include <stdio.h>
#include <string.h>

void font_registry_init(font_registry_t *registry) {
    if (registry) memset(registry, 0, sizeof(*registry));
}

int font_registry_load(font_registry_t *registry, const char *binding) {
    if (!registry || !binding || registry->count >= FONT_REGISTRY_MAX_FONTS) return -1;
    const char *separator = strchr(binding, '=');
    if (!separator || separator == binding || !separator[1]) return -1;
    size_t id_len = (size_t)(separator - binding);
    if (id_len >= FONT_REGISTRY_ID_MAX) return -1;
    for (uint32_t i = 0; i < registry->count; i++) {
        if (strlen(registry->entries[i].id) == id_len && strncmp(registry->entries[i].id, binding, id_len) == 0) return -1;
    }

    lv_font_t *font = lv_binfont_create(separator + 1);
    if (!font) {
        fprintf(stderr, "ERROR: Failed to load LVGL binary font: %s\n", separator + 1);
        return -1;
    }
    font_registry_entry_t *entry = &registry->entries[registry->count++];
    memcpy(entry->id, binding, id_len);
    entry->id[id_len] = '\0';
    entry->font = font;
    return 0;
}

const lv_font_t *font_registry_find(const font_registry_t *registry, const char *id) {
    if (!registry || !id) return NULL;
    for (uint32_t i = 0; i < registry->count; i++) {
        if (strcmp(registry->entries[i].id, id) == 0) return registry->entries[i].font;
    }
    return NULL;
}

uint32_t font_registry_count(const font_registry_t *registry) {
    return registry ? registry->count : 0;
}

void font_registry_destroy(font_registry_t *registry) {
    if (!registry) return;
    for (uint32_t i = 0; i < registry->count; i++) {
        if (registry->entries[i].font) lv_binfont_destroy(registry->entries[i].font);
    }
    memset(registry, 0, sizeof(*registry));
}
