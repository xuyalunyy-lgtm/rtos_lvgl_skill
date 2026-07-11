from __future__ import annotations

import difflib
import json
import os
import re
import shlex
import shutil
import subprocess
import tempfile
import textwrap
from pathlib import Path
from typing import Any

try:
    from schemas import (
        ASSET_INPUT_EXTENSIONS,
        COLOR_FORMATS,
        DEFAULT_FONT_CANDIDATES,
        DISPLAY_CONFIG,
        IMAGE_FORMATS,
        INITIAL_LOADING_BACKGROUND_FILE,
        INITIAL_LOADING_DESIGN_FILE,
        INITIAL_LOADING_PET_FILE,
        LVGL_TOOL_SCHEMAS,
        LVGL_VERSIONS,
        REGRESSION_SANDBOX_CONFIG,
    )
except ImportError:  # pragma: no cover - package import fallback
    from .schemas import (
        ASSET_INPUT_EXTENSIONS,
        COLOR_FORMATS,
        DEFAULT_FONT_CANDIDATES,
        DISPLAY_CONFIG,
        IMAGE_FORMATS,
        INITIAL_LOADING_BACKGROUND_FILE,
        INITIAL_LOADING_DESIGN_FILE,
        INITIAL_LOADING_PET_FILE,
        LVGL_TOOL_SCHEMAS,
        LVGL_VERSIONS,
        REGRESSION_SANDBOX_CONFIG,
    )

ROOT = Path(__file__).resolve().parent.parent


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def require_choice(name: str, value: str, allowed: set[str]) -> None:
    if value not in allowed:
        raise ValueError(f"{name} must be one of {sorted(allowed)}, got {value!r}")






def safe_symbol(name: str) -> str:
    symbol = re.sub(r"[^A-Za-z0-9_]", "_", name.strip())
    symbol = re.sub(r"_+", "_", symbol).strip("_")
    if not symbol:
        symbol = "ui_image"
    if symbol[0].isdigit():
        symbol = f"ui_{symbol}"
    return symbol.lower()



def c_string(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("\r", "\\r")
        .replace("\n", "\\n")
        .replace("\t", "\\t")
        .replace('"', '\\"')
    )


def macro_symbol(prefix: str, name: str) -> str:
    return f"{safe_symbol(prefix)}_{safe_symbol(name)}".upper()


def text_macro_for(name: str) -> str:
    return macro_symbol("UI_TEXT", name)


def image_src_macro_for(name: str) -> str:
    return macro_symbol("UI_IMG_SRC", name)


def asset_macro_for(symbol: str) -> str:
    base = safe_symbol(symbol)
    if base.endswith("_map"):
        base = base[:-4]
    if base.startswith("ui_img_"):
        base = base[7:]
    return macro_symbol("UI_IMG", base)


def c_text_expr(value: str) -> str:
    return f'"{c_string(value)}"'


def image_source_expr(value: Any) -> str:
    src = str(value or "").strip()
    if not src:
        return "NULL"
    if src.startswith("&") or src.startswith("(") or src == "NULL":
        return src
    if src.startswith('"') and src.endswith('"'):
        return src
    if re.fullmatch(r"[A-Z][A-Z0-9_]*", src):
        return src
    if re.search(r"[\\/.]", src):
        return c_text_expr(src)
    if re.fullmatch(r"[A-Za-z_]\w*", src):
        return f"&{src}"
    return c_text_expr(src)


def add_macro_define(macros: dict[str, str], name: str, default_expr: str) -> None:
    macros.setdefault(name, default_expr)


def render_macro_defines(macros: dict[str, str]) -> str:
    if not macros:
        return ""
    blocks = []
    for name, default_expr in macros.items():
        blocks.append(f"#ifndef {name}\n#define {name} {default_expr}\n#endif")
    return "\n\n".join(blocks) + "\n"


def ensure_c_macro(lines: list[str], name: str, default_expr: str) -> str:
    define_re = re.compile(rf"\s*#define\s+{re.escape(name)}\b.*")
    for idx, line in enumerate(lines):
        if define_re.fullmatch(line):
            lines[idx] = f"#define {name} {default_expr}"
            return "updated_macro"
    insert_at = 0
    for idx, line in enumerate(lines):
        if line.lstrip().startswith("#include"):
            insert_at = idx + 1
    block = ["", f"#ifndef {name}", f"#define {name} {default_expr}", "#endif"]
    lines[insert_at:insert_at] = block
    return "inserted_macro"


def resolve_path(value: Any, *, base: Path = ROOT, allow_write: bool = False) -> Path:
    """Resolve a path with containment checks to prevent path traversal.

    Args:
        value: The path string to resolve.
        base: Base directory for relative paths (default: project ROOT).
        allow_write: If True, the path must be under WRITE_ROOT (artifacts/).

    Raises:
        ValueError: If the path is None, outside allowed roots, or a symlink
                    pointing outside allowed roots.
    """
    if value is None:
        raise ValueError("path is required")
    path = Path(str(value))
    if not path.is_absolute():
        path = base / path
    resolved = path.resolve()
    # Block symlink traversal: the resolved path must stay under ROOT
    if not resolved.is_relative_to(ROOT):
        raise ValueError(f"Path {resolved} is outside project root — path traversal blocked")
    if allow_write:
        write_root = (ROOT / "artifacts").resolve()
        if not resolved.is_relative_to(write_root):
            raise ValueError(f"Write path {resolved} is outside artifacts/ — only artifacts/ may be written via MCP")
    return resolved



















def generate_lvgl_layout_spec(args: dict[str, Any]) -> dict[str, Any]:
    page_name = safe_symbol(str(args.get("page_name", "page")))
    design_notes = str(args.get("design_notes", "")).strip()
    assets = args.get("assets") or []
    if not isinstance(assets, list):
        raise ValueError("assets must be a list")
    layout = str(args.get("layout", "auto"))
    require_choice("layout", layout, {"auto", "flex", "grid"})
    chosen_layout = "flex" if layout == "auto" else layout
    return {
        "ok": True,
        "spec": {
            "schema": "freertos-embedded-architect.lvgl.layout-spec.v1",
            "page_name": page_name,
            "display_config_uri": str(args.get("display_config_uri", "lvgl://display-config")),
            "layout": {"type": chosen_layout, "absolute_position_exceptions": []},
            "theme": {
                "colors": {
                    "primary": "0x2196F3",
                    "secondary": "0xFF9800",
                    "background": "0xFFFFFF",
                    "text": "0x212121",
                }
            },
            "assets": assets,
            "components": [
                {
                    "id": "content",
                    "type": "container",
                    "layout": chosen_layout,
                    "children": [
                        {"id": "title", "type": "label", "text": "TODO title"},
                        {"id": "primary_action", "type": "button", "text": "OK", "event": "on_primary_action"},
                    ],
                }
            ],
            "design_notes": design_notes,
            "checklist": [
                "Use Flex/Grid before absolute coordinates.",
                "Declare every image in assets before use.",
                "Keep LVGL mutations on UI task or through lv_async_call.",
                "Add LVGL_LAYOUT_EXCEPTION comments for any absolute coordinate call.",
            ],
        },
    }


