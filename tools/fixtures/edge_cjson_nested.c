// Edge case: cJSON deep nesting with proper cleanup
// Tests that cjson_leak_checker does not false-positive on complex but correct patterns
#include "cJSON.h"
#include <stdlib.h>

// Correct: nested cJSON with goto cleanup
int parse_nested_config(const char *json_str)
{
    cJSON *root = NULL;
    cJSON *level1 = NULL;
    cJSON *level2 = NULL;
    cJSON *level3 = NULL;
    cJSON *level4 = NULL;
    cJSON *level5 = NULL;
    int result = -1;

    root = cJSON_Parse(json_str);
    if (!root) goto cleanup;

    level1 = cJSON_GetObjectItem(root, "config");
    if (!level1) goto cleanup;

    level2 = cJSON_GetObjectItem(level1, "network");
    if (!level2) goto cleanup;

    level3 = cJSON_GetObjectItem(level2, "wifi");
    if (!level3) goto cleanup;

    level4 = cJSON_GetObjectItem(level3, "ap");
    if (!level4) goto cleanup;

    level5 = cJSON_GetObjectItem(level4, "ssid");
    if (!level5) goto cleanup;

    // All levels accessed successfully
    result = 0;

cleanup:
    // root owns all children, only delete root
    if (root) cJSON_Delete(root);
    return result;
}

// Correct: cJSON in loop with per-iteration delete
int parse_json_array(const char *json_str)
{
    cJSON *array = cJSON_Parse(json_str);
    if (!array) return -1;

    int count = cJSON_GetArraySize(array);
    for (int i = 0; i < count; i++) {
        cJSON *item = cJSON_GetArrayItem(array, i);
        if (item) {
            cJSON *name = cJSON_GetObjectItem(item, "name");
            if (name && name->valuestring) {
                // process name
            }
        }
        // No per-item delete needed — array owns items
    }

    cJSON_Delete(array);
    return 0;
}
