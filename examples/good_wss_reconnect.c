/**
 * @file good_wss_reconnect.c
 * @brief 范例：WSS 状态机 + SNTP 前置 + 指数退避重连
 *
 * 文件归属: network_wss_task.c (Model 层)
 * 配对反例: bad_wss_blocking.c（tight loop / 无 SNTP）
 * 配对正例: good_wss_json_parse.c（解析与 Queue 投递）
 *
 * 要点:
 *   1. WiFi IP → SNTP → time() 有效 → 再 TLS
 *   2. 断线指数退避 1s→2s→…→60s，禁止 tight loop
 *   3. 解析与 UI 分离；payload heap → Presenter
 */

#include "app_mvp.h"
#include "FreeRTOS.h"
#include "task.h"
#include "queue.h"
#include <string.h>
#include <stdio.h>
#include <time.h>

#define WSS_TASK_STACK           (6144)
#define WSS_TASK_PRIO            (tskIDLE_PRIORITY + 4)
#define WSS_EVT_QUEUE_LEN        (4)
#define WSS_RECONNECT_BASE_MS    (1000)
#define WSS_RECONNECT_MAX_MS     (60000)

extern int  wifi_wait_ip(uint32_t timeout_ms);
extern int  sntp_sync_wait(uint32_t timeout_ms);
extern int  wss_connect(const char *url);
extern int  wss_recv(char *buf, size_t max_len, uint32_t timeout_ms);
extern void wss_disconnect(void);

static QueueHandle_t s_net_evt_queue = NULL;
static TaskHandle_t  s_wss_task_hdl  = NULL;
static wss_state_t   s_wss_state     = WSS_ST_DISCONNECTED;
static uint32_t      s_backoff_ms    = WSS_RECONNECT_BASE_MS;

static bool net_emit_event(net_evt_type_t type, char *payload, size_t len)
{
    if (s_net_evt_queue == NULL) {
        if (payload != NULL) {
            vPortFree(payload);
        }
        return false;
    }

    net_evt_t evt = { .type = type, .payload = payload, .len = len };

    if (xQueueSend(s_net_evt_queue, &evt, pdMS_TO_TICKS(50)) != pdTRUE) {
        if (payload != NULL) {
            vPortFree(payload);
        }
        return false;
    }
    return true;
}

static bool network_prereq_ready(void)
{
    if (wifi_wait_ip(30000) != 0) {
        return false;
    }
    if (sntp_sync_wait(15000) != 0) {
        return false;
    }
    return time(NULL) > 1577836800; /* 2020-01-01，证书 notBefore 有效 */
}

static void wss_backoff_wait(void)
{
    vTaskDelay(pdMS_TO_TICKS(s_backoff_ms));
    if (s_backoff_ms < WSS_RECONNECT_MAX_MS) {
        s_backoff_ms *= 2;
        if (s_backoff_ms > WSS_RECONNECT_MAX_MS) {
            s_backoff_ms = WSS_RECONNECT_MAX_MS;
        }
    }
}

static void wss_reset_backoff(void)
{
    s_backoff_ms = WSS_RECONNECT_BASE_MS;
}

static void wss_session_loop(void)
{
    char recv_buf[2048];

    for (;;) {
        int n = wss_recv(recv_buf, sizeof(recv_buf) - 1, 5000);
        if (n < 0) {
            s_wss_state = WSS_ST_ERROR;
            net_emit_event(NET_EVT_ERROR, NULL, 0);
            break;
        }
        if (n == 0) {
            continue;
        }
        recv_buf[n] = '\0';

        char *copy = (char *)pvPortMalloc((size_t)n + 1);
        if (copy != NULL) {
            memcpy(copy, recv_buf, (size_t)n + 1);
            net_emit_event(NET_EVT_DATA, copy, (size_t)n);
        }
    }
}

static void wss_task(void *arg)
{
    (void)arg;
    const char *url = "wss://api.example.com/v1/stream";

    for (;;) {
        if (!network_prereq_ready()) {
            wss_backoff_wait();
            continue;
        }

        s_wss_state = WSS_ST_CONNECTING;
        wss_disconnect();

        if (wss_connect(url) != 0) {
            s_wss_state = WSS_ST_ERROR;
            net_emit_event(NET_EVT_ERROR, NULL, 0);
            wss_backoff_wait();
            continue;
        }

        s_wss_state = WSS_ST_CONNECTED;
        wss_reset_backoff();
        net_emit_event(NET_EVT_CONNECTED, NULL, 0);
        wss_session_loop();

        wss_disconnect();
        s_wss_state = WSS_ST_DISCONNECTED;
        wss_backoff_wait();
    }
}

QueueHandle_t network_get_evt_queue(void)
{
    return s_net_evt_queue;
}

void network_wss_reconnect_task_start(void)
{
    if (s_net_evt_queue == NULL) {
        s_net_evt_queue = xQueueCreate(WSS_EVT_QUEUE_LEN, sizeof(net_evt_t));
        configASSERT(s_net_evt_queue != NULL);
    }

    if (s_wss_task_hdl == NULL) {
        BaseType_t ret = xTaskCreate(
            wss_task,
            "WssReconnect",
            WSS_TASK_STACK,
            NULL,
            WSS_TASK_PRIO,
            &s_wss_task_hdl
        );
        configASSERT(ret == pdPASS);
    }
}