def load_spec(args: dict[str, Any]) -> dict[str, Any]:
    if "spec_json" in args:
        spec = args["spec_json"]
        if isinstance(spec, str):
            spec = json.loads(spec)
        if not isinstance(spec, dict):
            raise ValueError("spec_json must be an object or JSON object string")
        return spec
    if "spec_path" in args:
        return json.loads(resolve_path(args["spec_path"]).read_text(encoding="utf-8"))
    return generate_lvgl_layout_spec(args)["spec"]


def emit_component(
    component: dict[str, Any],
    parent: str,
    lines: list[str],
    *,
    lvgl_version: str = "v8",
    macro_defs: dict[str, str] | None = None,
) -> None:
    comp_id = safe_symbol(str(component.get("id", component.get("type", "obj"))))
    comp_type = str(component.get("type", "container"))
    var = f"{comp_id}_obj"
    if comp_type == "label":
        text = str(component.get("text", ""))
        text_macro = str(component.get("text_macro") or text_macro_for(comp_id))
        if macro_defs is not None:
            add_macro_define(macro_defs, text_macro, c_text_expr(text))
        lines.append(f"    lv_obj_t *{var} = lv_label_create({parent});")
        lines.append(f"    lv_label_set_text({var}, {text_macro});")
        lines.append(f"    lv_obj_add_style({var}, &s_text_style, 0);")
    elif comp_type == "button":
        lines.append(f"    lv_obj_t *{var} = lv_btn_create({parent});")
        lines.append(f"    lv_obj_add_style({var}, &s_button_style, 0);")
        text = str(component.get("text", ""))
        if text:
            label_var = f"{comp_id}_label"
            text_macro = str(component.get("text_macro") or text_macro_for(f"{comp_id}_label"))
            if macro_defs is not None:
                add_macro_define(macro_defs, text_macro, c_text_expr(text))
            lines.append(f"    lv_obj_t *{label_var} = lv_label_create({var});")
            lines.append(f"    lv_label_set_text({label_var}, {text_macro});")
            lines.append(f"    lv_obj_center({label_var});")
        event = component.get("event")
        if event:
            callback = safe_symbol(str(event))
            lines.append(f"    lv_obj_add_event_cb({var}, {callback}, LV_EVENT_CLICKED, NULL);")
    elif comp_type == "image":
        image_create = "lv_image_create" if lvgl_version == "v9" else "lv_img_create"
        image_set_src = "lv_image_set_src" if lvgl_version == "v9" else "lv_img_set_src"
        lines.append(f"    lv_obj_t *{var} = {image_create}({parent});")
        src = component.get("src", component.get("image", component.get("id", "image")))
        src_macro = str(component.get("src_macro") or component.get("image_macro") or image_src_macro_for(comp_id))
        if macro_defs is not None:
            add_macro_define(macro_defs, src_macro, image_source_expr(src))
        lines.append(f"    {image_set_src}({var}, {src_macro});")
    else:
        lines.append(f"    lv_obj_t *{var} = lv_obj_create({parent});")
        lines.append(f"    lv_obj_set_width({var}, LV_PCT(100));")
        layout = str(component.get("layout", "flex"))
        if layout == "grid":
            lines.append("    /* TODO: tune grid track descriptors for final design. */")
            lines.append(f"    static int32_t {comp_id}_cols[] = {{LV_GRID_FR(1), LV_GRID_TEMPLATE_LAST}};")
            lines.append(f"    static int32_t {comp_id}_rows[] = {{LV_GRID_CONTENT, LV_GRID_TEMPLATE_LAST}};")
            lines.append(f"    lv_obj_set_grid_dsc_array({var}, {comp_id}_cols, {comp_id}_rows);")
            lines.append(f"    lv_obj_set_layout({var}, LV_LAYOUT_GRID);")
        else:
            lines.append(f"    lv_obj_set_flex_flow({var}, LV_FLEX_FLOW_COLUMN);")
            lines.append(f"    lv_obj_set_flex_align({var}, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);")
    for child in component.get("children", []) or []:
        if not isinstance(child, dict):
            raise ValueError("component children must be objects")
        emit_component(child, var, lines, lvgl_version=lvgl_version, macro_defs=macro_defs)


def collect_events(components: list[Any]) -> list[str]:
    events: list[str] = []
    for component in components:
        if not isinstance(component, dict):
            continue
        event = component.get("event")
        if event:
            events.append(safe_symbol(str(event)))
        events.extend(collect_events(component.get("children", []) or []))
    return sorted(set(events))



def c_identifier(name: Any, *, default: str) -> str:
    ident = re.sub(r"[^A-Za-z0-9_]", "_", str(name or "").strip())
    ident = re.sub(r"_+", "_", ident).strip("_")
    if not ident:
        ident = default
    if ident[0].isdigit():
        ident = f"_{ident}"
    return ident


def bool_config(args: dict[str, Any], spec: dict[str, Any], key: str, default: bool) -> bool:
    if key in args:
        return bool(args[key])
    return bool(spec.get(key, default))


def state_names_from_config(args: dict[str, Any], spec: dict[str, Any]) -> list[str]:
    raw = args.get("states", spec.get("states", ["init", "loading", "ready", "error"]))
    if not isinstance(raw, list):
        raise ValueError("states must be an array of strings")
    states: list[str] = []
    seen: set[str] = set()
    for item in raw:
        state = safe_symbol(str(item))
        if state and state not in seen:
            seen.add(state)
            states.append(state)
    if not states:
        raise ValueError("states must contain at least one non-empty state")
    return states



def render_state_typedef(page_name: str, states: list[str]) -> str:
    type_name = f"ui_{page_name}_state_t"
    enum_lines = [
        f"    UI_{page_name.upper()}_STATE_{state.upper()}{' = 0' if idx == 0 else ''},"
        for idx, state in enumerate(states)
    ]
    return "typedef enum {\n" + "\n".join(enum_lines) + f"\n}} {type_name};"


def render_runtime_h_decls(
    page_name: str,
    *,
    event_name: str,
    custom_events_enabled: bool,
    state_machine_enabled: bool,
    states: list[str],
) -> str:
    lines: list[str] = []
    if state_machine_enabled:
        lines.append(render_state_typedef(page_name, states))
        lines.append("")
    if custom_events_enabled:
        lines.append("/* Worker threads should use the post helper; direct UI changes stay on the LVGL task. */")
        lines.append(f"extern uint32_t {event_name};")
    if state_machine_enabled:
        lines.append(f"void ui_{page_name}_set_state(ui_{page_name}_state_t state);")
    if custom_events_enabled:
        lines.append(f"void ui_{page_name}_post_server_update(void *payload);")
    return "\n".join(lines)


