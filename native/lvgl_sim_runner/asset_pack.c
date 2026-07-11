#include "asset_pack.h"

#include <stdio.h>
#include <string.h>

#define ASSET_PACK_HEADER_SIZE 16U
#define ASSET_PACK_ENTRY_SIZE 64U
#define ASSET_PACK_VERSION 1U
#define ASSET_PACK_MAX_BYTES (64U * 1024U * 1024U)

enum {
    ASSET_FORMAT_RGB565 = 1,
    ASSET_FORMAT_RGB565A8 = 2,
    ASSET_FORMAT_ARGB8888 = 3,
    ASSET_FORMAT_A8 = 4,
};

static uint32_t read_le32(const uint8_t *p) {
    return (uint32_t)p[0] |
           ((uint32_t)p[1] << 8) |
           ((uint32_t)p[2] << 16) |
           ((uint32_t)p[3] << 24);
}

static int checked_span(size_t total, uint32_t offset, uint32_t length) {
    return (size_t)offset <= total && (size_t)length <= total - (size_t)offset;
}

static int image_format(uint32_t format, uint32_t width, uint32_t height,
                        uint32_t pixel_size, uint32_t alpha_size,
                        lv_color_format_t *color_format, uint32_t *stride) {
    uint64_t pixels = (uint64_t)width * (uint64_t)height;
    if (width == 0U || height == 0U || pixels > UINT32_MAX) return -1;

    switch (format) {
    case ASSET_FORMAT_RGB565:
        if ((uint64_t)pixel_size != pixels * 2U || alpha_size != 0U) return -1;
        *color_format = LV_COLOR_FORMAT_RGB565;
        *stride = width * 2U;
        return 0;
    case ASSET_FORMAT_RGB565A8:
        if ((uint64_t)pixel_size != pixels * 2U || (uint64_t)alpha_size != pixels) return -1;
        *color_format = LV_COLOR_FORMAT_RGB565A8;
        *stride = width * 2U;
        return 0;
    case ASSET_FORMAT_ARGB8888:
        if ((uint64_t)pixel_size != pixels * 4U || alpha_size != 0U) return -1;
        *color_format = LV_COLOR_FORMAT_ARGB8888;
        *stride = width * 4U;
        return 0;
    case ASSET_FORMAT_A8:
        if ((uint64_t)pixel_size != pixels || alpha_size != 0U) return -1;
        *color_format = LV_COLOR_FORMAT_A8;
        *stride = width;
        return 0;
    default:
        return -1;
    }
}

int asset_pack_load(asset_pack_t *pack, const uint8_t *data, size_t size) {
    if (!pack || !data || size < ASSET_PACK_HEADER_SIZE || size > ASSET_PACK_MAX_BYTES) {
        return -1;
    }
    if (memcmp(data, "APK\0", 4) != 0 || read_le32(data + 4) != ASSET_PACK_VERSION) {
        fprintf(stderr, "ERROR: Invalid asset pack header\n");
        return -1;
    }

    uint32_t count = read_le32(data + 8);
    if (count > ASSET_PACK_MAX_ASSETS || (size_t)count > (size - ASSET_PACK_HEADER_SIZE) / ASSET_PACK_ENTRY_SIZE) {
        fprintf(stderr, "ERROR: Invalid asset pack entry count\n");
        return -1;
    }

    memset(pack, 0, sizeof(*pack));
    for (uint32_t i = 0; i < count; i++) {
        const uint8_t *entry = data + ASSET_PACK_HEADER_SIZE + ((size_t)i * ASSET_PACK_ENTRY_SIZE);
        const uint8_t *name_end = (const uint8_t *)memchr(entry, '\0', 32U);
        uint32_t offset = read_le32(entry + 32);
        uint32_t pixel_size = read_le32(entry + 36);
        uint32_t alpha_size = read_le32(entry + 40);
        uint32_t width = read_le32(entry + 44);
        uint32_t height = read_le32(entry + 48);
        uint32_t format = read_le32(entry + 52);
        lv_color_format_t color_format;
        uint32_t stride;

        if (!name_end || !checked_span(size, offset, pixel_size) ||
            pixel_size > UINT32_MAX - alpha_size ||
            !checked_span(size, offset, pixel_size + alpha_size) ||
            image_format(format, width, height, pixel_size, alpha_size, &color_format, &stride) != 0) {
            fprintf(stderr, "ERROR: Invalid asset pack entry %u\n", i);
            memset(pack, 0, sizeof(*pack));
            return -1;
        }

        asset_pack_entry_t *out = &pack->entries[i];
        memcpy(out->symbol, entry, (size_t)(name_end - entry));
        out->image.header.magic = LV_IMAGE_HEADER_MAGIC;
        out->image.header.cf = color_format;
        out->image.header.flags = 0;
        out->image.header.w = width;
        out->image.header.h = height;
        out->image.header.stride = stride;
        out->image.header.reserved_2 = 0;
        out->image.data_size = pixel_size + alpha_size;
        out->image.data = data + offset;
        out->image.reserved = NULL;
    }

    pack->count = count;
    return 0;
}

const lv_image_dsc_t *asset_pack_find(const asset_pack_t *pack, const char *symbol) {
    if (!pack || !symbol) return NULL;
    for (uint32_t i = 0; i < pack->count; i++) {
        if (strcmp(pack->entries[i].symbol, symbol) == 0) {
            return &pack->entries[i].image;
        }
    }
    return NULL;
}
