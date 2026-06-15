/* fixture: early return 无 Delete — 期望 cjson_leak_checker 失败 */
#include "cJSON.h"

static void parse_leak(const char *json)
{
    cJSON *root = cJSON_Parse(json);
    if (root == NULL) {
        return;
    }
    /* missing cJSON_Delete */
}
