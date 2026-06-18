#!/usr/bin/env python3
"""
端到端 MVP + LVGL 页面生成引擎。

从产品需求 JSON 生成完整 MVP 模块（Presenter + Model + View + UI 页面）。
所有生成代码自动满足 C1-C21 约束。

用法:
    python tools/mvp_page_engine.py product_spec.json -o ./generated
    python tools/mvp_page_engine.py product_spec.json --platform bk -o ./generated
    python tools/mvp_page_engine.py --list-spec
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from checker_io import configure_stdout


# ─── 默认产品规格 ───

DEFAULT_SPEC = {
    "product_name": "SmartSpeaker",
    "platform": "esp32",
    "resolution": {"width": 240, "height": 320},
    "color_depth": 16,
    "lvgl_version": "v8",
    "features": {
        "wifi": True,
        "wss": True,
        "lvgl": True,
        "audio": True,
        "voice_asr": True,
    },
    "io_pins": {
        "led_status": {"pin": "GPIO_NUM_2", "active": 1},
        "btn_wake": {"pin": "GPIO_NUM_0", "active": 0},
        "i2s_sck": {"pin": "GPIO_NUM_12"},
        "i2s_ws": {"pin": "GPIO_NUM_13"},
        "i2s_sd": {"pin": "GPIO_NUM_14"},
        "i2c_scl": {"pin": "GPIO_NUM_22"},
        "i2c_sda": {"pin": "GPIO_NUM_21"},
        "spi_mosi": {"pin": "GPIO_NUM_23"},
        "spi_sck": {"pin": "GPIO_NUM_18"},
        "spi_cs": {"pin": "GPIO_NUM_5"},
        "lcd_dc": {"pin": "GPIO_NUM_17"},
        "lcd_rst": {"pin": "GPIO_NUM_25"},
        "lcd_bl": {"pin": "GPIO_NUM_26"},
    },
    "theme": {
        "primary": 0x2196F3,
        "secondary": 0xFF9800,
        "bg": 0xFFFFFF,
        "text": 0x212121,
        "text_secondary": 0x757575,
    },
    "ui_pages": [
        {
            "page_name": "main",
            "components": [
                {"type": "label", "name": "status", "x": 10, "y": 10, "w": 200, "h": 30, "text": "Ready", "data_binding": "g_status_text"},
                {"type": "label", "name": "time", "x": 10, "y": 50, "w": 200, "h": 40, "text": "00:00", "data_binding": "g_time_text", "font_size": 24},
                {"type": "button", "name": "play", "x": 80, "y": 200, "w": 80, "h": 80, "radius": 40},
                {"type": "bar", "name": "progress", "x": 10, "y": 150, "w": 220, "h": 10, "data_binding": "g_progress"},
                {"type": "slider", "name": "volume", "x": 10, "y": 280, "w": 220, "h": 30, "max": 100, "init": 50, "data_binding": "g_volume"},
            ],
        }
    ],
    "task_priorities": {
        "audio": "MAX-1",
        "wss": "MAX-3",
        "lvgl": "MAX-5",
        "presenter": "MAX-7",
    },
    "queue_config": {
        "net_evt": {"depth": 4, "element": "net_evt_t"},
        "ui_evt": {"depth": 4, "element": "ui_evt_t"},
    },
}


# ─── 代码生成器 ───

def generate_board_io(spec: dict) -> str:
    """生成 board_io.h — 引脚定义（来自 IO 表，非模板）"""
    pins = spec.get("io_pins", {})
    lines = [
        "/**",
        " * @file board_io.h",
        " * @brief 板级 IO 口定义（自动生成，严格按用户 IO 表）",
        " * @warning 修改引脚前必须走 hw_sw_cocodebug workflow 重新核对",
        " */",
        "",
        "#ifndef BOARD_IO_H",
        "#define BOARD_IO_H",
        "",
    ]

    # LED
    if "led_status" in pins:
        led = pins["led_status"]
        lines.append("/* ── LED ─────────────────────────────── */")
        lines.append(f'#define BOARD_LED_STATUS_PIN        {led["pin"]}')
        lines.append(f'#define BOARD_LED_STATUS_ACTIVE     {led.get("active", 1)}')
        lines.append("")

    # Button
    if "btn_wake" in pins:
        btn = pins["btn_wake"]
        lines.append("/* ── 按键 ─────────────────────────────── */")
        lines.append(f'#define BOARD_BTN_WAKE_PIN          {btn["pin"]}')
        lines.append(f'#define BOARD_BTN_WAKE_ACTIVE       {btn.get("active", 0)}')
        lines.append("")

    # I2S
    i2s_pins = {k: v for k, v in pins.items() if k.startswith("i2s_")}
    if i2s_pins:
        lines.append("/* ── I2S 音频 ─────────────────────────── */")
        for name, cfg in i2s_pins.items():
            macro = f"BOARD_{name.upper()}_PIN"
            lines.append(f"#define {macro:<30s} {cfg['pin']}")
        lines.append("")

    # I2C
    i2c_pins = {k: v for k, v in pins.items() if k.startswith("i2c_")}
    if i2c_pins:
        lines.append("/* ── I2C ──────────────────────────────── */")
        for name, cfg in i2c_pins.items():
            macro = f"BOARD_{name.upper()}_PIN"
            lines.append(f"#define {macro:<30s} {cfg['pin']}")
        lines.append("")

    # SPI / LCD
    spi_pins = {k: v for k, v in pins.items() if k.startswith("spi_") or k.startswith("lcd_")}
    if spi_pins:
        lines.append("/* ── SPI / LCD ────────────────────────── */")
        for name, cfg in spi_pins.items():
            macro = f"BOARD_{name.upper()}_PIN"
            lines.append(f"#define {macro:<30s} {cfg['pin']}")
        lines.append("")

    lines.append("#endif /* BOARD_IO_H */")
    return "\n".join(lines)


def generate_ui_theme(spec: dict) -> str:
    """生成 ui_theme.h"""
    theme = spec.get("theme", {})
    return f"""/**
 * @file ui_theme.h
 * @brief UI 颜色主题（自动生成）
 */
