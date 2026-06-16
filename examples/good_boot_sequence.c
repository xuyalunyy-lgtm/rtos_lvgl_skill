/**
 * @file good_boot_sequence.c
 * @brief ✅ 正例：MVP 启动顺序 — Queue/Presenter → LVGL → WiFi → SNTP → WSS
 *
 * 文件归属: app_main.c / system_init.c（编排层，非 Model 内部）
 *
 * 约束: C8.1–C8.6
 * 对照: bad_wss_blocking.c（SNTP 缺失、tight 重连、回调重活）
 */

#include "FreeRTOS.h"
#include "task.h"
#include "queue.h"
#include "app_mvp.h"

extern void presenter_task(void *arg);
extern void lvgl_task(void *arg);
extern void wss_task(void *arg);
extern void wifi_start_sta(void);
extern void wifi_register_event_handlers(void);
extern bool sntp_wait_synced(uint32_t timeout_ms);

static QueueHandle_t s_net_q;
static TaskHandle_t s_presenter_hdl;
static TaskHandle_t s_lvgl_hdl;
static TaskHandle_t s_wss_hdl;

/* C8.1 — 消费链路先于生产者 */
static void mvp_queues_and_presenter_init(void)
{
    s_net_q = xQueueCreate(NET_QUEUE_DEPTH, sizeof(net_evt_t));
    configASSERT(s_net_q != NULL);
    xTaskCreate(presenter_task, "presenter", 3072, NULL, 5, &s_presenter_hdl);
}

/* C8.1 + C8.4 — View 任务独立，不在 init 里跑 lv_timer_handler 长循环 */
static void mvp_view_init(void)
{
    xTaskCreate(lvgl_task, "lvgl", 6144, NULL, 4, &s_lvgl_hdl);
}

/* C8.2 — WiFi 事件回调在 Presenter 就绪后注册；回调内仅 Queue（见 good_wss_json_parse.c） */
static void mvp_network_bringup(void)
{
    wifi_register_event_handlers();
    wifi_start_sta();
}

/* C8.5 — WSS 单任务，幂等创建 */
static void mvp_wss_start_once(void)
{
    if (s_wss_hdl != NULL) {
        return;
    }
    xTaskCreate(wss_task, "wss", 6144, NULL, 7, &s_wss_hdl);
}

/**
 * 平台 app_main / user_app_main 在 SDK init 完成后调用。
 * C8.6 — 此处不阻塞 TLS 握手，只编排任务创建顺序。
 */
void app_mvp_boot(void)
{
    mvp_queues_and_presenter_init();
    mvp_view_init();
    mvp_network_bringup();

    /* WiFi 获 IP 事件回调中（非此处阻塞）：
     *   1) sntp_wait_synced(10000)
     *   2) mvp_wss_start_once()
     */
    (void)sntp_wait_synced;
}
