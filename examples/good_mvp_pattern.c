/**
 * @file good_mvp_pattern.c
 * @brief 范例：按钮点击 → 消息队列 → Presenter 业务处理 → 加锁/async 刷新 UI
 *
 * 文件归属:
 *   - ui_view_manager.c  (View 层)
 *   - app_presenter.c    (Presenter 层)
 *
 * 闭环: 按钮回调不延时、不执行业务，仅发消息；业务在 Presenter；UI 经 lv_async_call 刷新
 * 类型: ui_evt_t / app_mvp_ui_async_t 见 app_mvp.h
 */

#include "app_mvp.h"
#include "FreeRTOS.h"
#include "task.h"
#include "queue.h"
#include "semphr.h"
#include "lvgl.h"
#include <string.h>
#include <stdio.h>

/* ui_evt_t 见 app_mvp.h */

SemaphoreHandle_t g_lvgl_mutex = NULL;

static QueueHandle_t s_ui_evt_queue  = NULL;
static TaskHandle_t  s_presenter_hdl = NULL;

static lv_obj_t *s_status_label = NULL;
static lv_obj_t *s_action_btn   = NULL;

/* ══════════════════════════════════════════════════════════
 *  View 层 — ui_view_manager.c
 * ══════════════════════════════════════════════════════════ */

typedef app_mvp_ui_async_t async_label_payload_t;

static void async_update_status_cb(void *user_data)
{
    async_label_payload_t *p = (async_label_payload_t *)user_data;
    if (p == NULL) {
        return;
    }
    if (s_status_label != NULL) {
        lv_label_set_text(s_status_label, p->text);
    }
    vPortFree(p);
}

/* 线程安全：任何任务均可调用 */
static void view_update_status_async(const char *text)
{
    if (text == NULL) {
        return;
    }

    async_label_payload_t *p = pvPortMalloc(sizeof(async_label_payload_t));
    if (p == NULL) {
        return;
    }
    strncpy(p->text, text, APP_MVP_UI_TEXT_LEN - 1);
    p->text[APP_MVP_UI_TEXT_LEN - 1] = '\0';

    lv_async_call(async_update_status_cb, p);
}

static void view_init(lv_obj_t *parent)
{
    if (parent == NULL) {
        return;
    }

    if (g_lvgl_mutex != NULL) {
        xSemaphoreTake(g_lvgl_mutex, portMAX_DELAY);
    }

    s_status_label = lv_label_create(parent);
    if (s_status_label != NULL) {
        lv_label_set_text(s_status_label, "Ready");
        lv_obj_align(s_status_label, LV_ALIGN_TOP_MID, 0, 20);
    }

    s_action_btn = lv_btn_create(parent);
    if (s_action_btn != NULL) {
        lv_obj_align(s_action_btn, LV_ALIGN_CENTER, 0, 0);
        lv_obj_t *lbl = lv_label_create(s_action_btn);
        if (lbl != NULL) {
            lv_label_set_text(lbl, "Start");
        }
    }

    if (g_lvgl_mutex != NULL) {
        xSemaphoreGive(g_lvgl_mutex);
    }
}

/* ══════════════════════════════════════════════════════════
 *  按钮回调 — 仅发消息，零业务逻辑，零延时
 * ══════════════════════════════════════════════════════════ */

static void on_action_btn_clicked(lv_event_t *e)
{
    if (lv_event_get_code(e) != LV_EVENT_CLICKED) {
        return;
    }

    if (s_ui_evt_queue == NULL) {
        return;
    }

    ui_evt_t evt = {
        .type  = UI_EVT_BTN_CLICKED,
        .param = 0,
    };

    /* 非阻塞发送，避免在 LVGL 回调中卡住 UI */
    xQueueSend(s_ui_evt_queue, &evt, 0);
}

/* ══════════════════════════════════════════════════════════
 *  Presenter 层 — app_presenter.c
 * ══════════════════════════════════════════════════════════ */

static void presenter_handle_event(const ui_evt_t *evt)
{
    if (evt == NULL) {
        return;
    }

    switch (evt->type) {
    case UI_EVT_BTN_CLICKED:
        /* ✅ 业务逻辑在 Presenter，可阻塞、可计算，不影响 UI 回调 */
        view_update_status_async("Processing...");
        vTaskDelay(pdMS_TO_TICKS(100));  /* 模拟耗时业务 */
        view_update_status_async("Done");
        break;

    case UI_EVT_UPDATE_STATUS:
        /* 其他模块也可触发刷新 */
        break;

    default:
        break;
    }
}

static void presenter_task(void *arg)
{
    (void)arg;
    ui_evt_t evt;

    for (;;) {
        if (xQueueReceive(s_ui_evt_queue, &evt, portMAX_DELAY) == pdTRUE) {
            presenter_handle_event(&evt);
        }
    }
}

/* ══════════════════════════════════════════════════════════
 *  初始化入口
 * ══════════════════════════════════════════════════════════ */

void app_mvp_init(lv_obj_t *screen)
{
    g_lvgl_mutex = xSemaphoreCreateMutex();
    configASSERT(g_lvgl_mutex != NULL);

    s_ui_evt_queue = xQueueCreate(8, sizeof(ui_evt_t));
    configASSERT(s_ui_evt_queue != NULL);

    view_init(screen);

    if (s_action_btn != NULL) {
        lv_obj_add_event_cb(s_action_btn, on_action_btn_clicked, LV_EVENT_CLICKED, NULL);
    }

    BaseType_t ret = xTaskCreate(
        presenter_task,
        "Presenter",
        512,
        NULL,
        tskIDLE_PRIORITY + 2,
        &s_presenter_hdl
    );
    configASSERT(ret == pdPASS);
}
