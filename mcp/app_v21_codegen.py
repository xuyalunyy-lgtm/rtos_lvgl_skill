"""Deterministic C generator for verified Manifest v2.1 applications.

The legacy :mod:`app_codegen` module remains the v2.0 scaffold generator.
This module emits the stricter one-active-view Router contract used by v2.1.
"""
from __future__ import annotations

import re
from typing import Any


def _safe(value: str) -> str:
    return re.sub(r"_+", "_", re.sub(r"[^A-Za-z0-9_]", "_", value)).strip("_").lower()


def _macro(value: str) -> str:
    return _safe(value).upper()


def _c_string(value: Any) -> str:
    return str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def generate_router_h(pages: list[dict[str, Any]], max_depth: int) -> str:
    enum = ",\n    ".join(f"UI_PAGE_{_macro(p['id'])}" for p in pages)
    return f'''#ifndef UI_APP_ROUTER_H
#define UI_APP_ROUTER_H

#include "lvgl.h"
#include <stdint.h>

typedef enum {{
    UI_APP_OK = 0,
    UI_APP_ERR_INVALID_ARG = -1,
    UI_APP_ERR_NO_MEMORY = -2,
    UI_APP_ERR_ROUTE_NOT_FOUND = -3,
    UI_APP_ERR_STACK_FULL = -4,
    UI_APP_ERR_NO_BACK = -5,
    UI_APP_ERR_CREATE_FAILED = -6,
}} ui_app_result_t;

typedef enum {{
    {enum},
    UI_PAGE_COUNT
}} ui_page_id_t;

ui_app_result_t ui_router_start(lv_obj_t *parent, ui_page_id_t entry);
void ui_router_deinit(void);
ui_app_result_t ui_router_push(ui_page_id_t page, const char *state);
ui_app_result_t ui_router_replace(ui_page_id_t page, const char *state);
ui_app_result_t ui_router_back(void);
ui_app_result_t ui_router_set_state(const char *state);
void ui_router_refresh(void);
lv_obj_t *ui_router_get_node(const char *node_id);
ui_page_id_t ui_router_current(void);
uint8_t ui_router_depth(void);

#define UI_ROUTER_MAX_DEPTH {max_depth}
#endif
'''


