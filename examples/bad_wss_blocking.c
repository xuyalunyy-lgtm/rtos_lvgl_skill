/**
 * @file bad_wss_blocking.c
 * @brief ❌ 反例：WSS/mbedTLS 任务栈不足、阻塞重连、回调里做重活 — 严禁模仿
 *
 * 文件归属: network_wss_task.c（错误写法示范）
 *
 * 典型后果:
 *   - STACK OVERFLOW @ WssTask（握手瞬间栈峰值）
 *   - heap 耗尽（tight loop 反复 TLS 握手）
 *   - 证书校验失败（SNTP 未同步）
 *   - 看门狗复位（回调中 vTaskDelay + cJSON 大解析）
 *
 * 正确做法: good_wss_json_parse.c + prompts/mbedtls_wss_memory.txt
 *   → 足够栈、SNTP 前置、指数退避、解析后 Queue 投 Presenter
 */

#include "FreeRTOS.h"
#include "task.h"
#include "cJSON.h"
#include "lvgl.h"
#include <string.h>
#include <stdio.h>

extern lv_obj_t *g_status_label;

extern int  wss_connect(const char *url);
extern int  wss_recv(char *buf, size_t max_len, uint32_t timeout_ms);
extern void wss_disconnect(void);

/* ❌ 错误 1：栈按 bytes 理解，实际 xTaskCreate 参数是 words → 仅 ~8KB，握手必溢出 */
#define WSS_TASK_STACK_WRONG   (2048)
#define WSS_TASK_PRIO          (tskIDLE_PRIORITY + 4)

static TaskHandle_t s_wss_hdl = NULL;

/* ❌ 错误 2：无退避，断线后立即重连 — TLS 握手反复分配耗尽显存 */
static void wss_reconnect_tight_loop(void)
{
    for (;;) {
        wss_disconnect();
        /* ❌ tight loop：无 vTaskDelay，CPU + heap 双杀 */
        if (wss_connect("wss://api.example.com/v1/stream") == 0) {
            break;
        }
    }
}

/* ❌ 错误 3：在 SDK 网络回调中阻塞 + 解析 + 改 UI（ESP esp_websocket 同理） */
void on_wss_data_callback(const char *json_str)
{
    if (json_str == NULL) {
        return;
    }

    /* ❌ 回调上下文栈浅，大 JSON 解析易溢出 */
    cJSON *root = cJSON_Parse(json_str);
    if (root == NULL) {
        lv_label_set_text(g_status_label, "Parse Error");
        return;
    }

    /* ❌ 在回调里 delay — 阻塞 esp_event / LwIP 线程 */
    vTaskDelay(pdMS_TO_TICKS(100));

    cJSON *cmd = cJSON_GetObjectItem(root, "command");
    if (cJSON_IsString(cmd)) {
        lv_label_set_text(g_status_label, cmd->valuestring);
    }

    cJSON_Delete(root);
}

/* ❌ 错误 4：主任务在 SNTP 之前启动 TLS（证书 notBefore 校验失败） */
static void wss_task(void *arg)
{
    (void)arg;
    char recv_buf[4096];

    /* ❌ 未等 WiFi IP + SNTP，直接 WSS — 量产常见握手 mysteriously fail */
    if (wss_connect("wss://api.example.com/v1/stream") != 0) {
        wss_reconnect_tight_loop();
    }

    for (;;) {
        int n = wss_recv(recv_buf, sizeof(recv_buf) - 1, 5000);
        if (n < 0) {
            wss_reconnect_tight_loop();
            continue;
        }
        if (n == 0) {
            continue;
        }
        recv_buf[n] = '\0';

        /* ❌ 在 WSS 任务里同步大解析 + 业务，应 extract plain data → Queue */
        on_wss_data_callback(recv_buf);
    }
}

void network_wss_task_start_wrong(void)
{
    BaseType_t ret = xTaskCreate(
        wss_task,
        "WssTask",
        WSS_TASK_STACK_WRONG,
        NULL,
        WSS_TASK_PRIO,
        &s_wss_hdl
    );
    (void)ret;
}

/*
 * ══════════════════════════════════════════════════════════
 *  修复清单（Code Review 时逐条对照）
 * ══════════════════════════════════════════════════════════
 *
 *  [ ] WSS 任务栈 ≥ 4096 words（ESP-IDF）或 stack_calculator 估算 ≥ 6144 bytes
 *  [ ] WiFi 获 IP → SNTP sync → 再 TLS（time() 有效）
 *  [ ] 重连指数退避 1s→2s→…→60s，禁止 tight loop
 *  [ ] recv/回调只做轻量工作；cJSON_Parse → 提取 heap copy → Delete → Queue
 *  [ ] 回调/WSS 任务禁止 lv_obj_*、禁止 vTaskDelay
 *  [ ] 对照 good_wss_json_parse.c 的 net_emit_event() + parse_message_text()
 *  [ ] 对照 bad_lvgl_cross_thread.c — UI 必须经 Presenter + lv_async_call
 */