#ifndef UI_THEME_H
#define UI_THEME_H

#define UI_COLOR_PRIMARY        0x{theme.get('primary', 0x2196F3):06X}
#define UI_COLOR_SECONDARY      0x{theme.get('secondary', 0xFF9800):06X}
#define UI_COLOR_BG             0x{theme.get('bg', 0xFFFFFF):06X}
#define UI_COLOR_TEXT            0x{theme.get('text', 0x212121):06X}
#define UI_COLOR_TEXT_SECONDARY  0x{theme.get('text_secondary', 0x757575):06X}

#endif /* UI_THEME_H */
"""


def generate_app_mvp_header(spec: dict) -> str:
    """生成 app_mvp.h — 跨层事件类型"""
    queues = spec.get("queue_config", {})
    return f"""/**
 * @file app_mvp.h
 * @brief MVP 跨层事件类型定义（自动生成）
 * @warning 所有任务共用此头文件，修改须走 l3_new_module workflow
 */
#ifndef APP_MVP_H
#define APP_MVP_H

#include <stdint.h>
#include <stdbool.h>

/* ── 网络事件（Model → Presenter）── */
typedef enum {{
    NET_EVT_CONNECTED,
    NET_EVT_DISCONNECTED,
    NET_EVT_DATA,
    NET_EVT_ERROR,
}} net_evt_type_t;

typedef struct {{
    net_evt_type_t type;
    char *payload;      /* heap 分配，Presenter 消费后 vPortFree */
    uint32_t len;
}} net_evt_t;

/* ── UI 事件（Presenter → View）── */
typedef enum {{
    UI_EVT_SET_TEXT,
    UI_EVT_SET_PROGRESS,
    UI_EVT_SET_VOLUME,
}} ui_evt_type_t;

#define APP_MVP_UI_TEXT_LEN  128

typedef struct {{
    ui_evt_type_t type;
    char text[APP_MVP_UI_TEXT_LEN];
    int32_t value;
}} ui_evt_t;

/* ── 测试模式宏（C5）── */
#ifndef APP_TEST_MODE_PRESENTER
#define APP_TEST_MODE_PRESENTER  0
#endif
#ifndef APP_TEST_MODE_WSS
#define APP_TEST_MODE_WSS        0
#endif
#ifndef APP_TEST_MODE_AUDIO
#define APP_TEST_MODE_AUDIO      0
#endif