def generate_router_c(pages: list[dict[str, Any]]) -> str:
    decls = []
    create_cases = []
    destroy_cases = []
    state_cases = []
    create_state_cases = []
    refresh_cases = []
    node_cases = []
    presenter_decls = []
    presenter_enter = []
    presenter_exit = []
    for page in pages:
        pid = _safe(page["id"])
        macro = _macro(pid)
        decls.append(f'#include "ui_page_{pid}.h"')
        decls.append(f'#include "presenter_{pid}.h"')
        create_cases.append(f"case UI_PAGE_{macro}: return ui_page_{pid}_create(parent);")
        destroy_cases.append(f"case UI_PAGE_{macro}: ui_page_{pid}_destroy(root); break;")
        state_cases.append(f"case UI_PAGE_{macro}: return ui_page_{pid}_set_state(state) == 0 ? UI_APP_OK : UI_APP_ERR_INVALID_ARG;")
        create_state_cases.append(f"case UI_PAGE_{macro}: state_result = ui_page_{pid}_set_state(state ? state : \"default\"); break;")
        refresh_cases.append(f"case UI_PAGE_{macro}: ui_page_{pid}_refresh(); break;")
        node_cases.append(f"case UI_PAGE_{macro}: return ui_page_{pid}_get_node(node_id);")
        presenter_enter.append(f"case UI_PAGE_{macro}: presenter_{pid}_on_enter(root); break;")
        presenter_exit.append(f"case UI_PAGE_{macro}: presenter_{pid}_on_exit(); break;")
    return f'''#include "ui_router.h"
#include <string.h>
{chr(10).join(decls)}

typedef struct {{ ui_page_id_t page; char state[32]; }} ui_route_frame_t;
static lv_obj_t *s_root;
static lv_obj_t *s_active;
static ui_route_frame_t s_stack[UI_ROUTER_MAX_DEPTH];
static uint8_t s_depth;

static lv_obj_t *create_page(ui_page_id_t page, const char *state) {{
    lv_obj_t *candidate = NULL;
    switch (page) {{ {chr(10).join(create_cases)} default: return NULL; }}
    if (candidate == NULL) return NULL;
    int state_result = 0;
    switch (page) {{ {chr(10).join(create_state_cases)} default: state_result = -1; break; }}
    if (state_result != 0) {{
        switch (page) {{ {chr(10).join(destroy_cases)} default: break; }}
        return NULL;
    }}
    return candidate;
}}

static void destroy_active(void) {{
    if (s_active == NULL || s_depth == 0) return;
    switch (s_stack[s_depth - 1].page) {{ {chr(10).join(presenter_exit)} default: break; }}
    switch (s_stack[s_depth - 1].page) {{ {chr(10).join(destroy_cases)} default: break; }}
    s_active = NULL;
}}

static void enter_active(void) {{
    if (s_active == NULL || s_depth == 0) return;
    switch (s_stack[s_depth - 1].page) {{ {chr(10).join(presenter_enter)} default: break; }}
}}

ui_app_result_t ui_router_start(lv_obj_t *parent, ui_page_id_t entry) {{
    if (parent == NULL) return UI_APP_ERR_INVALID_ARG;
    s_root = parent; s_active = NULL; s_depth = 0;
    return ui_router_push(entry, "default");
}}

void ui_router_deinit(void) {{ destroy_active(); s_depth = 0; s_root = NULL; }}

ui_app_result_t ui_router_push(ui_page_id_t page, const char *state) {{
    if (s_root == NULL || page >= UI_PAGE_COUNT) return UI_APP_ERR_INVALID_ARG;
    if (s_depth >= UI_ROUTER_MAX_DEPTH) return UI_APP_ERR_STACK_FULL;
    lv_obj_t *candidate = create_page(page, state ? state : "default");
    if (candidate == NULL) return UI_APP_ERR_CREATE_FAILED;
    lv_obj_add_flag(candidate, LV_OBJ_FLAG_HIDDEN);
    destroy_active();
    s_stack[s_depth].page = page;
    lv_snprintf(s_stack[s_depth].state, sizeof(s_stack[s_depth].state), "%s", state ? state : "default");
    s_depth++; s_active = candidate;
    lv_obj_clear_flag(s_active, LV_OBJ_FLAG_HIDDEN); enter_active();
    return UI_APP_OK;
}}

ui_app_result_t ui_router_replace(ui_page_id_t page, const char *state) {{
    if (s_depth == 0) return ui_router_push(page, state);
    if (page >= UI_PAGE_COUNT) return UI_APP_ERR_INVALID_ARG;
    lv_obj_t *candidate = create_page(page, state ? state : "default");
    if (candidate == NULL) return UI_APP_ERR_CREATE_FAILED;
    lv_obj_add_flag(candidate, LV_OBJ_FLAG_HIDDEN);
    destroy_active();
    s_stack[s_depth - 1].page = page;
    lv_snprintf(s_stack[s_depth - 1].state, sizeof(s_stack[s_depth - 1].state), "%s", state ? state : "default");
    s_active = candidate; lv_obj_clear_flag(s_active, LV_OBJ_FLAG_HIDDEN); enter_active();
    return UI_APP_OK;
}}

ui_app_result_t ui_router_back(void) {{
    if (s_depth <= 1) return UI_APP_ERR_NO_BACK;
    ui_route_frame_t previous = s_stack[s_depth - 2];
    lv_obj_t *candidate = create_page(previous.page, previous.state);
    if (candidate == NULL) return UI_APP_ERR_CREATE_FAILED;
    lv_obj_add_flag(candidate, LV_OBJ_FLAG_HIDDEN);
    destroy_active(); s_depth--; s_active = candidate;
    lv_obj_clear_flag(s_active, LV_OBJ_FLAG_HIDDEN); enter_active();
    return UI_APP_OK;
}}

ui_app_result_t ui_router_set_state(const char *state) {{
    if (s_active == NULL || s_depth == 0 || state == NULL) return UI_APP_ERR_INVALID_ARG;
    ui_app_result_t result;
    switch (s_stack[s_depth - 1].page) {{ {chr(10).join(state_cases)} default: result = UI_APP_ERR_ROUTE_NOT_FOUND; break; }}
    if (result == UI_APP_OK) lv_snprintf(s_stack[s_depth - 1].state, sizeof(s_stack[s_depth - 1].state), "%s", state);
    return result;
}}

void ui_router_refresh(void) {{ if (s_depth) switch (s_stack[s_depth - 1].page) {{ {chr(10).join(refresh_cases)} default: break; }} }}
lv_obj_t *ui_router_get_node(const char *node_id) {{ if (!s_depth) return NULL; switch (s_stack[s_depth - 1].page) {{ {chr(10).join(node_cases)} default: return NULL; }} }}
ui_page_id_t ui_router_current(void) {{ return s_depth ? s_stack[s_depth - 1].page : UI_PAGE_COUNT; }}
uint8_t ui_router_depth(void) {{ return s_depth; }}
'''


def generate_presenter_h(page_id: str) -> str:
    pid = _safe(page_id)
    return f'''#ifndef PRESENTER_{_macro(pid)}_H
#define PRESENTER_{_macro(pid)}_H
#include "lvgl.h"
void presenter_{pid}_bind(lv_obj_t *root);
void presenter_{pid}_on_enter(lv_obj_t *root);
void presenter_{pid}_on_exit(void);
#endif
'''


