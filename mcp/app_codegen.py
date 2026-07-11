"""App-level C/H code generators for multi-page LVGL MVP.

Generates Router, Presenter, Model Mock, and App scaffolding from
a resolved Manifest v2.  Pure text generation — no I/O side effects.

Usage:
    from mcp.app_codegen import (
        generate_router_c, generate_router_h,
        generate_presenter_c, generate_presenter_h,
        generate_model_c, generate_model_h,
        generate_app_c, generate_app_h,
    )
"""
from __future__ import annotations

import re
from typing import Any


# ── ID helpers (shared with lvgl_codegen) ──────────────────────────

def _safe_id(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9_]", "_", name)
    s = re.sub(r"^(\d)", r"_\1", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s.lower()


def _macro(name: str) -> str:
    return _safe_id(name).upper()


def _page_fn(page_id: str) -> str:
    return f"ui_page_{_safe_id(page_id)}"


# ── Router ─────────────────────────────────────────────────────────


def generate_router_h(app_id: str, pages: list[dict[str, Any]], max_depth: int = 8) -> str:
    """Generate ui_router.h — page stack management interface."""
    guard = f"UI_ROUTER_H"
    ids_enum = ", ".join(f"PAGE_{_macro(p['id'])}" for p in pages)
    page_count = len(pages)

    return f"""\
#ifndef {guard}
#define {guard}

#include "lvgl.h"
#include <stdint.h>

/* ── Error codes ── */
#define UI_ROUTER_OK              0
#define UI_ROUTER_ERR_STACK_FULL  (-1)
#define UI_ROUTER_ERR_UNKNOWN_PAGE (-2)
#define UI_ROUTER_ERR_NO_BACK     (-3)

/* ── Page IDs ── */
typedef enum {{
    {ids_enum},
    PAGE_COUNT
}} ui_page_id_t;

/* ── Page lifecycle ── */
void ui_router_init(lv_obj_t *parent, ui_page_id_t entry);
void ui_router_deinit(void);

/* ── Navigation ── */
int ui_router_push(ui_page_id_t page_id);
int ui_router_back(void);
int ui_router_replace(ui_page_id_t page_id);

/* ── Query ── */
ui_page_id_t ui_router_current(void);
uint8_t ui_router_depth(void);

#endif /* {guard} */
"""


def generate_router_c(app_id: str, pages: list[dict[str, Any]], routes: list[dict[str, Any]], max_depth: int = 8) -> str:
    """Generate ui_router.c — page stack implementation."""
    page_count = len(pages)

    # Build page factory table entries
    factory_entries = []
    for p in pages:
        pid = p["id"]
        fn = _page_fn(pid)
        factory_entries.append(f'    [PAGE_{_macro(pid)}] = {fn}_create,')

    factory_table = "\n".join(factory_entries)

    return f"""\
#include "ui_router.h"
#include <stdio.h>
#include <string.h>

/* ── Page factory forward declarations ── */
{chr(10).join(f'extern lv_obj_t *{_page_fn(p["id"])}_create(lv_obj_t *parent);' for p in pages)}

/* ── Page factory table ── */
typedef lv_obj_t *(*ui_page_create_fn)(lv_obj_t *parent);
static const ui_page_create_fn s_page_factory[PAGE_COUNT] = {{
{factory_table}
}};

/* ── Stack state ── */
#define UI_ROUTER_MAX_DEPTH {max_depth}
static lv_obj_t *s_page_obj[UI_ROUTER_MAX_DEPTH];
static ui_page_id_t s_page_stack[UI_ROUTER_MAX_DEPTH];
static uint8_t s_stack_depth = 0;
static lv_obj_t *s_root = NULL;

/* ── Internal helpers ── */
static void _hide_current(void) {{
    if (s_stack_depth > 0 && s_page_obj[s_stack_depth - 1]) {{
        lv_obj_add_flag(s_page_obj[s_stack_depth - 1], LV_OBJ_FLAG_HIDDEN);
    }}
}}

static void _show_current(void) {{
    if (s_stack_depth > 0 && s_page_obj[s_stack_depth - 1]) {{
        lv_obj_clear_flag(s_page_obj[s_stack_depth - 1], LV_OBJ_FLAG_HIDDEN);
    }}
}}

static void _destroy_current(void) {{
    if (s_stack_depth > 0) {{
        uint8_t idx = s_stack_depth - 1;
        if (s_page_obj[idx]) {{
            lv_obj_del(s_page_obj[idx]);
            s_page_obj[idx] = NULL;
        }}
        s_stack_depth--;
    }}
}}

/* ── Public API ── */

void ui_router_init(lv_obj_t *parent, ui_page_id_t entry) {{
    s_root = parent;
    s_stack_depth = 0;
    memset(s_page_obj, 0, sizeof(s_page_obj));
    memset(s_page_stack, 0, sizeof(s_page_stack));
    ui_router_push(entry);
}}

void ui_router_deinit(void) {{
    while (s_stack_depth > 0) {{
        _destroy_current();
    }}
    s_root = NULL;
}}

int ui_router_push(ui_page_id_t page_id) {{
    if (page_id >= PAGE_COUNT || !s_page_factory[page_id]) {{
        return UI_ROUTER_ERR_UNKNOWN_PAGE;
    }}
    if (s_stack_depth >= UI_ROUTER_MAX_DEPTH) {{
        return UI_ROUTER_ERR_STACK_FULL;
    }}
    _hide_current();
    lv_obj_t *page = s_page_factory[page_id](s_root);
    if (!page) {{
        return UI_ROUTER_ERR_UNKNOWN_PAGE;
    }}
    s_page_obj[s_stack_depth] = page;
    s_page_stack[s_stack_depth] = page_id;
    s_stack_depth++;
    return UI_ROUTER_OK;
}}

int ui_router_back(void) {{
    if (s_stack_depth <= 1) {{
        return UI_ROUTER_ERR_NO_BACK;
    }}
    _destroy_current();
    _show_current();
    return UI_ROUTER_OK;
}}

int ui_router_replace(ui_page_id_t page_id) {{
    if (page_id >= PAGE_COUNT || !s_page_factory[page_id]) {{
        return UI_ROUTER_ERR_UNKNOWN_PAGE;
    }}
    if (s_stack_depth == 0) {{
        return ui_router_push(page_id);
    }}
    _destroy_current();
    lv_obj_t *page = s_page_factory[page_id](s_root);
    if (!page) {{
        return UI_ROUTER_ERR_UNKNOWN_PAGE;
    }}
    s_page_obj[s_stack_depth] = page;
    s_page_stack[s_stack_depth] = page_id;
    s_stack_depth++;
    return UI_ROUTER_OK;
}}

ui_page_id_t ui_router_current(void) {{
    if (s_stack_depth == 0) {{
        return PAGE_COUNT;  /* invalid sentinel */
    }}
    return s_page_stack[s_stack_depth - 1];
}}

uint8_t ui_router_depth(void) {{
    return s_stack_depth;
}}
"""


# ── Presenter ──────────────────────────────────────────────────────


def generate_presenter_h(page_id: str) -> str:
    """Generate presenter_<page>.h — event binding interface."""
    safe = _safe_id(page_id)
    guard = f"PRESENTER_{_macro(page_id)}_H"

    return f"""\
#ifndef {guard}
#define {guard}

#include "lvgl.h"

/* Bind events on page widgets.  Does not own page objects. */
void presenter_{safe}_bind(lv_obj_t *root);

#endif /* {guard} */
"""


def generate_presenter_c(
    page_id: str,
    events: list[dict[str, Any]],
    routes: list[dict[str, Any]],
    models: list[dict[str, Any]],
) -> str:
    """Generate presenter_<page>.c — LVGL event callback wiring."""
    safe = _safe_id(page_id)
    guard = f"PRESENTER_{_macro(page_id)}_C"

    # Build route lookup: route_id → (mode, target_page_macro)
    route_map: dict[str, dict[str, str]] = {}
    for r in routes:
        route_map[r["id"]] = {
            "mode": r.get("mode", "push"),
            "to_macro": f"PAGE_{_macro(r['to'])}" if r.get("to") else "",
        }

    # Build model lookup: model_name → fields
    model_map: dict[str, list[dict[str, Any]]] = {}
    for m in models:
        model_map[m["name"]] = m.get("fields", [])

    # Generate callback bodies
    callbacks: list[str] = []
    bind_lines: list[str] = []

    for event in events:
        node_id = event.get("node_id", "")
        trigger = event.get("trigger", "clicked")
        actions = event.get("actions", [])
        if not node_id or not actions:
            continue

        cb_name = f"_on_{safe}_{_safe_id(node_id)}_{_safe_id(trigger)}"
        cb_body_lines: list[str] = []

        for action in actions:
            atype = action.get("type", "")
            if atype == "route":
                rid = action.get("route_id", "")
                rinfo = route_map.get(rid)
                if rinfo:
                    mode = rinfo["mode"]
                    target = rinfo["to_macro"]
                    if mode == "push":
                        cb_body_lines.append(f"    ui_router_push({target});")
                    elif mode == "replace":
                        cb_body_lines.append(f"    ui_router_replace({target});")
                    elif mode == "back":
                        cb_body_lines.append(f"    ui_router_back();")

            elif atype == "model_set":
                target = action.get("target", "")
                value = action.get("value")
                if "." in target:
                    mname, fname = target.split(".", 1)
                    m_fields = model_map.get(mname, [])
                    field = next((f for f in m_fields if f.get("name") == fname), None)
                    if field:
                        setter = f"model_{_safe_id(mname)}_set_{_safe_id(fname)}"
                        if field["type"] == "bool":
                            cb_body_lines.append(f"    {setter}({'true' if value else 'false'});")
                        elif field["type"] == "int32":
                            cb_body_lines.append(f"    {setter}({int(value)});")
                        elif field["type"] == "string":
                            cb_body_lines.append(f'    {setter}("{value}");')

            elif atype == "model_toggle":
                target = action.get("target", "")
                if "." in target:
                    mname, fname = target.split(".", 1)
                    m_fields = model_map.get(mname, [])
                    field = next((f for f in m_fields if f.get("name") == fname), None)
                    if field and field["type"] == "bool":
                        getter = f"model_{_safe_id(mname)}_get_{_safe_id(fname)}"
                        setter = f"model_{_safe_id(mname)}_set_{_safe_id(fname)}"
                        cb_body_lines.append(f"    {setter}(!{getter}());")

            elif atype == "set_state":
                state = action.get("state", "")
                cb_body_lines.append(f'    /* set_state "{state}" — page-specific state machine */')

        if not cb_body_lines:
            continue

        cb_body = "\n".join(cb_body_lines)
        callbacks.append(f"""\
static void {cb_name}(lv_event_t *e) {{
    (void)e;
{cb_body}
}}
""")

        # Find the widget — search by node_id via lv_obj_get_child_by_name or comment
        bind_lines.append(f'    /* bind {_safe_id(node_id)} → {trigger} */')
        bind_lines.append(f'    {{')
        bind_lines.append(f'        lv_obj_t *btn = lv_obj_get_child_by_name(root, "{_safe_id(node_id)}");')
        bind_lines.append(f'        if (btn) lv_obj_add_event_cb(btn, {cb_name}, LV_EVENT_CLICKED, NULL);')
        bind_lines.append(f'    }}')

    callbacks_code = "\n".join(callbacks) if callbacks else "/* No event actions declared */\n"
    bind_body = "\n".join(bind_lines) if bind_lines else "    (void)root;  /* No bindings */"

    return f"""\
#include "presenter_{safe}.h"
#include "ui_router.h"
{chr(10).join(f'#include "model_{_safe_id(m["name"])}.h"' for m in models)}

/* ── Event callbacks ── */
{callbacks_code}

/* ── Bind all events on page ── */
void presenter_{safe}_bind(lv_obj_t *root) {{
{bind_body}
}}
"""


# ── Model Mock ─────────────────────────────────────────────────────


_C_TYPE_MAP = {
    "bool": "bool",
    "int32": "int32_t",
    "string": "char",
}


def generate_model_h(model_name: str, fields: list[dict[str, Any]]) -> str:
    """Generate model_<name>.h — Mock model interface."""
    safe = _safe_id(model_name)
    guard = f"MODEL_{_macro(model_name)}_H"

    decls: list[str] = []
    for f in fields:
        fname = _safe_id(f["name"])
        ftype = f["type"]
        if ftype == "bool":
            decls.append(f"bool model_{safe}_get_{fname}(void);")
            decls.append(f"void model_{safe}_set_{fname}(bool value);")
        elif ftype == "int32":
            decls.append(f"int32_t model_{safe}_get_{fname}(void);")
            decls.append(f"void model_{safe}_set_{fname}(int32_t value);")
        elif ftype == "string":
            decls.append(f"const char *model_{safe}_get_{fname}(void);")
            decls.append(f"void model_{safe}_set_{fname}(const char *value);")

    functions = "\n".join(decls)

    return f"""\
#ifndef {guard}
#define {guard}

#include <stdbool.h>
#include <stdint.h>

void model_{safe}_init(void);
void model_{safe}_reset(void);

{functions}

#endif /* {guard} */
"""


def generate_model_c(model_name: str, fields: list[dict[str, Any]]) -> str:
    """Generate model_<name>.c — Mock model implementation."""
    safe = _safe_id(model_name)

    # Static storage
    storage_lines: list[str] = []
    init_lines: list[str] = []
    reset_lines: list[str] = []
    func_lines: list[str] = []

    for f in fields:
        fname = _safe_id(f["name"])
        ftype = f["type"]
        default = f.get("default")

        if ftype == "bool":
            var = f"static bool s_{safe}_{fname}"
            storage_lines.append(f"{var} = {'true' if default else 'false'};")
            init_lines.append(f"    s_{safe}_{fname} = {'true' if default else 'false'};")
            reset_lines.append(f"    s_{safe}_{fname} = {'true' if default else 'false'};")
            func_lines.append(f"""
bool model_{safe}_get_{fname}(void) {{
    return s_{safe}_{fname};
}}

void model_{safe}_set_{fname}(bool value) {{
    s_{safe}_{fname} = value;
}}""")

        elif ftype == "int32":
            dv = int(default) if isinstance(default, (int, float)) else 0
            var = f"static int32_t s_{safe}_{fname}"
            storage_lines.append(f"{var} = {dv};")
            init_lines.append(f"    s_{safe}_{fname} = {dv};")
            reset_lines.append(f"    s_{safe}_{fname} = {dv};")
            func_lines.append(f"""
int32_t model_{safe}_get_{fname}(void) {{
    return s_{safe}_{fname};
}}

void model_{safe}_set_{fname}(int32_t value) {{
    s_{safe}_{fname} = value;
}}""")

        elif ftype == "string":
            max_len = f.get("max_length", 64)
            dv = str(default) if isinstance(default, str) else ""
            escaped_default = dv.replace("\\", "\\\\").replace('"', '\\"')
            var = f"static char s_{safe}_{fname}[{max_len + 1}]"
            storage_lines.append(f'{var} = "{escaped_default}";')
            init_lines.append(f'    strncpy(s_{safe}_{fname}, "{escaped_default}", {max_len});')
            reset_lines.append(f'    strncpy(s_{safe}_{fname}, "{escaped_default}", {max_len});')
            func_lines.append(f"""
const char *model_{safe}_get_{fname}(void) {{
    return s_{safe}_{fname};
}}

void model_{safe}_set_{fname}(const char *value) {{
    if (value) {{
        strncpy(s_{safe}_{fname}, value, {max_len});
        s_{safe}_{fname}[{max_len}] = '\\0';
    }}
}}""")

    storage = "\n".join(storage_lines)
    init_body = "\n".join(init_lines) if init_lines else "    /* no fields */"
    reset_body = "\n".join(reset_lines) if reset_lines else "    /* no fields */"
    functions = "\n".join(func_lines)

    return f"""\
#include "model_{safe}.h"
#include <string.h>

/* ── Static storage ── */
{storage}

/* ── Init ── */
void model_{safe}_init(void) {{
{init_body}
}}

/* ── Reset ── */
void model_{safe}_reset(void) {{
{reset_body}
}}
{functions}
"""


# ── App ────────────────────────────────────────────────────────────


def generate_app_h(app_id: str) -> str:
    """Generate ui_app.h — application lifecycle interface."""
    safe = _safe_id(app_id)
    guard = f"UI_APP_H"

    return f"""\
#ifndef {guard}
#define {guard}

#include "lvgl.h"
#include <stdint.h>

/* ── Event types ── */
typedef enum {{
    UI_APP_EVENT_NONE = 0,
    UI_APP_EVENT_NAVIGATE,
    UI_APP_EVENT_MODEL_UPDATE,
    UI_APP_EVENT_STATE_CHANGE,
}} ui_app_event_type_t;

typedef struct {{
    ui_app_event_type_t type;
    union {{
        uint32_t page_id;
        struct {{
            uint32_t model_id;
            uint32_t field_id;
            char value[64];
        }} model;
        struct {{
            char state[32];
        }} state;
    }} data;
}} ui_app_event_t;

/* ── Lifecycle ── */
void ui_app_start(lv_obj_t *parent);
void ui_app_deinit(void);
void ui_app_post_event(const ui_app_event_t *event);

#endif /* {guard} */
"""


def generate_app_c(app_id: str, entry_page: str, models: list[dict[str, Any]]) -> str:
    """Generate ui_app.c — application init/deinit/event dispatch."""
    safe = _safe_id(app_id)
    entry_macro = f"PAGE_{_macro(entry_page)}"

    model_includes = "\n".join(f'#include "model_{_safe_id(m["name"])}.h"' for m in models)
    model_inits = "\n".join(f"    model_{_safe_id(m['name'])}_init();" for m in models)
    model_resets = "\n".join(f"    model_{_safe_id(m['name'])}_reset();" for m in models)

    return f"""\
#include "ui_app.h"
#include "ui_router.h"
{model_includes}
#include <string.h>

/* ── Async event dispatch (FreeRTOS-safe) ── */
static void _dispatch_async(void *arg) {{
    ui_app_event_t *evt = (ui_app_event_t *)arg;
    if (!evt) return;

    switch (evt->type) {{
    case UI_APP_EVENT_NAVIGATE:
        ui_router_push((ui_page_id_t)evt->data.page_id);
        break;
    case UI_APP_EVENT_MODEL_UPDATE:
        /* model update dispatched via presenter callbacks */
        break;
    case UI_APP_EVENT_STATE_CHANGE:
        /* state change dispatched via page set_state */
        break;
    default:
        break;
    }}

    lv_free(evt);
}}

/* ── Lifecycle ── */

void ui_app_start(lv_obj_t *parent) {{
    /* Init models */
{model_inits}

    /* Init router with entry page */
    ui_router_init(parent, {entry_macro});
}}

void ui_app_deinit(void) {{
    ui_router_deinit();

    /* Reset models to defaults */
{model_resets}
}}

void ui_app_post_event(const ui_app_event_t *event) {{
    if (!event) return;

    /* Copy payload — caller memory is not retained */
    ui_app_event_t *copy = lv_malloc(sizeof(ui_app_event_t));
    if (!copy) return;
    memcpy(copy, event, sizeof(ui_app_event_t));

    /* Dispatch on UI thread */
    lv_async_call(_dispatch_async, copy);
}}
"""
