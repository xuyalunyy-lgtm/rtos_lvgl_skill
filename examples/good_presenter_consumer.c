/**
 * @file good_presenter_consumer.c
 * @brief 范例：Android Handler/Looper 风格的 Presenter 事件消费闭环
 *
 * 对标 Android:
 *   Model    ≈ Background Service / Retrofit 回调线程
 *   Queue    ≈ Handler.sendMessage() → MessageQueue
 *   Presenter≈ 主线程 Handler.handleMessage()（Looper 消费循环）
 *   View     ≈ runOnUiThread() / lv_async_call 刷新 UI
 *
 * 文件归属: app_presenter.c
 * 配对范例: good_wss_json_parse.c（Model 发消息端）
 *
 * 内存所有权:
 *   - cJSON root:     Model 解析函数内 Delete，不得进 Queue
 *   - payload 堆块:   Model 分配 → Presenter 消费后 vPortFree
 *   - async UI 数据:  View 分配 → lv_async_call 回调内 vPortFree
 */

#include "app_mvp.h"
#include "FreeRTOS.h"
#include "task.h"
#include "queue.h"
#include "semphr.h"
#include "lvgl.h"
#include <string.h>
#include <stdio.h>

/* net_evt_t 见 app_mvp.h */

#ifndef APP_TEST_MODE_PRESENTER
#define APP_TEST_MODE_PRESENTER  0   /* 1=只跑 presenter 自测，不启 WSS */
#endif

extern QueueHandle_t network_get_evt_queue(void);

#define NET_EVT_QUEUE_LEN  (4)

#if APP_TEST_MODE_PRESENTER
/* 自测专用：只创建 Queue，不启动 WSS 任务 */
static QueueHandle_t s_test_net_queue = NULL;

static QueueHandle_t presenter_test_get_queue(void)
{
    if (s_test_net_queue == NULL) {
        s_test_net_queue = xQueueCreate(NET_EVT_QUEUE_LEN, sizeof(net_evt_t));
        configASSERT(s_test_net_queue != NULL);
    }
    return s_test_net_queue;
}
#endif

/* ── View 接口（runOnUiThread 等价） ───────────────────── */

static lv_obj_t *s_status_label = NULL;

static void ui_async_set_text_cb(void *user_data)
{
    app_mvp_ui_async_t *p = (app_mvp_ui_async_t *)user_data;
    if (p == NULL) {
        return;
    }
    if (s_status_label != NULL) {
        lv_label_set_text(s_status_label, p->text);
    }
    vPortFree(p);
}

/* 任意任务可调 — 等同 Android runOnUiThread(Runnable) */
static void view_post_set_text(const char *text)
{
    if (text == NULL) {
        return;
    }
    app_mvp_ui_async_t *p = pvPortMalloc(sizeof(app_mvp_ui_async_t));
    if (p == NULL) {
        return;
    }
    strncpy(p->text, text, APP_MVP_UI_TEXT_LEN - 1);
    p->text[APP_MVP_UI_TEXT_LEN - 1] = '\0';
    lv_async_call(ui_async_set_text_cb, p);
}

void presenter_view_bind_label(lv_obj_t *label)
{
    s_status_label = label;
}

/* ── handleMessage：Presenter 业务状态机 ───────────────── */

static void presenter_handle_message(const net_evt_t *msg)
{
    if (msg == NULL) {
        return;
    }

    switch (msg->type) {
    case NET_EVT_CONNECTED:
        view_post_set_text("Connected");
        break;

    case NET_EVT_DATA:
        if (msg->payload != NULL && msg->len > 0) {
            /* 业务处理：此处可解析指令、更新状态机，不阻塞 */
            view_post_set_text(msg->payload);
        }
        break;

    case NET_EVT_ERROR:
        view_post_set_text("Network Error");
        break;

    default:
        break;
    }
}

/* ── Looper 线程：等价 Android Looper.loop() ───────────── */

static void presenter_looper_task(void *arg)
{
    (void)arg;
#if APP_TEST_MODE_PRESENTER
    QueueHandle_t inbox = presenter_test_get_queue();
#else
    QueueHandle_t inbox = network_get_evt_queue();
#endif
    configASSERT(inbox != NULL);

    net_evt_t msg;

    for (;;) {
        /* 阻塞等待消息 — 等同 MessageQueue.next() */
        if (xQueueReceive(inbox, &msg, portMAX_DELAY) != pdTRUE) {
            continue;
        }

        presenter_handle_message(&msg);

        /* Presenter 拥有 payload 生命周期 — 等同回收 Message.obj */
        if (msg.payload != NULL) {
            vPortFree(msg.payload);
            msg.payload = NULL;
        }
    }
}

/* ── 测试模式：模拟 Model 发消息，无需真实 WSS ─────────── */

#if APP_TEST_MODE_PRESENTER

static void presenter_self_test_task(void *arg)
{
    (void)arg;
    QueueHandle_t q = presenter_test_get_queue();
    configASSERT(q != NULL);

    vTaskDelay(pdMS_TO_TICKS(500));

    net_evt_t evt = { .type = NET_EVT_CONNECTED, .payload = NULL, .len = 0 };
    xQueueSend(q, &evt, pdMS_TO_TICKS(100));

    vTaskDelay(pdMS_TO_TICKS(500));

    char *text = pvPortMalloc(32);
    if (text != NULL) {
        strcpy(text, "Hello from test mode");
        evt = (net_evt_t){ .type = NET_EVT_DATA, .payload = text, .len = strlen(text) };
        xQueueSend(q, &evt, pdMS_TO_TICKS(100));
    }

    vTaskDelete(NULL);
}

#endif /* APP_TEST_MODE_PRESENTER */

/* ── 公开 API ───────────────────────────────────────────── */

void app_presenter_start(void)
{
    BaseType_t ret = xTaskCreate(
        presenter_looper_task,
        "PresenterLooper",
        512,
        NULL,
        tskIDLE_PRIORITY + 2,
        NULL
    );
    configASSERT(ret == pdPASS);

#if APP_TEST_MODE_PRESENTER
    xTaskCreate(presenter_self_test_task, "PresSelfTest", 384, NULL,
                tskIDLE_PRIORITY + 1, NULL);
#endif
}
