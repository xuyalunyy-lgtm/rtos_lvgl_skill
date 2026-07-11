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

/* Execution evidence is updated while commands are decoded, so these globals
 * must be declared before execute_command(). */
#define MAX_OPCODE 128
static uint8_t g_opcodes_hit[MAX_OPCODE];
static uint8_t g_opcodes_unsupported[MAX_OPCODE];
static uint32_t g_asset_requests = 0;
static uint32_t g_asset_hits = 0;

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

static int execute_command(const scene_cmd_header_t *cmd, const uint8_t *payload,
                           fb_display_t *display, const asset_pack_t *assets, const font_registry_t *fonts) {
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
        lv_obj_t *btn = lv_button_create(parent);
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
                if (lv_obj_check_type(obj, &lv_label_class)) {
                    lv_label_set_text(obj, text);
                } else if (lv_obj_check_type(obj, &lv_button_class)) {
                    /* Buttons are containers in LVGL v9; attach a real label
                     * instead of casting the button itself to lv_label_t. */
                    lv_obj_t *label = lv_label_create(obj);
                    if (!label) return -1;
                    lv_label_set_text(label, text);
                    lv_obj_center(label);
                } else {
                    fprintf(stderr, "ERROR: SET_TEXT target is not a label/button\n");
                    return -1;
                }
            }
        }
        return 0;
    }

    case OP_SET_IMAGE_SOURCE: {
        if (cmd->size != 4 || !obj) return -1;
        uint32_t str_idx;
        memcpy(&str_idx, payload, sizeof(str_idx));
        const char *symbol = scene_get_string(NULL, str_idx);
        g_asset_requests++;
        const lv_image_dsc_t *image = asset_pack_find(assets, symbol);
        if (!symbol || !image) {
            fprintf(stderr, "ERROR: Image asset not found: %s\n", symbol ? symbol : "<invalid>");
            return -1;
        }
        g_asset_hits++;
        lv_image_set_src(obj, image);
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

    case OP_SET_STYLE_BG_OPA: {
        if (cmd->size >= 4 && obj) {
            uint32_t opacity;
            memcpy(&opacity, payload, sizeof(opacity));
            lv_obj_set_style_bg_opa(obj, (lv_opa_t)opacity, 0);
        }
        return 0;
    }

    case OP_SET_STYLE_BORDER_WIDTH: {
        if (cmd->size >= 4 && obj) {
            int32_t width;
            memcpy(&width, payload, sizeof(width));
            lv_obj_set_style_border_width(obj, width, 0);
        }
        return 0;
    }

    case OP_SET_STYLE_BORDER_COLOR: {
        if (cmd->size >= 4 && obj) {
            uint32_t color;
            memcpy(&color, payload, sizeof(color));
            lv_obj_set_style_border_color(obj, lv_color_hex(color), 0);
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

    case OP_SET_STYLE_TEXT_FONT: {
        if (cmd->size != 4 || !obj) return -1;
        uint32_t str_idx;
        memcpy(&str_idx, payload, sizeof(str_idx));
        const char *font_id = scene_get_string(NULL, str_idx);
        const lv_font_t *font = font_registry_find(fonts, font_id);
        if (!font) {
            fprintf(stderr, "ERROR: Font asset not found: %s\n", font_id ? font_id : "<invalid>");
            return -1;
        }
        lv_obj_set_style_text_font(obj, font, 0);
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

    case OP_SET_SOURCE_BBOX: {
        if (cmd->size != 16 || !obj) return -1;
        int32_t x, y, width, height;
        memcpy(&x, payload, sizeof(x));
        memcpy(&y, payload + 4, sizeof(y));
        memcpy(&width, payload + 8, sizeof(width));
        memcpy(&height, payload + 12, sizeof(height));
        if (width <= 0 || height <= 0) return -1;
        lv_obj_set_pos(obj, x, y);
        lv_obj_set_size(obj, width, height);
        return 0;
    }

    case OP_SET_EVENT_CLICKED:
    case OP_SET_EVENT_VALUE_CHANGED:
    case OP_SET_NODE_ID:
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

/* ── Opcode tracking ───────────────────────────────────────────── */

void scene_decoder_reset_tracking(void) {
    memset(g_opcodes_hit, 0, sizeof(g_opcodes_hit));
    memset(g_opcodes_unsupported, 0, sizeof(g_opcodes_unsupported));
    g_asset_requests = 0;
    g_asset_hits = 0;
}

uint32_t scene_decoder_get_unsupported(uint16_t *out, uint32_t max_out) {
    uint32_t count = 0;
    for (uint16_t i = 0; i < MAX_OPCODE && count < max_out; i++) {
        if (g_opcodes_unsupported[i]) {
            out[count++] = i;
        }
    }
    return count;
}

uint32_t scene_decoder_get_asset_stats(uint32_t *requests, uint32_t *hits) {
    *requests = g_asset_requests;
    *hits = g_asset_hits;
    return 0;
}

/* ── Main decode function ──────────────────────────────────────── */

int scene_decode_and_execute(const uint8_t *data, size_t size, fb_display_t *display,
                             const asset_pack_t *assets, const font_registry_t *fonts) {
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
    scene_decoder_reset_tracking();

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

        int result = execute_command(cmd, payload, display, assets, fonts);

        /* Track opcode usage for capability reporting */
        if (cmd->opcode < MAX_OPCODE) {
            switch (cmd->opcode) {
            case OP_SET_EVENT_CLICKED:
            case OP_SET_EVENT_VALUE_CHANGED:
            case OP_SET_NODE_ID:
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
                g_opcodes_unsupported[cmd->opcode] = 1;
                break;
            default:
                g_opcodes_hit[cmd->opcode] = 1;
                break;
            }
        }

        if (result != 0) {
            return result;
        }

        cmd_data = payload + cmd->size;
        commands_executed++;
    }

    fprintf(stderr, "Executed %u commands, %u nodes\n", commands_executed, g_node_count);
    return 0;
}
