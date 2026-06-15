/**
 * @file good_wss_json_parse.c
 * @brief 范例：FreeRTOS WSS 任务中安全接收数据、cJSON 解析、Queue 投递 Presenter
 *
 * 文件归属: network_wss_task.c (Model 层)
 * 架构:     Model 只做网络+解析，结果经 Queue 送 Presenter，禁止操作 UI
 * 类型:     使用 app_mvp.h（与 mvp_codegen 输出一致）
 */

#include "app_mvp.h"
#include "FreeRTOS.h"
#include "task.h"
#include "queue.h"
#include "cJSON.h"
#include <string.h>
#include <stdio.h>

/* net_evt_t 见 app_mvp.h */

#define WSS_TASK_STACK      (1536)
#define WSS_TASK_PRIO       (tskIDLE_PRIORITY + 4)
#define WSS_EVT_QUEUE_LEN   (4)
#define WSS_RECV_BUF_SIZE   (2048)

static QueueHandle_t s_net_evt_queue = NULL;
static TaskHandle_t  s_wss_task_hdl  = NULL;

/* 前向声明：平台相关 WSS 接口 */
extern int  wss_connect(const char *url);
extern int  wss_recv(char *buf, size_t max_len, uint32_t timeout_ms);
extern void wss_disconnect(void);

/* ── 安全解析：所有分支均释放 cJSON ─────────────────────── */

static char *parse_message_text(const char *json_str)
{
    if (json_str == NULL) {
        return NULL;
    }

    cJSON *root = cJSON_Parse(json_str);
    if (root == NULL) {
        return NULL;
    }

    char *result = NULL;
    cJSON *text_item = cJSON_GetObjectItemCaseSensitive(root, "text");

    if (cJSON_IsString(text_item) && (text_item->valuestring != NULL)) {
        size_t slen = strlen(text_item->valuestring);
        result = (char *)pvPortMalloc(slen + 1);
        if (result != NULL) {
            memcpy(result, text_item->valuestring, slen + 1);
        }
    }

    cJSON_Delete(root);   /* ✅ 唯一出口前必 Delete */
    return result;
}

/* ── 投递事件到 Presenter Queue ───────────────────────── */

static bool net_emit_event(net_evt_type_t type, char *payload, size_t len)
{
    if (s_net_evt_queue == NULL) {
        if (payload != NULL) {
            vPortFree(payload);
        }
        return false;
    }

    net_evt_t evt = {
        .type    = type,
        .payload = payload,
        .len     = len,
    };

    if (xQueueSend(s_net_evt_queue, &evt, pdMS_TO_TICKS(50)) != pdTRUE) {
        if (payload != NULL) {
            vPortFree(payload);
        }
        return false;
    }
    return true;
}

/* ── WSS 主任务 ─────────────────────────────────────────── */

static void wss_task(void *arg)
{
    (void)arg;
    char recv_buf[WSS_RECV_BUF_SIZE];

    if (wss_connect("wss://api.example.com/v1/stream") != 0) {
        net_emit_event(NET_EVT_ERROR, NULL, 0);
        vTaskDelete(NULL);
        return;
    }

    net_emit_event(NET_EVT_CONNECTED, NULL, 0);

    for (;;) {
        int n = wss_recv(recv_buf, sizeof(recv_buf) - 1, 5000);
        if (n < 0) {
            net_emit_event(NET_EVT_ERROR, NULL, 0);
            break;
        }
        if (n == 0) {
            continue;
        }

        recv_buf[n] = '\0';

        /* 解析 JSON，提取业务字段 */
        char *text = parse_message_text(recv_buf);
        if (text != NULL) {
            net_emit_event(NET_EVT_DATA, text, strlen(text));
        }
        /* parse_message_text 内部已 cJSON_Delete，text 由 Presenter 释放 */
    }

    wss_disconnect();
    vTaskDelete(NULL);
}

/* ── 公开 API ───────────────────────────────────────────── */

QueueHandle_t network_get_evt_queue(void)
{
    return s_net_evt_queue;
}

void network_wss_task_start(void)
{
    if (s_net_evt_queue == NULL) {
        s_net_evt_queue = xQueueCreate(WSS_EVT_QUEUE_LEN, sizeof(net_evt_t));
        configASSERT(s_net_evt_queue != NULL);
    }

    if (s_wss_task_hdl == NULL) {
        BaseType_t ret = xTaskCreate(
            wss_task,
            "WssTask",
            WSS_TASK_STACK,
            NULL,
            WSS_TASK_PRIO,
            &s_wss_task_hdl
        );
        configASSERT(ret == pdPASS);
    }
}
