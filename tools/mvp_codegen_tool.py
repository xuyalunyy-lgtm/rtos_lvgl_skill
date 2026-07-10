#!/usr/bin/env python3
"""
MVP architecture code skeleton generator (aligned with Skill).

- Android Handler/Looper style Presenter
- Unified event bus with payload ownership
- Per-module APP_TEST_MODE_* test macros
- --platform: freertos | esp32 | stm32 | jl | bk

Usage:
    python tools/mvp_codegen_tool.py Network --platform jl -o ./generated
    python tools/mvp_codegen_tool.py Audio --platform bk
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

PLATFORMS = ("freertos", "esp32", "stm32", "jl", "bk")

PLATFORM_CTX = {
    "freertos": {
        "task_include": '#include "FreeRTOS.h"\n#include "task.h"',
        "delay_ms": "vTaskDelay(pdMS_TO_TICKS({ms}))",
        "task_create": """        BaseType_t ret = xTaskCreate(
            {func}, "{name}",
            {stack}, {parm},
            {prio}, {hdl}
        );
        configASSERT(ret == pdPASS);""",
        "malloc": "pvPortMalloc",
        "free": "vPortFree",
        "stack_unit_note": "words (FreeRTOS xTaskCreate)",
        "default_stack": 1024,
        "default_prio": "tskIDLE_PRIORITY + 3",
        "pres_prio": "tskIDLE_PRIORITY + 2",
    },
    "esp32": {
        "task_include": '#include "freertos/FreeRTOS.h"\n#include "freertos/task.h"',
        "delay_ms": "vTaskDelay(pdMS_TO_TICKS({ms}))",
        "task_create": """        BaseType_t ret = xTaskCreate(
            {func}, "{name}",
            {stack}, {parm},
            {prio}, {hdl}
        );
        configASSERT(ret == pdPASS);""",
        "malloc": "heap_caps_malloc(size, MALLOC_CAP_8BIT)",
        "free": "heap_caps_free",
        "stack_unit_note": "words (ESP-IDF xTaskCreate)",
        "default_stack": 4096,
        "default_prio": "(configMAX_PRIORITIES - 3)",
        "pres_prio": "(configMAX_PRIORITIES - 7)",
    },
    "stm32": {
        "task_include": '#include "cmsis_os.h"\n#include "FreeRTOS.h"\n#include "task.h"',
        "delay_ms": "osDelay({ms})",
        "task_create": """        const osThreadAttr_t attr = {{
            .name = "{name}",
            .stack_size = {stack} * 4,
            .priority = (osPriority_t){prio},
        }};
        *{hdl} = osThreadNew({func}, {parm}, &attr);
        configASSERT(*{hdl} != NULL);""",
        "malloc": "pvPortMalloc",
        "free": "vPortFree",
        "stack_unit_note": "words for xTaskCreate; bytes for osThreadNew (stack*4)",
        "default_stack": 1536,
        "default_prio": "osPriorityNormal",
        "pres_prio": "osPriorityBelowNormal",
    },
    "jl": {
        "task_include": '#include "system/os/os_api.h"',
        "delay_ms": "thread_delay_ms({ms})",
        "task_create": """        int pid = 0;
        int ret = thread_fork("{name}", {prio}, {stack}, 0, &pid, {func}, {parm});
        configASSERT(ret == 0);
        (void)pid;""",
        "malloc": "malloc",
        "free": "free",
        "stack_unit_note": "words (JieLi thread_fork)",
        "default_stack": 1024,
        "default_prio": "6",
        "pres_prio": "3",
    },
    "bk": {
        "task_include": '#include "FreeRTOS.h"\n#include "task.h"',
        "delay_ms": "vTaskDelay(pdMS_TO_TICKS({ms}))",
        "task_create": """        BaseType_t ret = xTaskCreate(
            {func}, "{name}",
            {stack}, {parm},
            {prio}, {hdl}
        );
        configASSERT(ret == pdPASS);""",
        "malloc": "pvPortMalloc",
        "free": "vPortFree",
        "stack_unit_note": "bytes (BK7258 xTaskCreate, refer to SDK)",
        "default_stack": 4096,
        "default_prio": "(configMAX_PRIORITIES - 5)",
        "pres_prio": "(configMAX_PRIORITIES - 7)",
    },
}

TEST_CONFIG_TEMPLATE = """/**
 * @file app_test_config.h
 * @brief Test mode macros — when enabled, only runs the corresponding module self-test (see prompts/test_mode_macro.txt)
 *
 * When generating multiple times with mvp_codegen: keep existing #define, only append APP_TEST_MODE_{module_upper}.
 */

