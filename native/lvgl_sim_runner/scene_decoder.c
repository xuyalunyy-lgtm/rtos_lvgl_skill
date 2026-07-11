/**
 * Scene Decoder Implementation
 */

#include "scene_decoder.h"
#include <stdio.h>
#include <string.h>

/* ── String table access ───────────────────────────────────────── */

static const uint8_t *g_string_table = NULL;
static uint32_t g_string_table_size = 0;

const char *scene_get_string(const uint8_t *data, uint32_t index) {
    if (!g_string_table || index >= g_string_table_size) {
        return NULL;
    }

    /* Walk null-terminated strings */
    uint32_t offset = 0;
    uint32_t current = 0;
    while (offset < g_string_table_size && current < index) {
        if (g_string_table[offset] == '\0') {
            current++;
            offset++;
            if (current == index) break;
        } else {
            offset++;
        }
    }

    if (current == index && offset < g_string_table_size) {
        return (const char *)(g_string_table + offset);
    }
    return NULL;
}

/* ── Node registry ─────────────────────────────────────────────── */

typedef struct {
    uint32_t id;
    lv_obj_t *obj;
    char name[64];
} node_entry_t;

static node_entry_t g_nodes[SCENE_MAX_NODES];
static uint32_t g_node_count = 0;

static lv_obj_t *find_node(uint32_t id) {
    for (uint32_t i = 0; i < g_node_count; i++) {
        if (g_nodes[i].id == id) return g_nodes[i].obj;
    }
    return NULL;
}

static void register_node(uint32_t id, lv_obj_t *obj, const char *name) {
    if (g_node_count >= SCENE_MAX_NODES) {
        fprintf(stderr, "WARNING: Max nodes exceeded\n");
        return;
    }
    g_nodes[g_node_count].id = id;
    g_nodes[g_node_count].obj = obj;
    if (name) {
        strncpy(g_nodes[g_node_count].name, name, sizeof(g_nodes[g_node_count].name) - 1);
    }
    g_node_count++;
}

/* ── Command execution ─────────────────────────────────────────── */

static int execute_command(const scene_cmd_header_t *cmd, const uint8_t *payload, fb_display_t *display) {
    lv_obj_t *obj = find_node(cmd->node_id);
    lv_obj_t *parent = NULL;

    switch (cmd->opcode) {
    case OP_END:
        return 0;  /* End of scene */

    case OP_CREATE_SCREEN: {
        lv_obj_t *scr = lv_display_get_screen_active(lv_display_get_default());
        register_node(cmd->node_id, scr, "screen");
        return 0;
    }

    case OP_CREATE_CONTAINER: {
        parent = obj ? obj : lv_display_get_screen_active(lv_display_get_default());
        lv_obj_t *container = lv_obj_create(parent);
        register_node(cmd->node_id, container, NULL);
        return 0;
    }

    case OP_CREATE_LABEL: {
        parent = find_node(cmd->node_id) ? obj : lv_display_get_screen_active(lv_display_get_default());
        /* We need to find parent from SET_PARENT command later */
        lv_obj_t *label = lv_label_create(parent);
        register_node(cmd->node_id, label, NULL);
        return 0;
    }

    case OP_CREATE_BUTTON: {
        parent = obj ? obj : lv_display_get_screen_active(lv_display_get_default());
        lv_obj_t *btn = lv_btn_create(parent);
        register_node(cmd->node_id, btn, NULL);
        return 0;
    }

    case OP_CREATE_IMAGE: {
        parent = obj ? obj : lv_display_get_screen_active(lv_display_get_default());
#if LVGL_VERSION_MAJOR >= 9
        lv_obj_t *img = lv_image_create(parent);
#else
        lv_obj_t *img = lv_img_create(parent);
#endif
        register_node(cmd->node_id, img, NULL);
        return 0;
    }

    case OP_CREATE_BAR: {
        parent = obj ? obj : lv_display_get_screen_active(lv_display_get_default());
        lv_obj_t *bar = lv_bar_create(parent);
        register_node(cmd->node_id, bar, NULL);
        return 0;
    }

    case OP_SET_PARENT: {
        if (cmd->size >= 4 && obj) {
            uint32_t parent_id;
            memcpy(&parent_id, payload, 4);
            lv_obj_t *new_parent = find_node(parent_id);
            if (new_parent) {
                lv_obj_set_parent(obj, new_parent);
            }
        }
        return 0;
    }

    case OP_SET_SIZE: {
        if (cmd->size >= 8 && obj) {
            int32_t w, h;
            memcpy(&w, payload, 4);
            memcpy(&h, payload + 4, 4);
            lv_obj_set_size(obj, w, h);
        }
        return 0;
    }

    case OP_SET_TEXT: {
        if (cmd->size >= 4 && obj) {
            uint32_t str_idx;
            memcpy(&str_idx, payload, 4);
            const char *text = scene_get_string(NULL, str_idx);
            if (text) {
                lv_label_set_text(obj, text);
            }
        }
        return 0;
    }

    case OP_SET_VALUE: {
        if (cmd->size >= 4 && obj) {
            int32_t value;
            memcpy(&value, payload, 4);
            lv_bar_set_value(obj, value, LV_ANIM_OFF);
        }
        return 0;
    }

    case OP_SET_RANGE: {
        if (cmd->size >= 8 && obj) {
            int32_t min_val, max_val;
            memcpy(&min_val, payload, 4);
            memcpy(&max_val, payload + 4, 4);
            lv_bar_set_range(obj, min_val, max_val);
        }
        return 0;
    }

    case OP_SET_FLEX_FLOW: {
        if (cmd->size >= 4 && obj) {
            uint32_t flow;
            memcpy(&flow, payload, 4);
            lv_flex_flow_t flex_flow = (flow == 0) ? LV_FLEX_FLOW_ROW : LV_FLEX_FLOW_COLUMN;
            lv_obj_set_flex_flow(obj, flex_flow);
        }
        return 0;
    }

    case OP_SET_PAD_GAP: {
        if (cmd->size >= 4 && obj) {
            int32_t gap;
            memcpy(&gap, payload, 4);
            lv_obj_set_style_pad_gap(obj, gap, 0);
        }
        return 0;
    }

    case OP_SET_STYLE_BG_COLOR: {
        if (cmd->size >= 4 && obj) {
            uint32_t color;
            memcpy(&color, payload, 4);
            lv_obj_set_style_bg_color(obj, lv_color_hex(color), 0);
        }
        return 0;
    }

    case OP_SET_STYLE_RADIUS: {
        if (cmd->size >= 4 && obj) {
            int32_t radius;
            memcpy(&radius, payload, 4);
            lv_obj_set_style_radius(obj, radius, 0);
        }
        return 0;
    }

    case OP_SET_STYLE_TEXT_COLOR: {
        if (cmd->size >= 4 && obj) {
            uint32_t color;
            memcpy(&color, payload, 4);
            lv_obj_set_style_text_color(obj, lv_color_hex(color), 0);
        }
        return 0;
    }

    case OP_SET_STYLE_WIDTH: {
        if (cmd->size >= 4 && obj) {
            int32_t w;
            memcpy(&w, payload, 4);
            lv_obj_set_width(obj, w);
        }
        return 0;
    }

    case OP_SET_STYLE_HEIGHT: {
        if (cmd->size >= 4 && obj) {
            int32_t h;
            memcpy(&h, payload, 4);
            lv_obj_set_height(obj, h);
        }
        return 0;
    }

    case OP_SET_STYLE_BG_OPA:
    case OP_SET_STYLE_BORDER_WIDTH:
    case OP_SET_STYLE_BORDER_COLOR:
    case OP_SET_EVENT_CLICKED:
    case OP_SET_EVENT_VALUE_CHANGED:
    case OP_SET_NODE_ID:
    case OP_SET_SOURCE_BBOX:
    case OP_SET_IMAGE_SOURCE:
    case OP_SET_STYLE_TEXT_FONT_SIZE:
    case OP_SET_PAD:
    case OP_SET_FLEX_ALIGN:
    case OP_CREATE_SLIDER:
    case OP_CREATE_SWITCH:
    case OP_CREATE_CHECKBOX:
    case OP_CREATE_DROPDOWN:
    case OP_CREATE_SPINNER:
    case OP_CREATE_ARC:
    case OP_SET_STYLE_SHADOW_WIDTH:
    case OP_SET_STYLE_TEXT_ALIGN:
    case OP_SET_GRID:
        /* Silently ignore unimplemented opcodes for now */
        return 0;

    default:
        fprintf(stderr, "WARNING: Unknown opcode %d\n", cmd->opcode);
        return 0;
    }
}

