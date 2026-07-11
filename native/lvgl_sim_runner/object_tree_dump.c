/**
 * Object Tree Dump Implementation
 */

#include "object_tree_dump.h"
#include "lvgl.h"
#include <stdio.h>
#include <string.h>

/* ── Binary format ─────────────────────────────────────────────── */

#define TREE_MAGIC  0x00454554  /* "TEE\0" */
#define TREE_MAX_DEPTH 32

#if defined(_MSC_VER)
#pragma pack(push, 1)
#define LVGL_SIM_PACKED
#else
#define LVGL_SIM_PACKED __attribute__((packed))
#endif

typedef struct {
    uint32_t magic;
    uint32_t version;
    uint32_t display_width;
    uint32_t display_height;
    uint32_t node_count;
} LVGL_SIM_PACKED tree_header_t;

typedef struct {
    uint32_t type_id;       /* Widget type enum */
    int32_t  x, y;
    int32_t  width, height;
    uint32_t flags;         /* visible, clickable, etc. */
    uint32_t child_count;
    uint32_t text_offset;   /* offset into string table, 0 if no text */
    uint32_t value;         /* for bar/slider */
    uint32_t reserved[2];
} LVGL_SIM_PACKED tree_node_t;

#if defined(_MSC_VER)
#pragma pack(pop)
#endif
#undef LVGL_SIM_PACKED

/* ── Widget type IDs ───────────────────────────────────────────── */

static uint32_t get_type_id(lv_obj_t *obj) {
    const lv_obj_class_t *cls = lv_obj_get_class(obj);
    if (cls == &lv_obj_class) return 1;      /* container */
    if (cls == &lv_label_class) return 2;    /* label */
    if (cls == &lv_btn_class) return 3;      /* button */
#if LVGL_VERSION_MAJOR >= 9
    if (cls == &lv_image_class) return 4;    /* image */
#else
    if (cls == &lv_img_class) return 4;      /* image */
#endif
    if (cls == &lv_bar_class) return 5;      /* bar */
    if (cls == &lv_slider_class) return 6;   /* slider */
    if (cls == &lv_switch_class) return 7;   /* switch */
    if (cls == &lv_checkbox_class) return 8; /* checkbox */
    if (cls == &lv_dropdown_class) return 9; /* dropdown */
    if (cls == &lv_arc_class) return 10;     /* arc */
    if (cls == &lv_spinner_class) return 11; /* spinner */
    return 0;  /* unknown */
}

/* ── String table builder ──────────────────────────────────────── */

#define MAX_STRINGS 256
#define MAX_STRING_LEN 256

static char g_strings[MAX_STRINGS][MAX_STRING_LEN];
static uint32_t g_string_offsets[MAX_STRINGS];
static uint32_t g_string_count = 0;
static uint32_t g_string_total_size = 0;

static uint32_t add_string(const char *s) {
    if (!s || s[0] == '\0') return 0;

    /* Check if already added */
    for (uint32_t i = 0; i < g_string_count; i++) {
        if (strcmp(g_strings[i], s) == 0) {
            return g_string_offsets[i];
        }
    }

    if (g_string_count >= MAX_STRINGS) return 0;

    uint32_t offset = g_string_total_size;
    strncpy(g_strings[g_string_count], s, MAX_STRING_LEN - 1);
    g_string_offsets[g_string_count] = offset;
    g_string_count++;
    g_string_total_size += strlen(s) + 1;

    return offset;
}

/* ── Tree traversal ────────────────────────────────────────────── */

#define MAX_NODES 512

static tree_node_t g_nodes[MAX_NODES];
static uint32_t g_node_count = 0;

static void traverse_object(lv_obj_t *obj, int depth) {
    if (!obj || depth > TREE_MAX_DEPTH || g_node_count >= MAX_NODES) return;

    tree_node_t *node = &g_nodes[g_node_count++];
    memset(node, 0, sizeof(tree_node_t));

    /* Get type */
    node->type_id = get_type_id(obj);

    /* Get position and size */
    lv_area_t coords;
    lv_obj_get_coords(obj, &coords);
    node->x = coords.x1;
    node->y = coords.y1;
    node->width = coords.x2 - coords.x1 + 1;
    node->height = coords.y2 - coords.y1 + 1;

    /* Flags */
    node->flags = 0;
    if (lv_obj_is_visible(obj)) node->flags |= 1;
    if (lv_obj_has_flag(obj, LV_OBJ_FLAG_CLICKABLE)) node->flags |= 2;

    /* Text (for labels) */
    if (node->type_id == 2) {  /* label */
        const char *text = lv_label_get_text(obj);
        node->text_offset = add_string(text);
    }

    /* Value (for bar) */
    if (node->type_id == 5) {  /* bar */
        node->value = (uint32_t)lv_bar_get_value(obj);
    }

    /* Children */
    uint32_t child_count = (uint32_t)lv_obj_get_child_count(obj);
    node->child_count = child_count;

    for (uint32_t i = 0; i < child_count; i++) {
        lv_obj_t *child = lv_obj_get_child(obj, i);
        traverse_object(child, depth + 1);
    }
}

/* ── File writing ──────────────────────────────────────────────── */

int object_tree_dump(const char *path, int width, int height) {
    /* Reset state */
    g_string_count = 0;
    g_string_total_size = 0;
    g_node_count = 0;

    /* Add empty string at offset 0 */
    add_string("");

    /* Traverse active screen */
    lv_obj_t *scr = lv_display_get_screen_active(lv_display_get_default());
    if (!scr) {
        fprintf(stderr, "WARNING: No active screen\n");
        return -1;
    }

    traverse_object(scr, 0);

    /* Write file */
    FILE *f = fopen(path, "wb");
    if (!f) {
        fprintf(stderr, "ERROR: Cannot create %s\n", path);
        return -1;
    }

    /* Header */
    tree_header_t header = {
        .magic = TREE_MAGIC,
        .version = 1,
        .display_width = (uint32_t)width,
        .display_height = (uint32_t)height,
        .node_count = g_node_count,
    };
    fwrite(&header, sizeof(header), 1, f);

    /* String table size */
    fwrite(&g_string_total_size, sizeof(uint32_t), 1, f);

    /* String table */
    for (uint32_t i = 0; i < g_string_count; i++) {
        fwrite(g_strings[i], 1, strlen(g_strings[i]) + 1, f);
    }

    /* Nodes */
    fwrite(g_nodes, sizeof(tree_node_t), g_node_count, f);

    fclose(f);

    fprintf(stderr, "Object tree: %u nodes, %u strings\n", g_node_count, g_string_count);
    return 0;
}