#ifndef APP_TEST_CONFIG_H
#define APP_TEST_CONFIG_H

#define APP_TEST_MODE_{module_upper}    0   /* 1=test only {module_name} module */

#endif /* APP_TEST_CONFIG_H */
"""

HEADER_TEMPLATE = """/**
 * @file {module_lower}_mvp.h
 * @brief {module_name} MVP — Android Handler style event bus
 *
 * Shared types see app_mvp.h (net_evt_t / app_mvp_ui_async_t etc.).
 * Model    → xQueueSend (sendMessage)
 * Presenter→ Looper consume (handleMessage)
 * View     → lv_async_call (runOnUiThread)
 *
 * payload: Model allocates → Presenter {free} (see prompts/memory_ownership.txt)
 */

#ifndef {guard}_H
#define {guard}_H

#include "app_mvp.h"
#include "app_test_config.h"
#include "FreeRTOS.h"
#include "queue.h"
#include "semphr.h"
#include "lvgl.h"

#ifdef __cplusplus
extern "C" {{
#endif

typedef enum {{
    {module_upper}_EVT_NONE = 0,
    {module_upper}_EVT_DATA_READY,
    {module_upper}_EVT_ERROR,
    {module_upper}_EVT_STATE_CHANGED,
}} {module_lower}_evt_type_t;

typedef struct {{
    {module_lower}_evt_type_t type;
    void *payload;          /* Model allocates, Presenter frees; do not pass cJSON* */
    size_t payload_len;
}} {module_lower}_evt_t;

void {module_lower}_view_init(lv_obj_t *parent);
void {module_lower}_view_post_text(const char *text);   /* runOnUiThread */

void {module_lower}_presenter_start(void);
void {module_lower}_presenter_handle(const {module_lower}_evt_t *evt);

void {module_lower}_model_start(void);
bool {module_lower}_model_emit({module_lower}_evt_type_t type, void *payload, size_t len);
QueueHandle_t {module_lower}_model_queue(void);

#if APP_TEST_MODE_{module_upper}
void {module_lower}_test_run(void);
#endif

#ifdef __cplusplus
}}
#endif

#endif /* {guard}_H */
"""

MODEL_TEMPLATE = """/**
 * @file {module_lower}_model.c
 * @brief {module_name} Model — background task, no lv_obj_* allowed
 */

#include "{module_lower}_mvp.h"
{task_include}
#include <string.h>

#define {module_upper}_STACK   ({default_stack})
#define {module_upper}_PRIO    ({default_prio})
#define {module_upper}_QLEN    (8)

static QueueHandle_t s_q = NULL;

bool {module_lower}_model_emit({module_lower}_evt_type_t type, void *payload, size_t len)
{{
    if (s_q == NULL) {{
        if (payload != NULL) {{ {free}(payload); }}
        return false;
    }}
    {module_lower}_evt_t evt = {{ .type = type, .payload = payload, .payload_len = len }};
    if (xQueueSend(s_q, &evt, pdMS_TO_TICKS(50)) != pdTRUE) {{
        if (payload != NULL) {{ {free}(payload); }}
        return false;
    }}
    return true;
}}

static void {module_lower}_model_task(void *parm)
{{
    (void)parm;
    for (;;) {{
        /* TODO: hardware/network data collection */
        {delay_10}
    }}
}}

void {module_lower}_model_start(void)
{{
    if (s_q == NULL) {{
        s_q = xQueueCreate({module_upper}_QLEN, sizeof({module_lower}_evt_t));
        configASSERT(s_q != NULL);
    }}
#if !APP_TEST_MODE_{module_upper}
    static TaskHandle_t hdl = NULL;
{task_create_model}
#endif
}}

