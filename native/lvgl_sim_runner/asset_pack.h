/**
 * Read-only asset-pack registry for the headless LVGL runner.
 *
 * The pack is encoded by mcp/lvgl_ir/asset_pack.py.  Its backing bytes are
 * owned by the caller and must remain alive while LVGL renders the scene.
 */
#ifndef LVGL_SIM_ASSET_PACK_H
#define LVGL_SIM_ASSET_PACK_H

#include <stddef.h>
#include <stdint.h>

#include "lvgl.h"

#define ASSET_PACK_MAX_ASSETS 128U

typedef struct {
    char symbol[32];
    lv_image_dsc_t image;
} asset_pack_entry_t;

typedef struct {
    asset_pack_entry_t entries[ASSET_PACK_MAX_ASSETS];
    uint32_t count;
} asset_pack_t;

/**
 * Parse a packed, read-only asset buffer.
 *
 * @return 0 on success, non-zero if the pack violates the protocol.
 */
int asset_pack_load(asset_pack_t *pack, const uint8_t *data, size_t size);

/** Look up an image descriptor by its exact ASCII symbol. */
const lv_image_dsc_t *asset_pack_find(const asset_pack_t *pack, const char *symbol);

#endif /* LVGL_SIM_ASSET_PACK_H */
