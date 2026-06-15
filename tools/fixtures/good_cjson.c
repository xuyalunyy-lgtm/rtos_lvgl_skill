/* fixture: cJSON Parse/Delete 成对 — 期望 cjson_leak_checker 通过 */
#include "cJSON.h"

static void parse_ok(const char *json)
{
    cJSON *root = cJSON_Parse(json);
    if (root == NULL) {
        return;
    }
    cJSON_Delete(root);
}