def generate_presenter_c(page: dict[str, Any], routes: list[dict[str, Any]], models: list[dict[str, Any]]) -> str:
    pid = _safe(page["id"])
    route_map = {r["id"]: r for r in routes if isinstance(r, dict) and "id" in r}
    model_map = {m["name"]: {f["name"]: f for f in m.get("fields", [])} for m in models if isinstance(m, dict)}
    callbacks, binds = [], []
    event_map = {"clicked": "LV_EVENT_CLICKED", "value_changed": "LV_EVENT_VALUE_CHANGED", "checked": "LV_EVENT_VALUE_CHANGED", "unchecked": "LV_EVENT_VALUE_CHANGED"}
    for event in page.get("events", []):
        node, trigger = _safe(event.get("node_id", "")), event.get("trigger", "clicked")
        if not node or trigger not in event_map: continue
        body = []
        for action in event.get("actions", []):
            kind = action.get("type")
            if kind == "route":
                route = route_map.get(action.get("route_id"), {})
                mode, target = route.get("mode"), route.get("to")
                if mode == "back": body.append("    (void)ui_router_back();")
                elif mode == "replace": body.append(f"    (void)ui_router_replace(UI_PAGE_{_macro(target)}, \"default\");")
                elif mode == "push": body.append(f"    (void)ui_router_push(UI_PAGE_{_macro(target)}, \"default\");")
            elif kind in {"model_set", "model_toggle"}:
                source = action.get("target", "")
                if "." not in source: continue
                model, field = source.split(".", 1); desc = model_map.get(model, {}).get(field, {})
                prefix = f"model_{_safe(model)}"
                if kind == "model_toggle" and desc.get("type") == "bool": body.append(f"    {prefix}_set_{_safe(field)}(!{prefix}_get_{_safe(field)}());")
                elif desc.get("type") == "bool": body.append(f"    {prefix}_set_{_safe(field)}({'true' if action.get('value') else 'false'});")
                elif desc.get("type") == "int32": body.append(f"    {prefix}_set_{_safe(field)}({int(action.get('value', 0))});")
                elif desc.get("type") == "string": body.append(f'    {prefix}_set_{_safe(field)}("{_c_string(action.get("value", ""))}");')
                body.append("    ui_router_refresh();")
            elif kind == "set_state": body.append(f'    (void)ui_router_set_state("{_c_string(action.get("state", "default"))}");')
        if not body: continue
        callback = f"on_{pid}_{node}_{_safe(trigger)}"
        callbacks.append(f"static void {callback}(lv_event_t *e) {{ (void)e;\n{chr(10).join(body)}\n}}")
        binds.append(f"    obj = ui_router_get_node(\"{node}\"); if (obj) lv_obj_add_event_cb(obj, {callback}, {event_map[trigger]}, NULL);")
    includes = "\n".join(f'#include "model_{_safe(m["name"])}.h"' for m in models)
    return f'''#include "presenter_{pid}.h"
#include "ui_router.h"
{includes}
{chr(10).join(callbacks)}
void presenter_{pid}_bind(lv_obj_t *root) {{ lv_obj_t *obj; (void)root; {chr(10).join(binds)} }}
void presenter_{pid}_on_enter(lv_obj_t *root) {{ presenter_{pid}_bind(root); }}
void presenter_{pid}_on_exit(void) {{ }}
'''


def generate_app_h() -> str:
    return '''#ifndef UI_APP_H
#define UI_APP_H
#include "ui_router.h"
ui_app_result_t ui_app_start(lv_obj_t *parent);
void ui_app_deinit(void);
/* Task callers submit typed messages through the platform-owned queue.
 * The UI task calls ui_app_drain_posts() before lv_timer_handler(). */
ui_app_result_t ui_app_post_route(ui_page_id_t page);
void ui_app_drain_posts(void);
#endif
'''


def generate_app_c(entry_page: str, models: list[dict[str, Any]]) -> str:
    inits = "\n".join(f"    model_{_safe(model['name'])}_init();" for model in models)
    resets = "\n".join(f"    model_{_safe(model['name'])}_reset();" for model in models)
    includes = "\n".join(f'#include "model_{_safe(model["name"])}.h"' for model in models)
    return f'''#include "ui_app.h"
{includes}

ui_app_result_t ui_app_start(lv_obj_t *parent) {{
{inits}
    return ui_router_start(parent, UI_PAGE_{_macro(entry_page)});
}}
void ui_app_deinit(void) {{ ui_router_deinit();
{resets}
}}
ui_app_result_t ui_app_post_route(ui_page_id_t page) {{
    /* Platform integration must enqueue this payload; it must not call LVGL
     * from a worker task.  The native harness invokes router APIs on UI time. */
    (void)page; return UI_APP_ERR_INVALID_ARG;
}}
void ui_app_drain_posts(void) {{ /* implemented by ui_app_port on target */ }}
'''
