#!/usr/bin/env python3
"""
MVP 架构代码骨架生成器。

根据业务模块名称，输出 Model 任务、Presenter 消息队列、View 加锁刷新函数模板。

用法:
    python tools/mvp_codegen_tool.py Audio
    python tools/mvp_codegen_tool.py Network --output-dir ./generated
"""

from __future__ import annotations

import argparse
import os
import re
import sys

HEADER_TEMPLATE = """/**
 * @file {module_lower}_mvp.h
 * @brief {module_name} MVP 模块 — 头文件
 *
 * 架构约束:
 *   - View:    仅 LVGL 控件与线程安全刷新
 *   - Presenter: 状态机，经 Queue 收发事件
 *   - Model:   后台任务，禁止直接操作 UI
 */

#ifndef {guard}_H
#define {guard}_H

#include "FreeRTOS.h"
#include "queue.h"
#include "semphr.h"
#include "lvgl.h"

#ifdef __cplusplus
extern "C" {{
#endif

/* ── 事件类型 ─────────────────────────────────────────── */

typedef enum {{
    {module_upper}_EVT_NONE = 0,
    {module_upper}_EVT_DATA_READY,
    {module_upper}_EVT_ERROR,
    {module_upper}_EVT_STATE_CHANGED,
}} {module_lower}_evt_type_t;

typedef struct {{
    {module_lower}_evt_type_t type;
    void *payload;          /* Presenter 负责释放 */
    size_t payload_len;
}} {module_lower}_evt_t;

/* ── View 接口 (仅 UI 任务或加锁调用) ─────────────────── */

void {module_lower}_view_init(lv_obj_t *parent);
void {module_lower}_view_update_label(const char *text);
void {module_lower}_view_set_state(int state);

/* ── Presenter 接口 ───────────────────────────────────── */

void {module_lower}_presenter_init(void);
void {module_lower}_presenter_on_event(const {module_lower}_evt_t *evt);

/* ── Model 接口 ───────────────────────────────────────── */

void {module_lower}_model_task_start(void);
QueueHandle_t {module_lower}_model_get_evt_queue(void);

#ifdef __cplusplus
}}
#endif

#endif /* {guard}_H */
"""

MODEL_TEMPLATE = """/**
 * @file {module_lower}_model.c
 * @brief {module_name} Model 层 — 后台数据采集/网络任务
 */

#include "{module_lower}_mvp.h"
#include <string.h>

#define {module_upper}_MODEL_STACK   (1024)
#define {module_upper}_MODEL_PRIO    (tskIDLE_PRIORITY + 3)
#define {module_upper}_QUEUE_LEN     (8)

static QueueHandle_t s_{module_lower}_evt_queue = NULL;
static TaskHandle_t  s_{module_lower}_task_hdl  = NULL;

static void {module_lower}_model_task(void *arg)
{{
    (void)arg;

    for (;;) {{
        /* TODO: 采集数据 / 网络接收 */

        {module_lower}_evt_t evt = {{
            .type = {module_upper}_EVT_DATA_READY,
            .payload = NULL,
            .payload_len = 0,
        }};

        if (s_{module_lower}_evt_queue != NULL) {{
            if (xQueueSend(s_{module_lower}_evt_queue, &evt, pdMS_TO_TICKS(100)) != pdTRUE) {{
                /* 队列满，丢弃或降采样 */
            }}
        }}
    }}
}}

void {module_lower}_model_task_start(void)
{{
    if (s_{module_lower}_evt_queue == NULL) {{
        s_{module_lower}_evt_queue = xQueueCreate({module_upper}_QUEUE_LEN, sizeof({module_lower}_evt_t));
        configASSERT(s_{module_lower}_evt_queue != NULL);
    }}

    if (s_{module_lower}_task_hdl == NULL) {{
        BaseType_t ret = xTaskCreate(
            {module_lower}_model_task,
            "{module_name}Model",
            {module_upper}_MODEL_STACK,
            NULL,
            {module_upper}_MODEL_PRIO,
            &s_{module_lower}_task_hdl
        );
        configASSERT(ret == pdPASS);
    }}
}}

QueueHandle_t {module_lower}_model_get_evt_queue(void)
{{
    return s_{module_lower}_evt_queue;
}}
"""

PRESENTER_TEMPLATE = """/**
 * @file {module_lower}_presenter.c
 * @brief {module_name} Presenter 层 — 状态机与事件路由
 */

#include "{module_lower}_mvp.h"

#define {module_upper}_PRES_STACK  (512)
#define {module_upper}_PRES_PRIO   (tskIDLE_PRIORITY + 2)

static TaskHandle_t s_{module_lower}_pres_task = NULL;

static void {module_lower}_presenter_task(void *arg)
{{
    QueueHandle_t q = {module_lower}_model_get_evt_queue();
    configASSERT(q != NULL);

    {module_lower}_evt_t evt;

    for (;;) {{
        if (xQueueReceive(q, &evt, portMAX_DELAY) == pdTRUE) {{
            {module_lower}_presenter_on_event(&evt);

            /* Presenter 拥有 payload 生命周期 */
            if (evt.payload != NULL) {{
                vPortFree(evt.payload);
                evt.payload = NULL;
            }}
        }}
    }}
}}

void {module_lower}_presenter_on_event(const {module_lower}_evt_t *evt)
{{
    if (evt == NULL) {{
        return;
    }}

    switch (evt->type) {{
    case {module_upper}_EVT_DATA_READY:
        /* 业务处理完成后，调用 View 刷新（View 内部加锁） */
        {module_lower}_view_set_state(1);
        break;

    case {module_upper}_EVT_ERROR:
        {module_lower}_view_update_label("Error");
        break;

    default:
        break;
    }}
}}

void {module_lower}_presenter_init(void)
{{
    {module_lower}_model_task_start();

    if (s_{module_lower}_pres_task == NULL) {{
        BaseType_t ret = xTaskCreate(
            {module_lower}_presenter_task,
            "{module_name}Pres",
            {module_upper}_PRES_STACK,
            NULL,
            {module_upper}_PRES_PRIO,
            &s_{module_lower}_pres_task
        );
        configASSERT(ret == pdPASS);
    }}
}}
"""