def render_runtime_c_support(
    page_name: str,
    *,
    root_var: str,
    lvgl_version: str,
    event_name: str,
    custom_events_enabled: bool,
    state_machine_enabled: bool,
    states: list[str],
) -> str:
    if not custom_events_enabled and not state_machine_enabled:
        return ""

    type_name = f"ui_{page_name}_state_t"
    init_state = f"UI_{page_name.upper()}_STATE_{states[0].upper()}"
    support: list[str] = []

    if custom_events_enabled:
        support.extend(
            [
                f"uint32_t {event_name};",
                "",
                "#ifndef UI_ASYNC_ALLOC",
                "#define UI_ASYNC_ALLOC malloc",
                "#endif",
                "",
                "#ifndef UI_ASYNC_FREE",
                "#define UI_ASYNC_FREE free",
                "#endif",
                "",
                "#ifndef UI_ASYNC_CALL",
                "#define UI_ASYNC_CALL(callback, data) lv_async_call((callback), (data))",
                "#endif",
                "",
                "typedef struct {",
                "    lv_obj_t *target;",
                "    void *payload;",
                f"}} ui_{page_name}_server_update_async_t;",
                "",
            ]
        )

    if state_machine_enabled:
        support.extend([f"static {type_name} s_state = {init_state};", ""])

    if custom_events_enabled:
        support.extend(
            [
                f"static void ui_{page_name}_custom_events_init(void)",
                "{",
                f"    if ({event_name} == 0U) {{",
                f"        {event_name} = lv_event_register_id();",
                "    }",
                "}",
                "",
                f"static void ui_{page_name}_server_update_async_cb(void *user_data)",
                "{",
                f"    ui_{page_name}_server_update_async_t *msg = (ui_{page_name}_server_update_async_t *)user_data;",
                "    if (msg == NULL) {",
                "        return;",
                "    }",
                f"    if (msg->target != NULL && {event_name} != 0U) {{",
                f"        lv_event_send(msg->target, {event_name}, msg->payload);",
                "    }",
                "    UI_ASYNC_FREE(msg);",
                "}",
                "",
                f"static void ui_{page_name}_server_update_cb(lv_event_t *e)",
                "{",
                "    lv_event_code_t code = lv_event_get_code(e);",
                f"    if ((uint32_t)code == {event_name}) {{",
                "        void *server_payload = lv_event_get_param(e);",
                "        (void)server_payload;",
                "        /* TODO: Parse server_payload and update UI components on the LVGL/UI task. */",
                "        return;",
                "    }",
                "    if ((uint32_t)code > (uint32_t)LV_EVENT_LAST) {",
                "        /* TODO: Handle project-specific custom events here. */",
                "    }",
                "}",
                "",
                f"void ui_{page_name}_post_server_update(void *payload)",
                "{",
                f"    ui_{page_name}_server_update_async_t *msg = (ui_{page_name}_server_update_async_t *)UI_ASYNC_ALLOC(sizeof(*msg));",
                "    if (msg == NULL) {",
                "        /* TODO: Report or drop the server update when async payload allocation fails. */",
                "        return;",
                "    }",
                f"    msg->target = {root_var};",
                "    msg->payload = payload;",
                f"    UI_ASYNC_CALL(ui_{page_name}_server_update_async_cb, msg);",
                "}",
                "",
            ]
        )

    if state_machine_enabled:
        first_case = states[0]
        support.extend(
            [
                f"void ui_{page_name}_set_state({type_name} state)",
                "{",
                "    switch (state) {",
            ]
        )
        for state in states:
            support.extend([f"    case UI_{page_name.upper()}_STATE_{state.upper()}:", "        s_state = state;", "        break;"])
        support.extend(
            [
                "    default:",
                f"        s_state = UI_{page_name.upper()}_STATE_{first_case.upper()};",
                "        break;",
                "    }",
                "",
                "    switch (s_state) {",
            ]
        )
        for state in states:
            support.extend(
                [
                    f"    case UI_{page_name.upper()}_STATE_{state.upper()}:",
                    f"        /* TODO: Apply UI visibility/text/style updates for {state} state on the LVGL/UI task. */",
                    "        break;",
                ]
            )
        support.extend(
            [
                "    default:",
                "        break;",
                "    }",
                "}",
                "",
            ]
        )

    return "\n".join(support).rstrip()


def generate_lvgl_page_code(args: dict[str, Any]) -> dict[str, Any]:
    spec = load_spec(args)
    page_name = safe_symbol(str(spec.get("page_name", "page")))
    output_dir = resolve_path(args.get("output_dir", ROOT / "artifacts" / "lvgl_ui"))
    output_dir.mkdir(parents=True, exist_ok=True)
    version = str(args.get("lvgl_version", DISPLAY_CONFIG["lvgl"]["version"]))
    require_choice("lvgl_version", version, LVGL_VERSIONS)
    components = spec.get("components") or []
    if not isinstance(components, list):
        raise ValueError("spec.components must be a list")

    custom_events_enabled = bool_config(args, spec, "custom_events_enabled", True)
    state_machine_enabled = bool_config(args, spec, "state_machine_enabled", True)
    states = state_names_from_config(args, spec)
    default_event_name = f"UI_{page_name.upper()}_EVENT_SERVER_UPDATE"
    raw_event_name = args.get("server_update_event_name", spec.get("server_update_event_name", "auto"))
    event_name = c_identifier(default_event_name if str(raw_event_name).lower() == "auto" else raw_event_name, default=default_event_name)

    create_fn = f"ui_{page_name}_create"
    c_path = output_dir / f"ui_{page_name}.c"
    h_path = output_dir / f"ui_{page_name}.h"
    theme_h = output_dir / "ui_theme.h"
    body_lines: list[str] = []
    macro_defs: dict[str, str] = {}
    for component in components:
        if not isinstance(component, dict):
            raise ValueError("spec.components entries must be objects")
        emit_component(component, "root", body_lines, lvgl_version=version, macro_defs=macro_defs)
    event_stubs = "\n".join(
        f"static void {event}(lv_event_t *e)\n{{\n    (void)e;\n    /* TODO: connect generated UI event to presenter/action layer. */\n}}\n"
        for event in collect_events(components)
    )
    body = "\n".join(body_lines) if body_lines else "    /* TODO: add components from layout spec. */"
    macro_block = render_macro_defines(macro_defs)
    runtime_support = render_runtime_c_support(
        page_name,
        root_var="s_root",
        lvgl_version=version,
        event_name=event_name,
        custom_events_enabled=custom_events_enabled,
        state_machine_enabled=state_machine_enabled,
        states=states,
    )
    runtime_decls = render_runtime_h_decls(
        page_name,
        event_name=event_name,
        custom_events_enabled=custom_events_enabled,
        state_machine_enabled=state_machine_enabled,
        states=states,
    )
    create_runtime_lines: list[str] = ["    s_root = root;"]
    if custom_events_enabled:
        create_runtime_lines.extend(
            [
                f"    ui_{page_name}_custom_events_init();",
                f"    lv_obj_add_event_cb(root, ui_{page_name}_server_update_cb, LV_EVENT_ALL, NULL);",
            ]
        )
    create_runtime = "\n".join(create_runtime_lines)
    state_runtime = f"    ui_{page_name}_set_state(UI_{page_name.upper()}_STATE_{states[0].upper()});" if state_machine_enabled else ""
    c_path.write_text(
        normalize_generated_source(
            f"""\
            #include "ui_{page_name}.h"
            #include "ui_theme.h"

            #include <stdbool.h>
            #include <stdlib.h>

            {macro_block}
            {event_stubs}
            static lv_obj_t *s_root;
            static lv_style_t s_text_style;
            static lv_style_t s_button_style;

            {runtime_support}

            static void init_styles(void)
            {{
                static bool inited = false;
                if (inited) {{
                    return;
                }}
                inited = true;
                lv_style_init(&s_text_style);
                lv_style_set_text_color(&s_text_style, lv_color_hex(UI_COLOR_TEXT));
                lv_style_init(&s_button_style);
                lv_style_set_bg_color(&s_button_style, lv_color_hex(UI_COLOR_PRIMARY));
                lv_style_set_radius(&s_button_style, 8);
            }}

            lv_obj_t *{create_fn}(lv_obj_t *parent)
            {{
                init_styles();
                lv_obj_t *root = lv_obj_create(parent);
                lv_obj_set_size(root, UI_DISPLAY_WIDTH, UI_DISPLAY_HEIGHT);
                lv_obj_set_flex_flow(root, LV_FLEX_FLOW_COLUMN);
                lv_obj_set_flex_align(root, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);
                lv_obj_set_style_bg_color(root, lv_color_hex(UI_COLOR_BACKGROUND), 0);
                lv_obj_set_style_pad_all(root, 16, 0);
                lv_obj_set_style_pad_gap(root, 12, 0);

            {create_runtime}

            {body}

            {state_runtime}

                return root;
            }}
            """
        ),
        encoding="utf-8",
        newline="\n",
    )
    h_guard = f"UI_{page_name.upper()}_H"
    h_path.write_text(
        normalize_generated_source(
            f"""\
            #ifndef {h_guard}
            #define {h_guard}

            #include "lvgl.h"
            #include <stdint.h>

            {runtime_decls}

            lv_obj_t *{create_fn}(lv_obj_t *parent);

            #endif /* {h_guard} */
            """
        ),
        encoding="utf-8",
        newline="\n",
    )
    if not theme_h.exists():
        theme_h.write_text(
            textwrap.dedent(
                """\
                #ifndef UI_THEME_H
                #define UI_THEME_H

                #define UI_DISPLAY_WIDTH 480
                #define UI_DISPLAY_HEIGHT 800
                #define UI_COLOR_PRIMARY 0x2196F3
                #define UI_COLOR_SECONDARY 0xFF9800
                #define UI_COLOR_BACKGROUND 0xFFFFFF
                #define UI_COLOR_TEXT 0x212121

                #endif /* UI_THEME_H */
                """
            ),
            encoding="utf-8",
            newline="\n",
        )
    validation = validate_lvgl_layout_code({"path": str(c_path)})
    return {"ok": validation["ok"], "artifacts": [str(c_path), str(h_path), str(theme_h)], "validation": validation}