QueueHandle_t {module_lower}_model_queue(void) {{ return s_q; }}

#if APP_TEST_MODE_{module_upper}
void {module_lower}_test_run(void)
{{
    {module_lower}_model_start();
    /* Self-test: simulate emit, do not start full product */
    char *p = {malloc_stub};
    if (p != NULL) {{
        strcpy(p, "{module_name} test");
        {module_lower}_model_emit({module_upper}_EVT_DATA_READY, p, strlen(p));
    }}
    {module_lower}_presenter_start();
}}
#endif
"""

PRESENTER_TEMPLATE = """/**
 * @file {module_lower}_presenter.c
 * @brief {module_name} Presenter — Looper thread (handleMessage)
 */

#include "{module_lower}_mvp.h"
{task_include}

#define {module_upper}_PRES_STACK ({default_stack} / 2)
#define {module_upper}_PRES_PRIO ({pres_prio})

static void {module_lower}_presenter_looper(void *parm)
{{
    (void)parm;
    QueueHandle_t q = {module_lower}_model_queue();
    configASSERT(q != NULL);
    {module_lower}_evt_t evt;

    for (;;) {{
        if (xQueueReceive(q, &evt, portMAX_DELAY) == pdTRUE) {{
            {module_lower}_presenter_handle(&evt);
            if (evt.payload != NULL) {{
                {free}(evt.payload);
                evt.payload = NULL;
            }}
        }}
    }}
}}

void {module_lower}_presenter_handle(const {module_lower}_evt_t *evt)
{{
    if (evt == NULL) {{ return; }}
    switch (evt->type) {{
    case {module_upper}_EVT_DATA_READY:
        if (evt->payload != NULL) {{
            {module_lower}_view_post_text((const char *)evt->payload);
        }}
        break;
    case {module_upper}_EVT_ERROR:
        {module_lower}_view_post_text("Error");
        break;
    default:
        break;
    }}
}}

void {module_lower}_presenter_start(void)
{{
    {module_lower}_model_start();
    static TaskHandle_t hdl = NULL;
{task_create_pres}
}}
"""

VIEW_TEMPLATE = """/**
 * @file {module_lower}_view.c
 * @brief {module_name} View — lv_async_call refresh (runOnUiThread)
 */

#include "{module_lower}_mvp.h"
#include <string.h>

static lv_obj_t *s_label = NULL;

static void async_cb(void *user_data)
{{
    app_mvp_ui_async_t *m = (app_mvp_ui_async_t *)user_data;
    if (m == NULL) {{ return; }}
    if (s_label != NULL) {{ lv_label_set_text(s_label, m->text); }}
    {free}(m);
}}

void {module_lower}_view_init(lv_obj_t *parent)
{{
    if (parent == NULL) {{ return; }}
    s_label = lv_label_create(parent);
    if (s_label != NULL) {{
        lv_label_set_text(s_label, "{module_name}");
        lv_obj_center(s_label);
    }}
}}