VIEW_TEMPLATE = """/**
 * @file {module_lower}_view.c
 * @brief {module_name} View 层 — LVGL 控件与线程安全刷新
 *
 * ⚠️ 所有 lv_obj_* 调用必须经 lvgl_lock() 保护，或使用 lv_async_call()。
 */

#include "{module_lower}_mvp.h"

extern SemaphoreHandle_t g_lvgl_mutex;  /* 全局 LVGL 互斥锁，在 ui_init.c 创建 */

static lv_obj_t *s_{module_lower}_label = NULL;

/* ── 内部：加锁封装 ───────────────────────────────────── */

static void lvgl_lock(void)
{{
    if (g_lvgl_mutex != NULL) {{
        xSemaphoreTake(g_lvgl_mutex, portMAX_DELAY);
    }}
}}

static void lvgl_unlock(void)
{{
    if (g_lvgl_mutex != NULL) {{
        xSemaphoreGive(g_lvgl_mutex);
    }}
}}

/* ── 异步刷新回调 (lv_async_call 投递) ────────────────── */

typedef struct {{
    char text[64];
}} {module_lower}_async_label_t;

static void async_update_label_cb(void *user_data)
{{
    {module_lower}_async_label_t *data = ({module_lower}_async_label_t *)user_data;
    if (data == NULL || s_{module_lower}_label == NULL) {{
        if (data != NULL) {{
            vPortFree(data);
        }}
        return;
    }}

    lv_label_set_text(s_{module_lower}_label, data->text);
    vPortFree(data);
}}

/* ── 公开 View 接口 ───────────────────────────────────── */

void {module_lower}_view_init(lv_obj_t *parent)
{{
    if (parent == NULL) {{
        return;
    }}

    lvgl_lock();
    s_{module_lower}_label = lv_label_create(parent);
    if (s_{module_lower}_label != NULL) {{
        lv_label_set_text(s_{module_lower}_label, "{module_name}");
        lv_obj_center(s_{module_lower}_label);
    }}
    lvgl_unlock();
}}

void {module_lower}_view_update_label(const char *text)
{{
    if (text == NULL) {{
        return;
    }}

    /* 从任意任务安全调用：异步投递到 UI 线程 */
    {module_lower}_async_label_t *data = pvPortMalloc(sizeof({module_lower}_async_label_t));
    if (data == NULL) {{
        return;
    }}
    strncpy(data->text, text, sizeof(data->text) - 1);
    data->text[sizeof(data->text) - 1] = '\\0';

    lv_async_call(async_update_label_cb, data);
}}

void {module_lower}_view_set_state(int state)
{{
    char buf[32];
    snprintf(buf, sizeof(buf), "{module_name}: state=%d", state);
    {module_lower}_view_update_label(buf);
}}
"""


def sanitize_module_name(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]", "", name)
    if not cleaned:
        raise ValueError(f"无效的模块名: {name!r}")
    return cleaned


def to_upper_snake(name: str) -> str:
    s = re.sub(r"([a-z])([A-Z])", r"\1_\2", name)
    return s.upper()


def generate(module_name: str) -> dict[str, str]:
    mod = sanitize_module_name(module_name)
    ctx = {
        "module_name": mod,
        "module_lower": mod.lower(),
        "module_upper": to_upper_snake(mod),
        "guard": to_upper_snake(mod) + "_MVP",
    }
    return {
        f"{ctx['module_lower']}_mvp.h": HEADER_TEMPLATE.format(**ctx),
        f"{ctx['module_lower']}_model.c": MODEL_TEMPLATE.format(**ctx),
        f"{ctx['module_lower']}_presenter.c": PRESENTER_TEMPLATE.format(**ctx),
        f"{ctx['module_lower']}_view.c": VIEW_TEMPLATE.format(**ctx),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="MVP 架构代码骨架生成器")
    parser.add_argument("module", help="业务模块名，如 Audio, Network")
    parser.add_argument(
        "--output-dir", "-o",
        default=None,
        help="输出目录（默认打印到 stdout）",
    )
    args = parser.parse_args()

    try:
        files = generate(args.module)
    except ValueError as e:
        print(f"错误: {e}", file=sys.stderr)
        return 1

    if args.output_dir:
        os.makedirs(args.output_dir, exist_ok=True)
        for filename, content in files.items():
            path = os.path.join(args.output_dir, filename)
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(content)
            print(f"已生成: {path}")
    else:
        for filename, content in files.items():
            print(f"\n{'=' * 60}")
            print(f"// FILE: {filename}")
            print(f"{'=' * 60}")
            print(content)

    print(f"\n✅ 共生成 {len(files)} 个文件。请根据实际平台调整 STACK/PRIORITY。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
