/**
 * @file bad_lvgl_cross_thread.c
 * @brief ❌ 反例：网络任务跨线程直接操作 LVGL — 严禁模仿
 *
 * 文件归属: network_wss_task.c（错误写法示范）
 *
 * 典型后果:
 *   - 随机 HardFault / MemManage Fault
 *   - 界面花屏、Label 文字错乱
 *   - 与 lv_timer_handler 数据竞争导致死锁
 *
 * 正确做法: 见 good_wss_json_parse.c + good_mvp_pattern.c
 *   → xQueueSend 事件给 Presenter → view_update_status_async() / lv_async_call()
 */

#include "FreeRTOS.h"
#include "task.h"
#include "cJSON.h"
#include "lvgl.h"
#include <string.h>

/* ── 全局 UI 对象（在 ui_view_manager.c 中创建） ─────── */

extern lv_obj_t *g_status_label;   /* ❌ 暴露给 Model 层，诱导跨线程操作 */
extern lv_obj_t *g_data_label;

/* ── ❌ 错误 1：WSS 任务直接改 Label ─────────────────── */

static void wss_task(void *arg)
{
    (void)arg;
    char recv_buf[2048];

    for (;;) {
        int n = wss_recv(recv_buf, sizeof(recv_buf) - 1, 5000);
        if (n <= 0) {
            continue;
        }
        recv_buf[n] = '\0';

        /* ❌ 违规：网络任务直接操作 LVGL 控件
         * lv_timer_handler 可能同时在另一个任务中读写同一对象 */
        lv_label_set_text(g_status_label, "Receiving...");

        cJSON *root = cJSON_Parse(recv_buf);
        if (root != NULL) {
            cJSON *text = cJSON_GetObjectItem(root, "text");
            if (cJSON_IsString(text)) {
                /* ❌ 违规：在 WSS 任务中直接更新 UI */
                lv_label_set_text(g_data_label, text->valuestring);
            }
            cJSON_Delete(root);
        }

        /* ❌ 违规：无 Queue，无 Presenter，业务与 UI 耦合 */
        lv_label_set_text(g_status_label, "Done");
    }
}

/* ── ❌ 错误 2：WSS 回调中操作 UI（ESP32 esp_event 上下文同理） ── */

void on_wss_message(const char *json_str)
{
    if (json_str == NULL) {
        return;
    }

    /* ❌ 违规：回调不在 LVGL 任务中 */
    lv_obj_set_style_bg_color(g_status_label, lv_color_hex(0x00FF00), 0);

    cJSON *root = cJSON_Parse(json_str);
    if (root == NULL) {
        /* ❌ 违规：错误处理也直接改 UI */
        lv_label_set_text(g_status_label, "Parse Error");
        return;   /* ❌ 同时遗漏：若 root 非 NULL 的其他分支未统一处理 */
    }
    cJSON_Delete(root);
}

/* ── ❌ 错误 3：Presenter 绕过 View 直接操作 lv_obj_* ── */

void presenter_on_net_event(int evt_type, const char *text)
{
    (void)evt_type;

    /* ❌ 违规：Presenter 应调用 view_xxx() 接口，不直接碰 lv_obj_*
     * 即使 Presenter 优先级低于 LVGL，仍可能与 lv_timer_handler 竞态 */
    if (text != NULL) {
        lv_label_set_text(g_data_label, text);
    }
}

/*
 * ══════════════════════════════════════════════════════════
 *  修复清单（Code Review 时逐条对照）
 * ══════════════════════════════════════════════════════════
 *
 *  [ ] 删除 Model 层所有 lv_obj_* / lv_label_* 调用
 *  [ ] g_status_label 不暴露给 network 模块，仅在 ui_view_manager.c 内 static
 *  [ ] WSS 解析结果通过 Queue 发送 net_evt_t 给 Presenter
 *  [ ] Presenter 调用 view_update_status_async()，内部用 lv_async_call
 *  [ ] 参照 good_wss_json_parse.c 的 net_emit_event() 模式
 */