/* ── Main decode function ──────────────────────────────────────── */

int scene_decode_and_execute(const uint8_t *data, size_t size, fb_display_t *display) {
    if (size < sizeof(scene_header_t)) {
        fprintf(stderr, "ERROR: Scene too small (%zu bytes)\n", size);
        return -1;
    }

    /* Parse header */
    const scene_header_t *header = (const scene_header_t *)data;
    if (header->magic != SCENE_MAGIC) {
        fprintf(stderr, "ERROR: Invalid scene magic (got 0x%08X, expected 0x%08X)\n",
                header->magic, SCENE_MAGIC);
        return -1;
    }
    if (header->version != SCENE_VERSION) {
        fprintf(stderr, "ERROR: Unsupported scene version %d\n", header->version);
        return -1;
    }
    if (header->node_count > SCENE_MAX_NODES) {
        fprintf(stderr, "ERROR: Too many nodes (%d, max %d)\n", header->node_count, SCENE_MAX_NODES);
        return -1;
    }

    /* Validate offsets and sizes (overflow-safe) */
    if (header->string_table_offset > size ||
        header->string_table_size > size - header->string_table_offset) {
        fprintf(stderr, "ERROR: String table extends beyond scene file\n");
        return -1;
    }
    if (header->command_offset > size ||
        header->command_size > size - header->command_offset) {
        fprintf(stderr, "ERROR: Command section extends beyond scene file\n");
        return -1;
    }
    if (header->string_table_size > SCENE_MAX_STRING * 64) {
        fprintf(stderr, "ERROR: String table too large (%u bytes)\n", header->string_table_size);
        return -1;
    }

    /* Setup string table */
    g_string_table = data + header->string_table_offset;
    g_string_table_size = header->string_table_size;

    /* Reset node registry */
    g_node_count = 0;

    /* Execute commands */
    const uint8_t *cmd_data = data + header->command_offset;
    const uint8_t *cmd_end = cmd_data + header->command_size;
    uint32_t commands_executed = 0;

    while (cmd_data + sizeof(scene_cmd_header_t) <= cmd_end) {
        const scene_cmd_header_t *cmd = (const scene_cmd_header_t *)cmd_data;
        const uint8_t *payload = cmd_data + sizeof(scene_cmd_header_t);

        if (cmd->opcode == OP_END) {
            break;
        }

        if (payload + cmd->size > cmd_end) {
            fprintf(stderr, "ERROR: Command payload extends beyond scene\n");
            return -1;
        }

        int result = execute_command(cmd, payload, display);
        if (result != 0) {
            return result;
        }

        cmd_data = payload + cmd->size;
        commands_executed++;
    }

    fprintf(stderr, "Executed %u commands, %u nodes\n", commands_executed, g_node_count);
    return 0;
}
