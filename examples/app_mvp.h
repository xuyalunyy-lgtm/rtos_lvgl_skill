/**
 * @file app_mvp.h
 * @brief MVP 跨层共享类型（量产工程统一头；examples/ 教学 .c 可独立编译故重复 typedef）
 *
 * 文件归属: Core/Inc/ 或 apps/<product>/include/
 * 配对范例: good_wss_json_parse.c, good_presenter_consumer.c, good_mvp_pattern.c
 */

#ifndef APP_MVP_H
#define APP_MVP_H

#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ── 网络 Model → Presenter 事件 ─────────────────────── */

typedef enum {
    NET_EVT_CONNECTED = 0,
    NET_EVT_DATA,
    NET_EVT_ERROR,
} net_evt_type_t;

typedef struct {
    net_evt_type_t type;
    char *payload;      /* Model pvPortMalloc → Presenter vPortFree；禁止传 cJSON* */
    size_t len;
} net_evt_t;

/* ── UI View → Presenter 事件 ──────────────────────────── */

typedef enum {
    UI_EVT_BTN_CLICKED = 0,
    UI_EVT_UPDATE_STATUS,
} ui_evt_type_t;

typedef struct {
    ui_evt_type_t type;
    int param;
} ui_evt_t;

/* ── lv_async_call 载荷（View 层分配 → async 回调释放） ── */

#define APP_MVP_UI_TEXT_LEN  (64)

typedef struct {
    char text[APP_MVP_UI_TEXT_LEN];
} app_mvp_ui_async_t;

/* ── WSS 状态机（Model 层，见 prompts/mbedtls_wss_memory.txt） ── */

typedef enum {
    WSS_ST_DISCONNECTED = 0,
    WSS_ST_CONNECTING,
    WSS_ST_HANDSHAKING,
    WSS_ST_CONNECTED,
    WSS_ST_ERROR,
} wss_state_t;

#ifdef __cplusplus
}
#endif

#endif /* APP_MVP_H */
