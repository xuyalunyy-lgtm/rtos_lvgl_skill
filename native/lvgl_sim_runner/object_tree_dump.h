/**
 * Object Tree Dump — traverses LVGL widget tree and outputs binary format.
 *
 * Python side converts to JSON.
 */

#ifndef OBJECT_TREE_DUMP_H
#define OBJECT_TREE_DUMP_H

#include <stdint.h>

/**
 * Dump object tree to binary file.
 *
 * @param path    Output file path.
 * @param width   Display width.
 * @param height  Display height.
 * @return 0 on success, non-zero on error.
 */
int object_tree_dump(const char *path, int width, int height);

#endif /* OBJECT_TREE_DUMP_H */