#endif /* APP_MVP_H */
"""


def generate_presenter(spec: dict) -> str:
    """生成 app_presenter.c — Presenter Looper"""
    product = spec.get("product_name", "Speaker")
    return f"""/**
 * @file app_presenter.c
 * @brief Presenter Looper（自动生成）
 *
 * Android Handler/Looper 对标：
 *   Model → Queue → Presenter.handleMessage → View（lv_async_call）
 *
 * 内存所有权：payload 由 Model 分配，Presenter 消费后 vPortFree（C2.3）
 */
#include "app_mvp.h"
#include "FreeRTOS.h"
#include "task.h"
#include "queue.h"
#include "lvgl.h"
#include <string.h>

/* ── 配置 ────────────────────────────── */
#define NET_EVT_QUEUE_LEN  4
#define UI_EVT_QUEUE_LEN   4

/* ── 队列句柄 ────────────────────────── */
static QueueHandle_t s_net_evt_queue = NULL;

QueueHandle_t network_get_evt_queue(void) {{ return s_net_evt_queue; }}

/* ── View 接口（runOnUiThread 等价）── */
static void ui_async_set_text_cb(void *user_data)
{{
    app_mvp_ui_async_t *p = (app_mvp_ui_async_t *)user_data;
    if (p == NULL) return;
    /* TODO: 调用 ui_page_main_set_status(p->text) */
    vPortFree(p);
}}

/* ── handleMessage（业务状态机）── */
static void presenter_handle_message(const net_evt_t *msg)
{{
    if (msg == NULL) return;
    switch (msg->type) {{
    case NET_EVT_CONNECTED:
        /* TODO: 更新 UI 状态 */
        break;
    case NET_EVT_DATA:
        if (msg->payload != NULL && msg->len > 0) {{
            /* TODO: 解析数据，更新 UI */
        }}
        break;
    case NET_EVT_ERROR:
        /* TODO: 显示错误 */
        break;
    default:
        break;
    }}
}}

/* ── Looper 任务 ─────────────────────── */
static void presenter_looper_task(void *arg)
{{
    (void)arg;
    QueueHandle_t inbox = network_get_evt_queue();
    configASSERT(inbox != NULL);

    net_evt_t msg;
    for (;;) {{
        if (xQueueReceive(inbox, &msg, pdMS_TO_TICKS(100)) != pdTRUE) {{
            continue;  /* C8.3：有限超时，非 portMAX_DELAY */
        }}
        presenter_handle_message(&msg);
        if (msg.payload != NULL) {{
            vPortFree(msg.payload);  /* C2.3：Presenter 释放 payload */
            msg.payload = NULL;
        }}
    }}
}}

/* ── 启动 ─────────────────────────────── */
void app_presenter_start(void)
{{
    s_net_evt_queue = xQueueCreate(NET_EVT_QUEUE_LEN, sizeof(net_evt_t));
    configASSERT(s_net_evt_queue != NULL);

    BaseType_t ret = xTaskCreate(
        presenter_looper_task, "{product}Presenter",
        512, NULL, configMAX_PRIORITIES - 7, NULL  /* C15.1：优先级差 ≥2 */
    );
    configASSERT(ret == pdPASS);  /* C12.1：检查返回值 */
}}
"""


def generate_wss_model(spec: dict) -> str:
    """生成 network_wss_task.c — WSS Model"""
    return f"""/**
 * @file network_wss_task.c
 * @brief WSS Model（自动生成）
 *
 * 内存所有权：cJSON 树在本函数内 Delete，仅传 plain heap buffer 进 Queue（C3.3）
 */
#include "app_mvp.h"
#include "FreeRTOS.h"
#include "task.h"
#include "queue.h"
#include "cJSON.h"
#include <string.h>

/* ── 配置 ────────────────────────────── */
#define WSS_RECONNECT_BASE_MS   1000
#define WSS_RECONNECT_MAX_MS   60000