def html_attr(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace('"', "&quot;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def normalize_generated_source(text: str) -> str:
    normalized = textwrap.dedent(text)
    lines = normalized.splitlines()
    lines = [line[12:] if line.startswith("            ") else line for line in lines]
    while lines and not lines[0].strip():
        lines.pop(0)
    return "\n".join(lines).rstrip() + "\n"


def relative_asset_path(asset: Path, base: Path) -> str:
    try:
        return asset.resolve().relative_to(base.resolve()).as_posix()
    except ValueError:
        return asset.resolve().as_posix()


def generate_initial_loading_page(args: dict[str, Any]) -> dict[str, Any]:
    design_dir = resolve_path(args.get("design_dir", ROOT / "ui"))
    output_dir = resolve_path(args.get("output_dir", ROOT / "artifacts" / "lvgl_ui" / "initial_loading"))
    output_dir.mkdir(parents=True, exist_ok=True)
    version = str(args.get("lvgl_version", DISPLAY_CONFIG["lvgl"]["version"]))
    require_choice("lvgl_version", version, LVGL_VERSIONS)

    background_path = resolve_path(args.get("background_path", design_dir / INITIAL_LOADING_BACKGROUND_FILE))
    pet_path = resolve_path(args.get("pet_path", design_dir / INITIAL_LOADING_PET_FILE))
    design_path = resolve_path(args.get("design_path", design_dir / INITIAL_LOADING_DESIGN_FILE))
    for item in (background_path, pet_path, design_path):
        if not item.is_file():
            raise ValueError(f"design asset does not exist: {item}")

    page_name = safe_symbol(str(args.get("page_name", "initial_loading")))
    loading_text = str(args.get("loading_text", "???..."))
    width = int(args.get("width", DISPLAY_CONFIG["display"]["width"]))
    height = int(args.get("height", DISPLAY_CONFIG["display"]["height"]))
    pet_x = int(args.get("pet_x", 118))
    pet_y = int(args.get("pet_y", 111))
    pet_w = int(args.get("pet_w", 271))
    pet_h = int(args.get("pet_h", 391))
    dot_y = int(args.get("dot_y", 674))
    dot_radius = int(args.get("dot_radius", 6))
    loading_y = int(args.get("loading_y", 704))
    loading_font = int(args.get("loading_font", 24))
    bg_src = str(args.get("background_src", "S:/ui/background1.jpg"))
    pet_src = str(args.get("pet_src", "S:/ui/pet.png"))
    bg_src_macro = str(args.get("background_src_macro", "UI_IMG_SRC_INITIAL_LOADING_BG"))
    pet_src_macro = str(args.get("pet_src_macro", "UI_IMG_SRC_INITIAL_LOADING_PET"))
    loading_text_macro = str(args.get("loading_text_macro", "UI_TEXT_INITIAL_LOADING"))
    image_create = "lv_image_create" if version == "v9" else "lv_img_create"
    image_set_src = "lv_image_set_src" if version == "v9" else "lv_img_set_src"
    delete_api = "lv_obj_delete" if version == "v9" else "lv_obj_del"
    custom_events_enabled = bool(args.get("custom_events_enabled", True))
    state_machine_enabled = bool(args.get("state_machine_enabled", True))
    states = state_names_from_config(args, {})
    default_event_name = f"UI_{page_name.upper()}_EVENT_SERVER_UPDATE"
    raw_event_name = args.get("server_update_event_name", "auto")
    event_name = c_identifier(default_event_name if str(raw_event_name).lower() == "auto" else raw_event_name, default=default_event_name)

    create_fn = f"ui_{page_name}_create"
    destroy_fn = f"ui_{page_name}_destroy"
    set_text_fn = f"ui_{page_name}_set_loading_text"
    set_active_dot_fn = f"ui_{page_name}_set_active_dot"
    c_path = output_dir / f"ui_{page_name}.c"
    h_path = output_dir / f"ui_{page_name}.h"
    spec_path = output_dir / f"{page_name}_spec.json"
    preview_path = output_dir / "preview.html"
    readme_path = output_dir / "README.md"
    manifest_path = output_dir / "manifest.json"

    spec = {
        "schema": "freertos-embedded-architect.lvgl.initial-loading.v1",
        "page_name": page_name,
        "display": {"width": width, "height": height, "color_depth": DISPLAY_CONFIG["display"]["color_depth"]},
        "lvgl_version": version,
        "custom_events": {"enabled": custom_events_enabled, "server_update_event_name": event_name},
        "state_machine": {"enabled": state_machine_enabled, "states": states},
        "design": str(design_path),
        "assets": [
            {"id": "background", "path": str(background_path), "runtime_src": bg_src, "size": [width, height]},
            {"id": "pet", "path": str(pet_path), "runtime_src": pet_src, "pos": [pet_x, pet_y], "size": [pet_w, pet_h]},
        ],
        "components": [
            {"id": "background", "type": "image", "pos": [0, 0], "size": [width, height]},
            {"id": "pet", "type": "image", "pos": [pet_x, pet_y], "size": [pet_w, pet_h]},
            {"id": "loading_dots", "type": "indicator", "pos": [0, dot_y], "dot_radius": dot_radius},
            {"id": "loading_label", "type": "label", "text": loading_text, "y": loading_y, "font_px": loading_font},
        ],
        "notes": [
            "Pet cutout position was matched from the design screenshot: x=118, y=111.",
            "Runtime image paths require JPEG/PNG decoders and a mounted filesystem prefix.",
            "Absolute positioning is intentional for this pixel-matched splash/loading page.",
        ],
    }
    _write_json(spec_path, spec)

    runtime_support = render_runtime_c_support(
        page_name,
        root_var="s_page",
        lvgl_version=version,
        event_name=event_name,
        custom_events_enabled=custom_events_enabled,
        state_machine_enabled=state_machine_enabled,
        states=states,
    )
    runtime_decls = render_runtime_h_decls(
        page_name,
        event_name=event_name,
        custom_events_enabled=custom_events_enabled,
        state_machine_enabled=state_machine_enabled,
        states=states,
    )
    create_runtime_lines: list[str] = []
    if custom_events_enabled:
        create_runtime_lines.extend(
            [
                f"    ui_{page_name}_custom_events_init();",
                f"    lv_obj_add_event_cb(s_page, ui_{page_name}_server_update_cb, LV_EVENT_ALL, NULL);",
            ]
        )
    create_runtime = "\n".join(create_runtime_lines)
    state_runtime = f"    ui_{page_name}_set_state(UI_{page_name.upper()}_STATE_{states[0].upper()});" if state_machine_enabled else ""
    c_path.write_text(
        normalize_generated_source(
            f"""\
            #include "ui_{page_name}.h"

            #include <stdbool.h>
            #include <stdlib.h>

            #ifndef {bg_src_macro}
            #define {bg_src_macro} {image_source_expr(bg_src)}
            #endif

            #ifndef {pet_src_macro}
            #define {pet_src_macro} {image_source_expr(pet_src)}
            #endif

            #ifndef {loading_text_macro}
            #define {loading_text_macro} {c_text_expr(loading_text)}
            #endif

            #ifndef UI_INITIAL_LOADING_WIDTH
            #define UI_INITIAL_LOADING_WIDTH {width}
            #endif

            #ifndef UI_INITIAL_LOADING_HEIGHT
            #define UI_INITIAL_LOADING_HEIGHT {height}
            #endif

            static lv_obj_t *s_page;
            static lv_obj_t *s_loading_label;
            static lv_obj_t *s_dots[3];
            static lv_style_t s_text_style;
            static lv_style_t s_dot_style;
            static lv_style_t s_dot_active_style;

            {runtime_support}

            static void init_styles(void)
            {{
                static bool inited = false;
                if (inited) {{
                    return;
                }}
                inited = true;

                lv_style_init(&s_text_style);
                lv_style_set_text_color(&s_text_style, lv_color_hex(0xFFFFFF));
                lv_style_set_text_align(&s_text_style, LV_TEXT_ALIGN_CENTER);

                lv_style_init(&s_dot_style);
                lv_style_set_radius(&s_dot_style, LV_RADIUS_CIRCLE);
                lv_style_set_bg_opa(&s_dot_style, LV_OPA_50);
                lv_style_set_bg_color(&s_dot_style, lv_color_hex(0xFFFFFF));

                lv_style_init(&s_dot_active_style);
                lv_style_set_radius(&s_dot_active_style, LV_RADIUS_CIRCLE);
                lv_style_set_bg_opa(&s_dot_active_style, LV_OPA_COVER);
                lv_style_set_bg_color(&s_dot_active_style, lv_color_hex(0xFFFFFF));
            }}

            lv_obj_t *{create_fn}(lv_obj_t *parent)
            {{
                init_styles();

                s_page = lv_obj_create(parent);
                lv_obj_set_size(s_page, UI_INITIAL_LOADING_WIDTH, UI_INITIAL_LOADING_HEIGHT);
                lv_obj_clear_flag(s_page, LV_OBJ_FLAG_SCROLLABLE);
                lv_obj_set_style_border_width(s_page, 0, 0);
                lv_obj_set_style_pad_all(s_page, 0, 0);
                lv_obj_set_style_bg_color(s_page, lv_color_hex(0x79A05F), 0);

            {create_runtime}

                lv_obj_t *bg = {image_create}(s_page);
                {image_set_src}(bg, {bg_src_macro});
                {"lv_image_set_inner_align(bg, LV_IMAGE_ALIGN_STRETCH);" if version == "v9" else ""}
                /* LVGL_LAYOUT_EXCEPTION: full-screen pixel-matched background from design screenshot. */
                lv_obj_set_pos(bg, 0, 0);
                lv_obj_set_size(bg, UI_INITIAL_LOADING_WIDTH, UI_INITIAL_LOADING_HEIGHT);

                lv_obj_t *pet = {image_create}(s_page);
                {image_set_src}(pet, {pet_src_macro});
                {"lv_image_set_inner_align(pet, LV_IMAGE_ALIGN_STRETCH);" if version == "v9" else ""}
                /* LVGL_LAYOUT_EXCEPTION: pet cutout position matched from design screenshot. */
                lv_obj_set_pos(pet, {pet_x}, {pet_y});
                lv_obj_set_size(pet, {pet_w}, {pet_h});

                const int32_t dot_gap = {dot_radius * 4};
                const int32_t dot_size = {dot_radius * 2};
                const int32_t dot_start_x = (UI_INITIAL_LOADING_WIDTH - dot_size * 3 - dot_gap * 2) / 2;
                for (uint8_t i = 0; i < 3; ++i) {{
                    s_dots[i] = lv_obj_create(s_page);
                    lv_obj_remove_style_all(s_dots[i]);
                    lv_obj_set_size(s_dots[i], dot_size, dot_size);
                    /* LVGL_LAYOUT_EXCEPTION: loading indicator is centered at a fixed design y coordinate. */
                    lv_obj_set_pos(s_dots[i], dot_start_x + i * (dot_size + dot_gap), {dot_y});
                    lv_obj_add_style(s_dots[i], i == 0 ? &s_dot_active_style : &s_dot_style, 0);
                }}

                s_loading_label = lv_label_create(s_page);
                lv_label_set_text(s_loading_label, {loading_text_macro});
                lv_obj_add_style(s_loading_label, &s_text_style, 0);
                lv_obj_set_width(s_loading_label, UI_INITIAL_LOADING_WIDTH);
                /* LVGL_LAYOUT_EXCEPTION: loading label is centered at a fixed design y coordinate. */
                lv_obj_set_pos(s_loading_label, 0, {loading_y});

            {state_runtime}

                return s_page;
            }}

            void {destroy_fn}(void)
            {{
                if (s_page != NULL) {{
                    {delete_api}(s_page);
                    s_page = NULL;
                    s_loading_label = NULL;
                    for (uint8_t i = 0; i < 3; ++i) {{
                        s_dots[i] = NULL;
                    }}
                }}
            }}

            void {set_text_fn}(const char *text)
            {{
                if (s_loading_label != NULL && text != NULL) {{
                    lv_label_set_text(s_loading_label, text);
                }}
            }}

            void {set_active_dot_fn}(uint8_t active_index)
            {{
                for (uint8_t i = 0; i < 3; ++i) {{
                    if (s_dots[i] == NULL) {{
                        continue;
                    }}
                    lv_obj_remove_style(s_dots[i], &s_dot_style, 0);
                    lv_obj_remove_style(s_dots[i], &s_dot_active_style, 0);
                    lv_obj_add_style(s_dots[i], i == active_index ? &s_dot_active_style : &s_dot_style, 0);
                }}
            }}
            """
        ),
        encoding="utf-8",
        newline="\n",
    )

    h_guard = f"UI_{page_name.upper()}_H"
    h_path.write_text(
        normalize_generated_source(
            f"""\
            #ifndef {h_guard}
            #define {h_guard}

            #include "lvgl.h"
            #include <stdint.h>

            {runtime_decls}

            lv_obj_t *{create_fn}(lv_obj_t *parent);
            void {destroy_fn}(void);
            void {set_text_fn}(const char *text);
            void {set_active_dot_fn}(uint8_t active_index);

            #endif /* {h_guard} */
            """
        ),
        encoding="utf-8",
        newline="\n",
    )

    bg_rel = relative_asset_path(background_path, output_dir)
    pet_rel = relative_asset_path(pet_path, output_dir)
    design_rel = relative_asset_path(design_path, output_dir)
    preview_path.write_text(
        textwrap.dedent(
            f"""\
            <!doctype html>
            <html lang="zh-CN">
            <head>
              <meta charset="utf-8">
              <meta name="viewport" content="width=device-width, initial-scale=1">
              <title>Initial Loading Preview</title>
              <style>
                body {{ margin: 0; min-height: 100vh; display: grid; place-items: center; background: #1d2419; }}
                .screen {{ position: relative; width: {width}px; height: {height}px; overflow: hidden; background: #79a05f; }}
                .screen img {{ position: absolute; display: block; user-select: none; pointer-events: none; }}
                .bg {{ inset: 0; width: 100%; height: 100%; object-fit: cover; }}
                .pet {{ left: {pet_x}px; top: {pet_y}px; width: {pet_w}px; height: {pet_h}px; }}
                .dots {{ position: absolute; left: 0; top: {dot_y}px; width: 100%; display: flex; justify-content: center; gap: {dot_radius * 2}px; }}
                .dots span {{ width: {dot_radius * 2}px; height: {dot_radius * 2}px; border-radius: 999px; background: rgba(255,255,255,.5); }}
                .dots span:first-child {{ background: #fff; }}
                .label {{ position: absolute; left: 0; top: {loading_y}px; width: 100%; text-align: center; color: #fff; font: 600 {loading_font}px/1.2 system-ui, "Microsoft YaHei", sans-serif; }}
              </style>
            </head>
            <body>
              <div class="screen" data-design="{html_attr(design_rel)}">
                <img class="bg" src="{html_attr(bg_rel)}" alt="">
                <img class="pet" src="{html_attr(pet_rel)}" alt="">
                <div class="dots"><span></span><span></span><span></span></div>
                <div class="label">{html_attr(loading_text)}</div>
              </div>
            </body>
            </html>
            """
        ),
        encoding="utf-8",
        newline="\n",
    )

    readme_path.write_text(
        textwrap.dedent(
            f"""\
            # Initial Loading LVGL Page

            Generated from `ui/initial_loading.png` using the two cut assets:

            - Background: `{background_path}`
            - Pet: `{pet_path}`

            Key layout:

            - Screen: {width}x{height}
            - Pet: x={pet_x}, y={pet_y}, w={pet_w}, h={pet_h}
            - Loading dots y={dot_y}
            - Loading label y={loading_y}

            Runtime requirements:

            - JPEG decoder for `{bg_src}`.
            - PNG decoder for `{pet_src}`.
            - Override `UI_IMG_SRC_INITIAL_LOADING_BG`, `UI_IMG_SRC_INITIAL_LOADING_PET`, and `UI_TEXT_INITIAL_LOADING` when integrating final resources.
            - Network/MQTT threads should call `ui_{page_name}_post_server_update(payload)` instead of touching LVGL objects directly.
            - Payload ownership/lifetime stays with the project; copy server data before posting if the source buffer is transient.
            """
        ),
        encoding="utf-8",
        newline="\n",
    )

    validation = validate_lvgl_layout_code({"path": str(output_dir)})
    artifacts = [str(c_path), str(h_path), str(spec_path), str(preview_path), str(readme_path), str(manifest_path)]
    manifest = {"ok": validation["ok"], "page_name": page_name, "artifacts": artifacts[:-1], "validation": validation}
    _write_json(manifest_path, manifest)
    return {**manifest, "artifacts": artifacts}

def load_json_like(args: dict[str, Any], key: str, path_key: str = "") -> Any:
    if key in args and args[key] is not None:
        value = args[key]
        if isinstance(value, str):
            return json.loads(value)
        return value
    if path_key and args.get(path_key):
        return json.loads(resolve_path(args[path_key]).read_text(encoding="utf-8"))
    raise ValueError(f"{key} or {path_key} is required")


def walk_text_values(value: Any) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"text", "label", "title", "placeholder", "content"} and isinstance(item, str):
                found.append(item)
            else:
                found.extend(walk_text_values(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(walk_text_values(item))
    return found


def flatten_layout_nodes(value: Any) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []

    def visit(item: Any) -> None:
        if isinstance(item, list):
            for child in item:
                visit(child)
            return
        if not isinstance(item, dict):
            return
        has_visual_fields = any(key in item for key in ("id", "name", "type", "x", "y", "w", "h", "width", "height", "bbox", "bounds"))
        node_type = str(item.get("type", "")).lower()
        if has_visual_fields and node_type not in {"screen", "root", "page"}:
            nodes.append(item)
        for key in ("children", "items", "nodes", "layers"):
            if key in item:
                visit(item[key])
        if "tree" in item:
            visit(item["tree"])

    visit(value)
    return nodes


def node_identifier(node: dict[str, Any], index: int) -> str:
    for key in ("id", "name", "var", "key"):
        value = str(node.get(key, "")).strip()
        if value:
            return safe_symbol(value)
    node_type = safe_symbol(str(node.get("type", "obj")))
    return f"{node_type}_{index + 1}"



def node_text_macro(node: dict[str, Any], index: int) -> str:
    return str(node.get("text_macro") or text_macro_for(node_identifier(node, index)))


def node_image_src_macro(node: dict[str, Any], index: int) -> str:
    return str(node.get("src_macro") or node.get("image_macro") or image_src_macro_for(node_identifier(node, index)))


def node_type_of(node: dict[str, Any]) -> str:
    raw = str(node.get("type", "obj")).strip().lower()
    aliases = {
        "text": "label",
        "textbox": "label",
        "img": "image",
        "picture": "image",
        "container": "obj",
        "rect": "obj",
    }
    return aliases.get(raw, raw or "obj")


def node_box(node: dict[str, Any]) -> tuple[int | None, int | None, int | None, int | None]:
    x = node.get("x")
    y = node.get("y")
    w = node.get("w", node.get("width"))
    h = node.get("h", node.get("height"))
    bounds = node.get("bounds") or node.get("bbox")
    if isinstance(bounds, dict):
        x = bounds.get("x", x)
        y = bounds.get("y", y)
        w = bounds.get("w", bounds.get("width", w))
        h = bounds.get("h", bounds.get("height", h))
    elif isinstance(bounds, list) and len(bounds) >= 4:
        x, y, w, h = bounds[:4]
    def as_int(value: Any) -> int | None:
        if value is None or value == "":
            return None
        return int(round(float(value)))
    return as_int(x), as_int(y), as_int(w), as_int(h)



def parse_lvgl_objects(lines: list[str]) -> dict[str, dict[str, Any]]:
    create_re = re.compile(r"lv_obj_t\s*\*\s*(\w+)\s*=\s*(lv_\w+_create|lv_obj_create)\s*\(([^)]*)\)")
    pos_re = re.compile(r"lv_obj_set_pos\s*\(\s*(\w+)\s*,\s*([^,]+),\s*([^)]+)\)")
    size_re = re.compile(r"lv_obj_set_size\s*\(\s*(\w+)\s*,\s*([^,]+),\s*([^)]+)\)")
    text_re = re.compile(r"lv_label_set_text\s*\(\s*(\w+)\s*,\s*\"(.*)\"\s*\)")
    src_re = re.compile(r"lv_(?:img|image)_set_src\s*\(\s*(\w+)\s*,\s*([^)]*)\)")
    objects: dict[str, dict[str, Any]] = {}
    for idx, line in enumerate(lines):
        if match := create_re.search(line):
            var, api, parent = match.groups()
            objects[var] = {"var": var, "create_api": api, "parent": parent.strip(), "line": idx}
        if match := pos_re.search(line):
            var, x, y = match.groups()
            objects.setdefault(var, {"var": var})["pos"] = (x.strip(), y.strip(), idx)
        if match := size_re.search(line):
            var, w, h = match.groups()
            objects.setdefault(var, {"var": var})["size"] = (w.strip(), h.strip(), idx)
        if match := text_re.search(line):
            var, text = match.groups()
            objects.setdefault(var, {"var": var})["text"] = (text, idx)
        if match := src_re.search(line):
            var, src = match.groups()
            objects.setdefault(var, {"var": var})["src"] = (src.strip(), idx)
    return objects


def find_layout_var(node: dict[str, Any], index: int, objects: dict[str, dict[str, Any]]) -> str | None:
    candidates = []
    explicit = str(node.get("var", "")).strip()
    if explicit:
        candidates.append(explicit)
    ident = node_identifier(node, index)
    candidates.extend([f"{ident}_obj", ident, f"s_{ident}", f"{ident}_label"])
    for candidate in candidates:
        if candidate in objects:
            return candidate
    desired_text = str(node.get("text", node.get("label", ""))).strip()
    if desired_text:
        for var, info in objects.items():
            if info.get("text", (None,))[0] == desired_text:
                return var
    desired_src = str(node.get("src", node.get("image", ""))).strip()
    if desired_src:
        for var, info in objects.items():
            if desired_src in str(info.get("src", ("",))[0]):
                return var
    return None


def ensure_layout_exception(lines: list[str], idx: int, reason: str) -> None:
    marker = DISPLAY_CONFIG["layout_policy"]["exception_marker"]
    window = "\n".join(lines[max(0, idx - 3):idx + 1])
    if marker not in window:
        lines.insert(idx, f"    /* {marker}: {reason}. */")


def replace_or_insert_lvgl_call(lines: list[str], objects: dict[str, dict[str, Any]], var: str, key: str, new_line: str, *, exception_reason: str = "") -> str:
    info = objects.setdefault(var, {"var": var})
    existing = info.get(key)
    if existing:
        idx = int(existing[-1])
        lines[idx] = new_line
        if key == "pos":
            ensure_layout_exception(lines, idx, exception_reason)
        return "updated"
    insert_at = int(info.get("line", len(lines) - 1)) + 1
    if key == "pos":
        lines.insert(insert_at, f"    /* {DISPLAY_CONFIG['layout_policy']['exception_marker']}: {exception_reason}. */")
        insert_at += 1
    lines.insert(insert_at, new_line)
    return "inserted"


def generate_lvgl_node_block(node: dict[str, Any], index: int, *, parent: str, lvgl_version: str, reason: str) -> list[str]:
    ident = node_identifier(node, index)
    var = str(node.get("var") or f"{ident}_obj")
    comp_type = node_type_of(node)
    x, y, w, h = node_box(node)
    image_create = "lv_image_create" if lvgl_version == "v9" else "lv_img_create"
    image_set_src = "lv_image_set_src" if lvgl_version == "v9" else "lv_img_set_src"
    if comp_type == "label":
        create = f"lv_label_create({parent})"
    elif comp_type == "button":
        create = f"lv_btn_create({parent})"
    elif comp_type == "image":
        create = f"{image_create}({parent})"
    elif comp_type == "bar":
        create = f"lv_bar_create({parent})"
    elif comp_type == "slider":
        create = f"lv_slider_create({parent})"
    else:
        create = f"lv_obj_create({parent})"
    block = [f"    /* generated from visual node: {ident} */", f"    lv_obj_t *{var} = {create};"]
    text = str(node.get("text", node.get("label", "")))
    if comp_type == "label" and text:
        block.append(f"    lv_label_set_text({var}, {node_text_macro(node, index)});")
    elif comp_type == "button" and text:
        label_var = f"{var}_label"
        block.append(f"    lv_obj_t *{label_var} = lv_label_create({var});")
        block.append(f"    lv_label_set_text({label_var}, {node_text_macro(node, index)});")
        block.append(f"    lv_obj_center({label_var});")
    src = str(node.get("src", node.get("image", ""))).strip()
    if comp_type == "image" and src:
        block.append(f"    {image_set_src}({var}, {node_image_src_macro(node, index)});")
    if x is not None and y is not None:
        block.append(f"    /* {DISPLAY_CONFIG['layout_policy']['exception_marker']}: {reason}. */")
        block.append(f"    lv_obj_set_pos({var}, {x}, {y});")
    if w is not None and h is not None:
        block.append(f"    lv_obj_set_size({var}, {w}, {h});")
    radius = node.get("radius")
    if radius is not None:
        block.append(f"    lv_obj_set_style_radius({var}, {int(radius)}, 0);")
    color = str(node.get("color", "")).lstrip("#")
    if re.fullmatch(r"[0-9a-fA-F]{6}", color):
        if comp_type == "label":
            block.append(f"    lv_obj_set_style_text_color({var}, lv_color_hex(0x{color.upper()}), 0);")
        else:
            block.append(f"    lv_obj_set_style_bg_color({var}, lv_color_hex(0x{color.upper()}), 0);")
    block.append("")
    return block


def analyze_layout_and_patch(args: dict[str, Any]) -> dict[str, Any]:
    layout = load_json_like(args, "layout_json", "layout_path")
    apply_changes = bool(args.get("apply", False))
    target_path = resolve_path(args.get("target_path"), allow_write=apply_changes) if args.get("target_path") else None
    existing_code = str(args.get("existing_code", ""))
    if target_path:
        if not target_path.is_file():
            raise ValueError(f"target_path does not exist: {target_path}")
        original_text = target_path.read_text(encoding="utf-8", errors="replace")
        from_name = str(target_path)
    elif existing_code:
        original_text = existing_code
        from_name = "existing_code"
    else:
        raise ValueError("target_path or existing_code is required")
    lvgl_version = str(args.get("lvgl_version", DISPLAY_CONFIG["lvgl"]["version"]))
    require_choice("lvgl_version", lvgl_version, LVGL_VERSIONS)
    parent_var = str(args.get("parent_var", "root"))
    reason = str(args.get("exception_reason", "visual model incremental layout patch"))
    nodes = flatten_layout_nodes(layout)
    lines = original_text.splitlines()
    objects = parse_lvgl_objects(lines)
    operations: list[dict[str, Any]] = []
    pending_blocks: list[list[str]] = []

    for index, node in enumerate(nodes):
        comp_type = node_type_of(node)
        if comp_type in {"screen", "root", "page"}:
            continue
        text_value = str(node.get("text", node.get("label", "")))
        src = str(node.get("src", node.get("image", ""))).strip()
        if text_value and comp_type in {"label", "button"}:
            macro_status = ensure_c_macro(lines, node_text_macro(node, index), c_text_expr(text_value))
            operations.append({"op": macro_status, "id": node_identifier(node, index), "field": "text_macro", "macro": node_text_macro(node, index)})
            objects = parse_lvgl_objects(lines)
        if src and comp_type == "image":
            macro_status = ensure_c_macro(lines, node_image_src_macro(node, index), image_source_expr(src))
            operations.append({"op": macro_status, "id": node_identifier(node, index), "field": "src_macro", "macro": node_image_src_macro(node, index)})
            objects = parse_lvgl_objects(lines)
        var = find_layout_var(node, index, objects)
        if var is None:
            pending_blocks.append(generate_lvgl_node_block(node, index, parent=parent_var, lvgl_version=lvgl_version, reason=reason))
            operations.append({"op": "append", "id": node_identifier(node, index), "type": comp_type})
            continue
        x, y, w, h = node_box(node)
        if x is not None and y is not None:
            status = replace_or_insert_lvgl_call(lines, objects, var, "pos", f"    lv_obj_set_pos({var}, {x}, {y});", exception_reason=reason)
            objects = parse_lvgl_objects(lines)
            operations.append({"op": status, "var": var, "field": "pos", "value": [x, y]})
        if w is not None and h is not None:
            status = replace_or_insert_lvgl_call(lines, objects, var, "size", f"    lv_obj_set_size({var}, {w}, {h});")
            objects = parse_lvgl_objects(lines)
            operations.append({"op": status, "var": var, "field": "size", "value": [w, h]})
        if text_value and comp_type == "label":
            macro = node_text_macro(node, index)
            ensure_c_macro(lines, macro, c_text_expr(text_value))
            objects = parse_lvgl_objects(lines)
            status = replace_or_insert_lvgl_call(lines, objects, var, "text", f"    lv_label_set_text({var}, {macro});")
            objects = parse_lvgl_objects(lines)
            operations.append({"op": status, "var": var, "field": "text", "value": text_value, "macro": macro})
        if src and comp_type == "image":
            image_set_src = "lv_image_set_src" if lvgl_version == "v9" else "lv_img_set_src"
            macro = node_image_src_macro(node, index)
            ensure_c_macro(lines, macro, image_source_expr(src))
            objects = parse_lvgl_objects(lines)
            status = replace_or_insert_lvgl_call(lines, objects, var, "src", f"    {image_set_src}({var}, {macro});")
            objects = parse_lvgl_objects(lines)
            operations.append({"op": status, "var": var, "field": "src", "value": src, "macro": macro})

    if pending_blocks:
        insert_at = next((i for i, line in enumerate(lines) if re.search(r"\breturn\s+\w+\s*;", line)), len(lines) - 1)
        generated = ["    /* incremental visual-model additions */"]
        for block in pending_blocks:
            generated.extend(block)
        lines[insert_at:insert_at] = generated

    patched_text = "\n".join(lines) + ("\n" if original_text.endswith("\n") else "")
    diff = "\n".join(difflib.unified_diff(original_text.splitlines(), patched_text.splitlines(), fromfile=from_name, tofile=f"{from_name}.patched", lineterm=""))
    patch_path = None
    if args.get("patch_path"):
        patch_path = resolve_path(args["patch_path"], allow_write=True)
        patch_path.parent.mkdir(parents=True, exist_ok=True)
        patch_path.write_text(diff + "\n", encoding="utf-8", newline="\n")
    if apply_changes:
        if target_path is None:
            raise ValueError("apply=true requires target_path")
        # Atomic write: write to temp file, then replace
        tmp_fd, tmp_path = tempfile.mkstemp(dir=target_path.parent, suffix=".tmp", prefix=".codegen_")
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8", newline="\n") as f:
                f.write(patched_text)
            os.replace(tmp_path, target_path)
        except Exception:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise
    validation = None
    if apply_changes and target_path is not None:
        validation = validate_lvgl_layout_code({"path": str(target_path)})
    return {
        "ok": True if validation is None else bool(validation.get("ok")),
        "applied": apply_changes,
        "target_path": str(target_path) if target_path else "",
        "operations": operations,
        "node_count": len(nodes),
        "diff": diff,
        "patch_path": str(patch_path) if patch_path else "",
        "validation": validation,
    }



















def validate_lvgl_layout_code(args: dict[str, Any]) -> dict[str, Any]:
    path = resolve_path(args.get("path"))
    if path.is_dir():
        files = sorted(path.glob("*.c")) + sorted(path.glob("*.h"))
    elif path.is_file():
        files = [path]
    else:
        raise ValueError(f"path does not exist: {path}")
    forbidden = ("lv_obj_set_pos", "lv_obj_set_x", "lv_obj_set_y")
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    for file_path in files:
        lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
        style_calls = 0
        has_style_reuse = any("lv_style_t" in line for line in lines)
        for idx, line in enumerate(lines, start=1):
            if "lv_obj_set_style_" in line:
                style_calls += 1
            if any(token in line for token in forbidden):
                window = "\n".join(lines[max(0, idx - 3):idx])
                if DISPLAY_CONFIG["layout_policy"]["exception_marker"] not in window:
                    errors.append({"file": str(file_path), "line": idx, "message": "absolute positioning requires LVGL_LAYOUT_EXCEPTION"})
            if re.search(r"lv_(img|image)_set_src\s*\([^,]+,\s*\"[A-Z]?:?[^\"&]*\.(png|jpg|jpeg|bmp)", line, re.I):
                warnings.append({"file": str(file_path), "line": idx, "message": "runtime image path should go through a resource layer or generated descriptor"})
        if style_calls > 8 and not has_style_reuse:
            warnings.append({"file": str(file_path), "line": 0, "message": "many direct style calls without lv_style_t reuse"})
    return {"ok": not errors, "errors": errors, "warnings": warnings, "checked_files": [str(p) for p in files]}




















































try:
    from initial_loading_auto import generate_initial_loading_page as generate_initial_loading_page
except Exception:
    pass

try:
    from interactive_scene_auto import generate_interactive_scene_page as generate_interactive_scene_page
except Exception:
    pass
