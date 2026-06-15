/**
 * @file bad_cjson_leak.c
 * @brief ❌ 反例：cJSON 泄漏典型写法 — 严禁模仿
 *
 * 典型后果:
 *   - 运行数小时后堆耗尽，malloc/wss 握手失败
 *   - 看门狗复位、随机 HardFault
 *
 * 正确做法: good_wss_json_parse.c + prompts/cjson_safe_parse.txt
 * 审查工具: python tools/cjson_leak_checker.py bad_cjson_leak.c
 */

#include "cJSON.h"
#include <stdlib.h>
#include <string.h>

/* ❌ 错误 1：early return 遗漏 Delete */
static int parse_version_bad(const char *json)
{
    cJSON *root = cJSON_Parse(json);
    if (root == NULL) {
        return -1;
    }

    cJSON *ver = cJSON_GetObjectItem(root, "version");
    if (ver == NULL || !cJSON_IsNumber(ver)) {
        return -2;   /* ❌ 泄漏：root 未 Delete */
    }

    int v = ver->valueint;
    cJSON_Delete(root);
    return v;
}

/* ❌ 错误 2：条件分支只 Delete 部分路径 */
static char *extract_text_bad(const char *json)
{
    if (json == NULL) {
        return NULL;
    }

    cJSON *root = cJSON_Parse(json);
    if (root == NULL) {
        return NULL;
    }

    cJSON *text = cJSON_GetObjectItem(root, "text");
    if (!cJSON_IsString(text)) {
        cJSON_Delete(root);
        return NULL;
    }

    char *copy = strdup(text->valuestring);
    if (copy == NULL) {
        return NULL;   /* ❌ 泄漏：strdup 失败时 root 未 Delete */
    }

    cJSON_Delete(root);
    return copy;
}

/* ❌ 错误 3：循环中 Parse 不 Delete（网络接收最常见） */
static void on_wss_messages_bad(const char *json_batch[], int count)
{
    for (int i = 0; i < count; i++) {
        cJSON *root = cJSON_Parse(json_batch[i]);
        if (root == NULL) {
            continue;
        }
        /* 处理 ... */
        /* ❌ 泄漏：循环内从未 cJSON_Delete(root) */
    }
}

/* ❌ 错误 4：goto 只在一个 label 释放 */
static int parse_config_bad(const char *json, char *out, size_t out_len)
{
    cJSON *root = cJSON_Parse(json);
    if (root == NULL) {
        goto fail;
    }

    cJSON *name = cJSON_GetObjectItem(root, "name");
    if (!cJSON_IsString(name)) {
        goto fail;   /* ❌ 若 fail 标签未 Delete，则泄漏 */
    }

    strncpy(out, name->valuestring, out_len - 1);
    out[out_len - 1] = '\0';
    cJSON_Delete(root);
    return 0;

fail:
    return -1;       /* ❌ root 未 Delete */
}

/* ✅ 正确写法对照：统一 cleanup 出口 */
static int parse_config_good(const char *json, char *out, size_t out_len)
{
    int ret = -1;
    cJSON *root = NULL;

    if (json == NULL || out == NULL || out_len == 0) {
        return -1;
    }

    root = cJSON_Parse(json);
    if (root == NULL) {
        goto cleanup;
    }

    cJSON *name = cJSON_GetObjectItemCaseSensitive(root, "name");
    if (!cJSON_IsString(name) || name->valuestring == NULL) {
        goto cleanup;
    }

    strncpy(out, name->valuestring, out_len - 1);
    out[out_len - 1] = '\0';
    ret = 0;

cleanup:
    if (root != NULL) {
        cJSON_Delete(root);
    }
    return ret;
}

/*
 * 修复清单:
 *  [ ] 每个 Parse 对应唯一 cleanup 路径（goto cleanup 或 do-while(0)）
 *  [ ] 循环内 Parse 必须在 continue/break 前 Delete
 *  [ ] cJSON 树不得跨 Queue 传递 — 只传提取后的 plain data
 *  [ ] 跑 cjson_leak_checker.py 验证
 */