/* ── cJSON 解析（goto cleanup 模板，C3.2）── */
static int parse_message(const char *json, char *out_text, size_t out_len)
{{
    int ret = -1;
    cJSON *root = NULL;

    if (json == NULL || out_text == NULL) return -1;

    root = cJSON_Parse(json);  /* C3.1 */
    if (root == NULL) goto cleanup;

    cJSON *text = cJSON_GetObjectItemCaseSensitive(root, "text");
    if (cJSON_IsString(text) && text->valuestring != NULL) {{
        strncpy(out_text, text->valuestring, out_len - 1);
        out_text[out_len - 1] = '\\0';
        ret = 0;
    }}

cleanup:
    if (root != NULL) cJSON_Delete(root);  /* C3.1：唯一 Delete 出口 */
    return ret;
}}

/* ── Model：发送事件给 Presenter ─────── */
static bool emit_net_event(QueueHandle_t q, net_evt_type_t type,
                           const char *data, uint32_t len)
{{
    char *heap_copy = NULL;
    if (data != NULL && len > 0) {{
        heap_copy = pvPortMalloc(len + 1);  /* C12.1 */
        if (heap_copy == NULL) return false;
        memcpy(heap_copy, data, len);
        heap_copy[len] = '\\0';
    }}

    net_evt_t evt = {{ .type = type, .payload = heap_copy, .len = len }};
    if (xQueueSend(q, &evt, pdMS_TO_TICKS(50)) != pdTRUE) {{
        vPortFree(heap_copy);  /* C2.4：Queue 满时 Model 释放 */
        return false;
    }}
    return true;
}}

/* ── WSS 任务 ─────────────────────────── */
static void wss_task(void *arg)
{{
    (void)arg;
    QueueHandle_t evt_q = network_get_evt_queue();
    configASSERT(evt_q != NULL);

    /* TODO: WiFi 连接 */
    /* TODO: SNTP 同步（C8.2） */
    /* TODO: TLS 握手（栈 ≥4096 bytes，建议 6144，C7.5） */
    /* TODO: WebSocket 连接 */

    emit_net_event(evt_q, NET_EVT_CONNECTED, NULL, 0);

    for (;;) {{
        /* TODO: 接收 WSS 消息 */
        /* 消息处理示例：*/
        char text_buf[128];
        /* if (parse_message(received_json, text_buf, sizeof(text_buf)) == 0) {{*/
        /*     emit_net_event(evt_q, NET_EVT_DATA, text_buf, strlen(text_buf));*/
        /* }}*/
        vTaskDelay(pdMS_TO_TICKS(100));
    }}
}}

