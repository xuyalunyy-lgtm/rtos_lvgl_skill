/**
 * 反例 — C12 错误处理违规
 *
 * 违反约束:
 *   C12.1 — FreeRTOS API 返回值未检查
 *   C12.2 — malloc 失败后直接解引用 NULL
 *   C12.4 — 多资源函数 early return 不释放已获取资源
 *
 * 对照正例: error_handling.txt goto cleanup 模板
 */

#include "app_mvp.h"
#include <string.h>

/* ========== 反例 1: xTaskCreate 返回值未检查 (C12.1) ========== */

/* ❌ 创建失败时无感知，后续调度全部静默失败 */
static void bad_create_tasks(void)
{
    xTaskCreate(network_task, "wss", 4096, NULL, 5, NULL);
    xTaskCreate(presenter_task, "pres", 2048, NULL, 3, NULL);
    xTaskCreate(lvgl_task, "lvgl", 8192, NULL, 4, NULL);
}

/* ========== 反例 2: pvPortMalloc 失败后 NULL 解引用 (C12.2) ========== */

/* ❌ 内存不足时 HardFault */
static void bad_parse_and_send(const char *json)
{
    char *buf = pvPortMalloc(1024);
    /* 未检查 buf == NULL */
    memcpy(buf, json, strlen(json) + 1);  /* NULL 解引用 → HardFault */

    xQueueSend(s_queue, &buf, portMAX_DELAY);
}

/* ========== 反例 3: early return 不释放资源 (C12.4) ========== */

/* ❌ socket 创建后 malloc 失败，直接 return，socket 泄漏 */
static int bad_connect(const char *host, int port)
{
    int sock = socket(AF_INET, SOCK_STREAM, 0);
    if (sock < 0) {
        return -1;
    }

    char *buf = pvPortMalloc(4096);
    if (buf == NULL) {
        return -1;  /* 遗漏: 未 close(sock) → socket 泄漏 */
    }

    /* ... 使用 buf ... */

    vPortFree(buf);
    close(sock);
    return 0;
}

/* ========== 反例 4: configASSERT 用于可恢复错误 (C12.5) ========== */

/* ❌ JSON 解析失败不应 assert（输入来自网络，不可控） */
static void bad_parse_config(const char *json)
{
    cJSON *root = cJSON_Parse(json);
    configASSERT(root != NULL);  /* 应该 return error，不是 assert */

    /* ... */
    cJSON_Delete(root);
}