/**
 * Scene Decoder — reads scene.bin and creates LVGL widgets.
 */

#ifndef SCENE_DECODER_H
#define SCENE_DECODER_H

#include <stdint.h>
#include "lvgl.h"
#include "framebuffer_display.h"

/* ── Scene file format ─────────────────────────────────────────── */

#define SCENE_MAGIC         0x004E4353  /* "SCN\0" */
#define SCENE_VERSION       2
#define SCENE_MAX_NODES     512
#define SCENE_MAX_DEPTH     32
#define SCENE_MAX_STRING    4096

/* ── Opcodes ───────────────────────────────────────────────────── */

typedef enum {
    OP_END              = 0,
    OP_CREATE_SCREEN    = 1,
    OP_CREATE_CONTAINER = 2,
    OP_CREATE_LABEL     = 3,
    OP_CREATE_BUTTON    = 4,
    OP_CREATE_IMAGE     = 5,
    OP_CREATE_BAR       = 6,
    OP_CREATE_SLIDER    = 7,
    OP_CREATE_SWITCH    = 8,
    OP_CREATE_CHECKBOX  = 9,
    OP_CREATE_DROPDOWN  = 10,
    OP_CREATE_SPINNER   = 11,
    OP_CREATE_ARC       = 12,

    OP_SET_PARENT       = 20,
    OP_SET_SIZE         = 21,
    OP_SET_TEXT         = 22,
    OP_SET_VALUE        = 23,
    OP_SET_RANGE        = 24,
    OP_SET_IMAGE_SOURCE = 25,

    OP_SET_FLEX_FLOW    = 30,
    OP_SET_FLEX_ALIGN   = 31,
    OP_SET_PAD_GAP      = 32,
    OP_SET_PAD          = 33,

    OP_SET_STYLE_BG_COLOR     = 40,
    OP_SET_STYLE_BG_OPA       = 41,
    OP_SET_STYLE_RADIUS       = 42,
    OP_SET_STYLE_BORDER_WIDTH = 43,
    OP_SET_STYLE_BORDER_COLOR = 44,
    OP_SET_STYLE_TEXT_COLOR   = 45,
    OP_SET_STYLE_WIDTH        = 49,
    OP_SET_STYLE_HEIGHT       = 50,

    OP_SET_EVENT_CLICKED       = 60,
    OP_SET_EVENT_VALUE_CHANGED = 61,

    OP_SET_NODE_ID      = 70,
    OP_SET_SOURCE_BBOX  = 71,
} scene_opcode_t;

/* ── Command header ────────────────────────────────────────────── */

typedef struct {
    uint16_t opcode;
    uint16_t size;
    uint32_t node_id;
} __attribute__((packed)) scene_cmd_header_t;

/* ── Scene header ──────────────────────────────────────────────── */

typedef struct {
    uint32_t magic;
    uint32_t version;
    uint32_t node_count;
    uint32_t string_table_offset;
    uint32_t string_table_size;
    uint32_t command_offset;
    uint32_t command_size;
    uint32_t reserved;
} __attribute__((packed)) scene_header_t;

/* ── API ───────────────────────────────────────────────────────── */

/**
 * Decode scene.bin and create LVGL widgets.
 *
 * @param data      Scene file contents.
 * @param size      Scene file size.
 * @param display   Framebuffer display context.
 * @return 0 on success, non-zero on error.
 */
int scene_decode_and_execute(const uint8_t *data, size_t size, fb_display_t *display);

/**
 * Get string from scene string table.
 *
 * @param data      Scene file contents.
 * @param index     String index.
 * @return String pointer, or NULL if invalid.
 */
const char *scene_get_string(const uint8_t *data, uint32_t index);

#endif /* SCENE_DECODER_H */