/* ── 启动 ─────────────────────────────── */
void network_wss_start(void)
{{
    BaseType_t ret = xTaskCreate(
        wss_task, "WssTask",
        6144, NULL,  /* C7.5：WSS TLS 握手峰值 */
        configMAX_PRIORITIES - 3,  /* C15.1 */
        NULL
    );
    configASSERT(ret == pdPASS);  /* C12.1 */
}}
"""


def generate_lvgl_page(spec: dict, page_spec: dict) -> str:
    """生成 LVGL 页面代码"""
    page_name = page_spec.get("page_name", "main")
    res = spec.get("resolution", {"width": 240, "height": 320})
    theme = spec.get("theme", {})
    components = page_spec.get("components", [])

    lines = [
        "/**",
        f" * @file ui_page_{page_name}.c",
        f" * @brief LVGL 页面：{page_name}（自动生成）",
        " */",
        "",
        '#include "lvgl.h"',
        '#include "ui_theme.h"',
        "",
        f"#define DISP_HOR_RES  {res['width']}",
        f"#define DISP_VER_RES  {res['height']}",
        "",
        "static lv_obj_t *s_page = NULL;",
        "",
    ]

    # Dynamic handles
    dynamic = [c for c in components if c.get("data_binding")]
    if dynamic:
        lines.append("/* ── 动态组件句柄 ──────────────────── */")
        for c in dynamic:
            var = "s_" + c["name"].lower().replace(" ", "_")
            lines.append(f"static lv_obj_t *{var} = NULL;")
        lines.append("")

    # Event callbacks
    for c in components:
        if c["type"] == "button":
            var = "s_" + c["name"].lower().replace(" ", "_")
            lines.append(f"static void on_{var}_click(lv_event_t *e)")
            lines.append("{")
            lines.append("    (void)e;")
            lines.append(f"    /* TODO: {c['name']} 点击逻辑 */")
            lines.append("}")
            lines.append("")
        elif c["type"] == "slider":
            var = "s_" + c["name"].lower().replace(" ", "_")
            lines.append(f"static void on_{var}_change(lv_event_t *e)")
            lines.append("{")
            lines.append("    lv_obj_t *slider = lv_event_get_target(e);")
            lines.append("    int32_t val = lv_slider_get_value(slider);")
            lines.append(f"    /* TODO: {c['name']} 值变化处理 */")
            lines.append("}")
            lines.append("")

    # Page create
    lines.append(f"lv_obj_t *ui_page_{page_name}_create(lv_obj_t *parent)")
    lines.append("{")
    lines.append("    s_page = lv_obj_create(parent);")
    lines.append(f"    lv_obj_set_size(s_page, DISP_HOR_RES, DISP_VER_RES);")
    lines.append(f"    lv_obj_set_style_bg_color(s_page, lv_color_hex(0x{theme.get('bg', 0xFFFFFF):06X}), 0);")
    lines.append("    lv_obj_set_scrollbar_mode(s_page, LV_SCROLLBAR_MODE_OFF);")
    lines.append("")

    for c in components:
        var = "s_" + c["name"].lower().replace(" ", "_")
        ctype = c["type"]

        if ctype == "label":
            lines.append(f"    /* {c['name']} — label */")
            lines.append(f"    {var} = lv_label_create(s_page);")
            lines.append(f"    lv_obj_set_pos({var}, {c.get('x', 0)}, {c.get('y', 0)});")
            lines.append(f"    lv_obj_set_size({var}, {c.get('w', 100)}, {c.get('h', 30)});")
            lines.append(f"    lv_label_set_text({var}, \"{c.get('text', c['name'])}\");")
            lines.append("")

        elif ctype == "button":
            lines.append(f"    /* {c['name']} — button */")
            lines.append(f"    {var} = lv_btn_create(s_page);")
            lines.append(f"    lv_obj_set_pos({var}, {c.get('x', 0)}, {c.get('y', 0)});")
            lines.append(f"    lv_obj_set_size({var}, {c.get('w', 80)}, {c.get('h', 80)});")
            lines.append(f"    lv_obj_set_style_radius({var}, {c.get('radius', 8)}, 0);")
            lines.append(f"    lv_obj_set_style_bg_color({var}, lv_color_hex(0x{theme.get('primary', 0x2196F3):06X}), 0);")
            lines.append(f"    lv_obj_add_event_cb({var}, on_{var}_click, LV_EVENT_CLICKED, NULL);")
            lines.append("")

        elif ctype == "bar":
            lines.append(f"    /* {c['name']} — bar */")
            lines.append(f"    {var} = lv_bar_create(s_page);")
            lines.append(f"    lv_obj_set_pos({var}, {c.get('x', 0)}, {c.get('y', 0)});")
            lines.append(f"    lv_obj_set_size({var}, {c.get('w', 200)}, {c.get('h', 10)});")
            lines.append(f"    lv_bar_set_range({var}, 0, {c.get('max', 100)});")
            lines.append(f"    lv_bar_set_value({var}, {c.get('init', 0)}, LV_ANIM_OFF);")
            lines.append("")

        elif ctype == "slider":
            lines.append(f"    /* {c['name']} — slider */")
            lines.append(f"    {var} = lv_slider_create(s_page);")
            lines.append(f"    lv_obj_set_pos({var}, {c.get('x', 0)}, {c.get('y', 0)});")
            lines.append(f"    lv_obj_set_size({var}, {c.get('w', 200)}, {c.get('h', 30)});")
            lines.append(f"    lv_slider_set_range({var}, 0, {c.get('max', 100)});")
            lines.append(f"    lv_slider_set_value({var}, {c.get('init', 50)}, LV_ANIM_OFF);")
            lines.append(f"    lv_obj_add_event_cb({var}, on_{var}_change, LV_EVENT_VALUE_CHANGED, NULL);")
            lines.append("")

    lines.append("    return s_page;")
    lines.append("}")

    # External update interfaces for dynamic components
    if dynamic:
        lines.append("")
        lines.append("/* ── 外部更新接口（Presenter 调用）── */")
        for c in dynamic:
            var = "s_" + c["name"].lower().replace(" ", "_")
            fname = c["name"].lower().replace(" ", "_")
            if c["type"] == "label":
                lines.append(f"void ui_page_{page_name}_set_{fname}(const char *text)")
                lines.append("{")
                lines.append(f"    if ({var} != NULL && text != NULL) {{")
                lines.append(f"        lv_label_set_text({var}, text);")
                lines.append("    }")
                lines.append("}")
            elif c["type"] in ("bar", "slider"):
                lines.append(f"void ui_page_{page_name}_set_{fname}(int32_t value)")
                lines.append("{")
                lines.append(f"    if ({var} != NULL) {{")
                setter = "lv_bar_set_value" if c["type"] == "bar" else "lv_slider_set_value"
                lines.append(f"        {setter}({var}, value, LV_ANIM_ON);")
                lines.append("    }")
                lines.append("}")
            lines.append("")

    return "\n".join(lines)


# ─── 主流程 ───

def main() -> int:
    configure_stdout()
    parser = argparse.ArgumentParser(description="端到端 MVP + LVGL 页面生成引擎")
    parser.add_argument("spec", nargs="?", help="产品规格 JSON 文件")
    parser.add_argument("-o", "--output", default="./generated", help="输出目录")
    parser.add_argument("--platform", choices=["esp32", "stm32", "jl", "bk"], help="覆盖平台")
    parser.add_argument("--list-spec", action="store_true", help="输出示例规格 JSON")
    args = parser.parse_args()

    if args.list_spec:
        print(json.dumps(DEFAULT_SPEC, indent=2, ensure_ascii=False))
        return 0

    if not args.spec:
        parser.print_help()
        return 1

    spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    if args.platform:
        spec["platform"] = args.platform

    outdir = Path(args.output)
    outdir.mkdir(parents=True, exist_ok=True)

    product = spec.get("product_name", "Speaker")

    # 1. board_io.h
    (outdir / "board_io.h").write_text(generate_board_io(spec), encoding="utf-8")
    print(f"Generated: board_io.h")

    # 2. ui_theme.h
    (outdir / "ui_theme.h").write_text(generate_ui_theme(spec), encoding="utf-8")
    print(f"Generated: ui_theme.h")

    # 3. app_mvp.h
    (outdir / "app_mvp.h").write_text(generate_app_mvp_header(spec), encoding="utf-8")
    print(f"Generated: app_mvp.h")

    # 4. app_presenter.c
    (outdir / "app_presenter.c").write_text(generate_presenter(spec), encoding="utf-8")
    print(f"Generated: app_presenter.c")

    # 5. network_wss_task.c (if wss enabled)
    if spec.get("features", {}).get("wss"):
        (outdir / "network_wss_task.c").write_text(generate_wss_model(spec), encoding="utf-8")
        print(f"Generated: network_wss_task.c")

    # 6. LVGL pages
    for page_spec in spec.get("ui_pages", []):
        page_name = page_spec.get("page_name", "main")
        code = generate_lvgl_page(spec, page_spec)
        (outdir / f"ui_page_{page_name}.c").write_text(code, encoding="utf-8")
        print(f"Generated: ui_page_{page_name}.c")

    # 7. Summary
    print(f"\n{'='*60}")
    print(f"MVP 代码生成完成: {product}")
    print(f"平台: {spec.get('platform', 'unknown')}")
    print(f"输出目录: {outdir}")
    print(f"文件数: {len(list(outdir.iterdir()))}")
    print(f"\n下一步:")
    print(f"  1. 检查生成代码中的 TODO 注释")
    print(f"  2. 填写业务逻辑（<30% 工作量）")
    print(f"  3. 运行 python tools/run_review.py --dir {outdir} --platform {spec.get('platform', 'freertos')}")
    print(f"  4. 编译验证")

    return 0


if __name__ == "__main__":
    sys.exit(main())