void {module_lower}_view_post_text(const char *text)
{{
    if (text == NULL) {{ return; }}
    app_mvp_ui_async_t *m = {malloc_stub};
    if (m == NULL) {{ return; }}
    strncpy(m->text, text, APP_MVP_UI_TEXT_LEN - 1);
    m->text[APP_MVP_UI_TEXT_LEN - 1] = '\\0';
    lv_async_call(async_cb, m);
}}
"""


def sanitize_module_name(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]", "", name)
    if not cleaned:
        raise ValueError(f"Invalid module name: {name!r}")
    return cleaned


def to_upper_snake(name: str) -> str:
    return re.sub(r"([a-z])([A-Z])", r"\1_\2", name).upper()


def load_app_mvp_h() -> str:
    path = Path(__file__).resolve().parent.parent / "examples" / "app_mvp.h"
    if not path.is_file():
        raise FileNotFoundError(f"Missing examples/app_mvp.h: {path}")
    return path.read_text(encoding="utf-8")


def build_task_create(platform: str, func: str, name: str, stack: int, prio: str,
                      parm: str, hdl: str) -> str:
    tpl = PLATFORM_CTX[platform]["task_create"]
    if platform == "stm32":
        return tpl.format(func=func, name=name, stack=stack, prio=prio, parm=parm, hdl=hdl)
    if platform == "jl":
        return tpl.format(func=func, name=name, stack=stack, prio=prio, parm=parm)
    return tpl.format(func=func, name=name, stack=stack, prio=prio, parm=parm, hdl=hdl)


def generate(module_name: str, platform: str) -> dict[str, str]:
    if platform not in PLATFORM_CTX:
        raise ValueError(f"Unknown platform: {platform}")

    mod = sanitize_module_name(module_name)
    pc = PLATFORM_CTX[platform]
    ml = mod.lower()
    mu = to_upper_snake(mod)

    malloc_stub = f"({pc['malloc'].split('(')[0]})(sizeof(app_mvp_ui_async_t))"
    if platform == "esp32":
        malloc_stub = "(app_mvp_ui_async_t *)heap_caps_malloc(sizeof(app_mvp_ui_async_t), MALLOC_CAP_8BIT)"
        malloc_payload = "(char *)heap_caps_malloc(32, MALLOC_CAP_8BIT)"
    else:
        malloc_payload = f"(char *){pc['malloc'].split('(')[0]}(32)"

    ctx = {
        "module_name": mod,
        "module_lower": ml,
        "module_upper": mu,
        "guard": mu + "_MVP",
        "task_include": pc["task_include"],
        "delay_10": pc["delay_ms"].format(ms=10),
        "free": pc["free"],
        "default_stack": pc["default_stack"],
        "default_prio": pc["default_prio"],
        "pres_prio": pc["pres_prio"],
        "malloc_stub": malloc_stub,
        "task_create_model": build_task_create(
            platform, f"{ml}_model_task", f"{mod}Model",
            pc["default_stack"], pc["default_prio"], "NULL", "&hdl",
        ),
        "task_create_pres": build_task_create(
            platform, f"{ml}_presenter_looper", f"{mod}Looper",
            pc["default_stack"] // 2, pc["pres_prio"], "NULL", "&hdl",
        ),
    }

    model = MODEL_TEMPLATE.format(**ctx)
    model = model.replace("{malloc_stub}", malloc_payload)

    return {
        "app_mvp.h": load_app_mvp_h(),
        "app_test_config.h": TEST_CONFIG_TEMPLATE.format(module_upper=mu, module_name=mod),
        f"{ml}_mvp.h": HEADER_TEMPLATE.format(**ctx),
        f"{ml}_model.c": model,
        f"{ml}_presenter.c": PRESENTER_TEMPLATE.format(**ctx),
        f"{ml}_view.c": VIEW_TEMPLATE.format(**ctx),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="MVP skeleton generator (Skill-aligned)")
    parser.add_argument("module", help="Module name, e.g. Network, Audio")
    parser.add_argument(
        "--platform", "-p",
        choices=PLATFORMS,
        default="freertos",
        help="目标平台 (default: freertos)",
    )
    parser.add_argument("--output-dir", "-o", default=None)
    args = parser.parse_args()

    try:
        files = generate(args.module, args.platform)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    note = PLATFORM_CTX[args.platform]["stack_unit_note"]
    if args.output_dir:
        os.makedirs(args.output_dir, exist_ok=True)
        for fn, content in files.items():
            path = os.path.join(args.output_dir, fn)
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(content)
            print(f"Generated: {path}")
    else:
        for fn, content in files.items():
            print(f"\n{'=' * 60}\n// FILE: {fn}\n{'=' * 60}\n{content}")

    print(f"\n✅ Platform={args.platform}, stack unit: {note}")
    print("   Generated app_mvp.h + module _mvp.h (shared types see examples/app_mvp.h)")
    print("   Pairing example: examples/good_presenter_consumer.c")
    print("   For multiple generations, manually merge APP_TEST_MODE_* macros in app_test_config.h")
    return 0


if __name__ == "__main__":
    sys.exit(main())
