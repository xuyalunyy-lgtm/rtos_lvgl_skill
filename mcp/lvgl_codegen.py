"""LVGL code generation from UI Spec v2.

Generates C/H page code from structured UI specification.
Supports both LVGL v8 and v9 backends.

Usage:
    python mcp/lvgl_codegen.py --spec path/to/ui_spec.json --output-dir artifacts/lvgl_ui --json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import textwrap
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent

# ── ID/Name sanitization ──────────────────────────────────────────


def safe_c_identifier(name: str) -> str:
    """Convert to valid C identifier."""
    # Replace non-alphanumeric with underscore
    s = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    # Remove leading digits
    s = re.sub(r'^(\d)', r'_\1', s)
    # Collapse multiple underscores
    s = re.sub(r'_+', '_', s).strip('_')
    return s.lower()


def safe_macro_name(name: str) -> str:
    """Convert to valid C macro name (UPPER_CASE)."""
    return safe_c_identifier(name).upper()


def page_function_name(page_name: str) -> str:
    """Generate page create/destroy function names."""
    base = safe_c_identifier(page_name)
    return f"ui_page_{base}"


# ── Style generation ──────────────────────────────────────────────


def generate_style_code(var_name: str, styles: dict[str, Any], lvgl_version: str) -> list[str]:
    """Generate LVGL style setting code."""
    lines = []
    if not styles:
        return lines

    if lvgl_version == "v9":
        prefix = "lv_obj_set_style"
    else:
        prefix = "lv_obj_set_style"

    # Background
    if "bg_color" in styles:
        color = styles["bg_color"].lstrip("#")
        lines.append(f"    {prefix}_bg_color({var_name}, lv_color_hex(0x{color.upper()}), 0);")
    if "bg_opa" in styles:
        lines.append(f"    {prefix}_bg_opa({var_name}, {styles['bg_opa']}, 0);")

    # Border
    if "border_width" in styles:
        lines.append(f"    {prefix}_border_width({var_name}, {styles['border_width']}, 0);")
    if "border_color" in styles:
        color = styles["border_color"].lstrip("#")
        lines.append(f"    {prefix}_border_color({var_name}, lv_color_hex(0x{color.upper()}), 0);")

    # Radius
    if "radius" in styles:
        lines.append(f"    {prefix}_radius({var_name}, {styles['radius']}, 0);")

    # Shadow
    if "shadow_width" in styles:
        lines.append(f"    {prefix}_shadow_width({var_name}, {styles['shadow_width']}, 0);")

    # Text
    if "text_color" in styles:
        color = styles["text_color"].lstrip("#")
        lines.append(f"    {prefix}_text_color({var_name}, lv_color_hex(0x{color.upper()}), 0);")
    if "font" in styles:
        font_expr = str(styles["font"]).strip()
        if re.fullmatch(r"&?[A-Za-z_][A-Za-z0-9_]*", font_expr):
            lines.append(f"    {prefix}_text_font({var_name}, {font_expr}, 0);")
    if "text_font_size" in styles:
        # Font size is handled via font reference, not direct style
        pass
    if "text_align" in styles:
        align_map = {"left": "LV_TEXT_ALIGN_LEFT", "center": "LV_TEXT_ALIGN_CENTER", "right": "LV_TEXT_ALIGN_RIGHT"}
        align = align_map.get(styles["text_align"], "LV_TEXT_ALIGN_LEFT")
        lines.append(f"    {prefix}_text_align({var_name}, {align}, 0);")

    # Padding
    for side in ["top", "bottom", "left", "right"]:
        key = f"pad_{side}"
        if key in styles:
            lines.append(f"    {prefix}_pad_{side}({var_name}, {styles[key]}, 0);")

    # Size
    if "width" in styles and styles["width"] > 0:
        lines.append(f"    lv_obj_set_width({var_name}, {styles['width']});")
    if "height" in styles and styles["height"] > 0:
        lines.append(f"    lv_obj_set_height({var_name}, {styles['height']});")

    return lines


# ── Layout generation ─────────────────────────────────────────────


def generate_layout_code(var_name: str, layout: dict[str, Any], lvgl_version: str) -> list[str]:
    """Generate Flex/Grid layout code."""
    lines = []
    mode = layout.get("mode", "flex-column")

    if mode.startswith("flex"):
        lines.append(f"    lv_obj_set_flex_flow({var_name}, {'LV_FLEX_FLOW_ROW' if mode == 'flex-row' else 'LV_FLEX_FLOW_COLUMN'});")
        if "gap" in layout:
            lines.append(f"    lv_obj_set_flex_align({var_name}, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_START);")
            lines.append(f"    lv_obj_set_style_pad_gap({var_name}, {layout['gap']}, 0);")
        justify = layout.get("flex_justify", "start")
        justify_map = {"start": "LV_FLEX_ALIGN_START", "center": "LV_FLEX_ALIGN_CENTER", "end": "LV_FLEX_ALIGN_END",
                       "space-between": "LV_FLEX_ALIGN_SPACE_BETWEEN", "space-around": "LV_FLEX_ALIGN_SPACE_AROUND"}
        if justify in justify_map:
            lines.append(f"    lv_obj_set_flex_align({var_name}, {justify_map[justify]}, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_START);")

    elif mode == "grid":
        cols = layout.get("grid_columns", [])
        rows = layout.get("grid_rows", [])
        if cols:
            col_desc = ", ".join(str(c) for c in cols)
            lines.append(f"    /* Grid: {len(cols)} columns */")
        if rows:
            row_desc = ", ".join(str(r) for r in rows)
            lines.append(f"    /* Grid: {len(rows)} rows */")

    return lines


# ── Widget generation ─────────────────────────────────────────────


WIDGET_CREATORS = {
    "screen": {"v8": "lv_obj_create", "v9": "lv_obj_create"},
    "container": {"v8": "lv_obj_create", "v9": "lv_obj_create"},
    "label": {"v8": "lv_label_create", "v9": "lv_label_create"},
    "button": {"v8": "lv_btn_create", "v9": "lv_btn_create"},
    "image": {"v8": "lv_img_create", "v9": "lv_image_create"},
    "bar": {"v8": "lv_bar_create", "v9": "lv_bar_create"},
    "slider": {"v8": "lv_slider_create", "v9": "lv_slider_create"},
    "switch": {"v8": "lv_switch_create", "v9": "lv_switch_create"},
    "checkbox": {"v8": "lv_checkbox_create", "v9": "lv_checkbox_create"},
    "dropdown": {"v8": "lv_dropdown_create", "v9": "lv_dropdown_create"},
    "roller": {"v8": "lv_roller_create", "v9": "lv_roller_create"},
    "spinner": {"v8": "lv_spinner_create", "v9": "lv_spinner_create"},
    "arc": {"v8": "lv_arc_create", "v9": "lv_arc_create"},
}

TEXT_SETTERS = {
    "v8": "lv_label_set_text",
    "v9": "lv_label_set_text",
}

IMAGE_SETTERS = {
    "v8": "lv_img_set_src",
    "v9": "lv_image_set_src",
}


def generate_widget_code(
    node: dict[str, Any],
    parent_var: str,
    lvgl_version: str,
    page_name: str,
) -> tuple[list[str], str]:
    """Generate C code for a single widget.

    Returns:
        (code_lines, variable_name)
    """
    lines = []
    node_id = node.get("id", "unknown")
    node_type = node.get("type", "container")
    var_name = f"s_{safe_c_identifier(node_id)}"

    # Get creator function
    creator = WIDGET_CREATORS.get(node_type, WIDGET_CREATORS["container"]).get(lvgl_version, "lv_obj_create")

    # A UI Spec screen is the page's content root, not an independent LVGL
    # display screen. Attaching it to parent keeps it owned by the Router.
    lines.append(f"    {var_name} = {creator}({parent_var});")
    if node_type == "screen":
        lines.append(f"    lv_obj_set_size({var_name}, LV_PCT(100), LV_PCT(100));")
        if node.get("full_screen_tap"):
            lines.append(f"    lv_obj_add_flag({var_name}, LV_OBJ_FLAG_CLICKABLE);")

    # Set text
    text = node.get("text", "")
    text_macro = node.get("text_macro", "")
    if text and node_type in ("label", "button"):
        if text_macro:
            # Use macro for runtime-updateable text
            lines.append(f"    {TEXT_SETTERS[lvgl_version]}({var_name}, {text_macro});")
        else:
            # Escape text for C string
            escaped = text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
            lines.append(f'    {TEXT_SETTERS[lvgl_version]}({var_name}, "{escaped}");')

    # Set image source.  ``src`` remains the renderer-facing asset key while
    # ``src_expr`` carries the generated C descriptor (for example
    # ``&UI_IMG_BG_HOME``).  Never turn a C descriptor into a path macro.
    src = node.get("src", "")
    src_expr = node.get("src_expr", "")
    src_macro = node.get("src_macro", "")
    if node_type == "image":
        if isinstance(src_expr, str) and re.fullmatch(r"&?[A-Za-z_][A-Za-z0-9_]*", src_expr):
            lines.append(f"    {IMAGE_SETTERS[lvgl_version]}({var_name}, {src_expr});")
        elif src and src_macro:
            lines.append(f"    {IMAGE_SETTERS[lvgl_version]}({var_name}, {src_macro});")
        elif src:
            lines.append(f"    {IMAGE_SETTERS[lvgl_version]}({var_name}, \"{src}\");")
        if node.get("image_fit") == "stretch" and lvgl_version == "v9":
            # The bbox is the authored target size.  LVGL's default image
            # alignment keeps the source's native size, so opt in explicitly
            # for per-page non-uniform card sizing.
            lines.append(f"    lv_image_set_inner_align({var_name}, LV_IMAGE_ALIGN_STRETCH);")

    # Set value for bar/slider
    if "value" in node and node_type in ("bar", "slider"):
        lines.append(f"    lv_bar_set_value({var_name}, {node['value']}, LV_ANIM_OFF);")
    if "range_min" in node and "range_max" in node and node_type in ("bar", "slider"):
        lines.append(f"    lv_bar_set_range({var_name}, {node['range_min']}, {node['range_max']});")

    # Apply styles
    styles = node.get("styles", {})
    lines.extend(generate_style_code(var_name, styles, lvgl_version))

    # Source bboxes are absolute design coordinates for this generator.  A
    # page spec that uses them must attach positioned nodes to the screen root
    # (containers can still use their own relative child geometry explicitly).
    bbox = node.get("source_bbox")
    if isinstance(bbox, list) and len(bbox) == 4 and all(isinstance(v, int) for v in bbox):
        x, y, width, height = bbox
        if node_type != "screen":
            lines.append(f"    lv_obj_set_pos({var_name}, {x}, {y});")
            lines.append(f"    lv_obj_set_size({var_name}, {width}, {height});")

    # Apply layout
    layout = node.get("layout", {})
    if layout and node_type in ("container", "screen"):
        lines.extend(generate_layout_code(var_name, layout, lvgl_version))

    lines.append("")
    return lines, var_name


# ── Page generation ───────────────────────────────────────────────


def generate_page_code(spec: dict[str, Any], lvgl_version: str | None = None) -> dict[str, Any]:
    """Generate complete page C/H code from UI Spec.

    Args:
        spec: UI Spec v2 dict.
        lvgl_version: Override spec's lvgl_version if provided.

    Returns:
        {"ok": bool, "c_code": str, "h_code": str, "errors": list, "warnings": list}
    """
    errors: list[str] = []
    warnings: list[str] = []

    page_name = spec.get("page_name", "page")
    version = lvgl_version or spec.get("lvgl_version", "v9")
    if version not in ("v8", "v9"):
        errors.append(f"Unsupported LVGL version: {version}")
        return {"ok": False, "errors": errors}

    nodes = spec.get("nodes", [])
    if not nodes:
        errors.append("No nodes in UI Spec")
        return {"ok": False, "errors": errors}

    # Build parent map
    node_map = {n["id"]: n for n in nodes}
    children_map: dict[str, list[str]] = {}
    root_nodes = []
    for n in nodes:
        parent_id = n.get("parent_id")
        if parent_id and parent_id in node_map:
            children_map.setdefault(parent_id, []).append(n["id"])
        elif not parent_id or parent_id not in node_map:
            root_nodes.append(n["id"])

    # Validate IDs
    seen_ids = set()
    for n in nodes:
        nid = n.get("id", "")
        if not nid:
            errors.append(f"Node missing id: {n}")
            continue
        if nid in seen_ids:
            errors.append(f"Duplicate node id: {nid}")
        seen_ids.add(nid)
        # Validate C identifier
        if not re.match(r'^[a-z][a-z0-9_]*$', nid):
            warnings.append(f"Node id '{nid}' is not snake_case — will be sanitized")

    if errors:
        return {"ok": False, "errors": errors, "warnings": warnings}

    # ── Generate includes ──
    includes = [
        '#include "lvgl.h"',
        f'#include "ui_page_{safe_c_identifier(page_name)}.h"',
        '#include <string.h>',
    ]
    font_bundle = spec.get("font_bundle", {})
    if isinstance(font_bundle, dict):
        header = font_bundle.get("header")
        if isinstance(header, str) and re.fullmatch(r"[A-Za-z0-9_.-]+", header):
            includes.append(f'#include "{header}"')
    asset_bundle = spec.get("asset_bundle", {})
    if isinstance(asset_bundle, dict):
        header = asset_bundle.get("header")
        if isinstance(header, str) and re.fullmatch(r"[A-Za-z0-9_.-]+", header):
            includes.append(f'#include "{header}"')
    asset_header = spec.get("asset_header")
    if isinstance(asset_header, str) and re.fullmatch(r"[A-Za-z0-9_.-]+", asset_header):
        includes.append(f'#include "{asset_header}"')
    # Add asset includes
    for asset in spec.get("assets", []):
        symbol = asset.get("symbol", "")
        if symbol:
            includes.append(f'#include "{safe_c_identifier(symbol)}.h"')
    # Add font includes
    for font in spec.get("fonts", []):
        name = font.get("name", "")
        if name:
            includes.append(f'#include "{safe_c_identifier(name)}.h"')

    # ── Generate macros ──
    macros = []
    # Text macros
    for node in nodes:
        text_macro = node.get("text_macro", "")
        text = node.get("text", "")
        if text_macro and text:
            escaped = text.replace("\\", "\\\\").replace('"', '\\"')
            macros.append(f'#ifndef {text_macro}')
            macros.append(f'#define {text_macro} "{escaped}"')
            macros.append(f'#endif')
    # Image source macros
    for node in nodes:
        src_macro = node.get("src_macro", "")
        src = node.get("src", "")
        if src_macro and src and not node.get("src_expr"):
            macros.append(f'#ifndef {src_macro}')
            macros.append(f'#define {src_macro} "{src}"')
            macros.append(f'#endif')
    # Theme macros
    theme = spec.get("theme", {})
    for key, value in theme.items():
        if isinstance(value, str) and value.startswith("#"):
            macro_name = f"UI_COLOR_{safe_macro_name(key)}"
            color = value.lstrip("#")
            macros.append(f'#ifndef {macro_name}')
            macros.append(f'#define {macro_name} 0x{color.upper()}')
            macros.append(f'#endif')

    # ── Generate static variables ──
    static_vars = []
    for node in nodes:
        var = f"s_{safe_c_identifier(node['id'])}"
        static_vars.append(f"static lv_obj_t *{var} = NULL;")

    # ── Generate widget creation ──
    create_lines = []
    func_name = page_function_name(page_name)
    create_lines.append(f"lv_obj_t *{func_name}_create(lv_obj_t *parent)")
    create_lines.append("{")
    create_lines.append(f"    lv_obj_t *root = lv_obj_create(parent);")
    create_lines.append(f"    lv_obj_set_size(root, {spec.get('display', {}).get('width', 480)}, {spec.get('display', {}).get('height', 800)});")
    create_lines.append("")

    # Generate widgets in tree order
    def _generate_node(node_id: str, parent_var: str):
        node = node_map[node_id]
        code, var = generate_widget_code(node, parent_var, version, page_name)
        create_lines.extend(code)
        for child_id in children_map.get(node_id, []):
            _generate_node(child_id, var)

    for root_id in root_nodes:
        _generate_node(root_id, "root")

    create_lines.append("    return root;")
    create_lines.append("}")

    # App-mode page contract.  These functions are harmless for single-page
    # output and give Router/Presenter a deterministic way to own objects.
    lifecycle_funcs = [
        f"void {func_name}_destroy(lv_obj_t *root)",
        "{",
        "    if (root != NULL) lv_obj_del(root);",
        *[f"    s_{safe_c_identifier(node['id'])} = NULL;" for node in nodes],
        "}",
        "",
        f"int {func_name}_set_state(const char *state)",
        "{",
        "    if (state == NULL) return -1;",
        "    /* State-specific overrides are applied by the generated app IR. */",
        "    return 0;",
        "}",
        "",
        f"void {func_name}_refresh(void)",
        "{",
        "    /* Bindings are refreshed by the generated Presenter. */",
        "}",
        "",
        f"lv_obj_t *{func_name}_get_node(const char *node_id)",
        "{",
        "    if (node_id == NULL) return NULL;",
        *[f'    if (strcmp(node_id, "{safe_c_identifier(node["id"])}") == 0) return s_{safe_c_identifier(node["id"])};' for node in nodes],
        "    return NULL;",
        "}",
    ]

    # ── Generate update functions ──
    update_funcs = []
    for node in nodes:
        text_macro = node.get("text_macro", "")
        if text_macro:
            var = f"s_{safe_c_identifier(node['id'])}"
            func = f"{func_name}_set_{safe_c_identifier(node['id'])}_text"
            update_funcs.append(f"")
            update_funcs.append(f"void {func}(const char *text)")
            update_funcs.append(f"{{")
            update_funcs.append(f"    if ({var} != NULL && text != NULL) {{")
            update_funcs.append(f"        {TEXT_SETTERS[version]}({var}, text);")
            update_funcs.append(f"    }}")
            update_funcs.append(f"}}")

    # ── Assemble C source ──
    c_parts = [
        "\n".join(includes),
        "",
        "\n".join(macros) if macros else "",
        "",
        "/* ── Static widget handles ── */",
        "\n".join(static_vars),
        "",
        "/* ── Page create ── */",
        "\n".join(create_lines),
        "",
        "/* ── App lifecycle and node registry ── */",
        "\n".join(lifecycle_funcs),
    ]
    if update_funcs:
        c_parts.append("")
        c_parts.append("/* ── Update functions ── */")
        c_parts.append("\n".join(update_funcs))
    c_code = "\n".join(c_parts)

    # ── Generate header ──
    guard = f"UI_PAGE_{safe_macro_name(page_name)}_H"
    h_code = textwrap.dedent(f"""\
        #ifndef {guard}
        #define {guard}

        #include "lvgl.h"

        /* ── Macros ── */
        {chr(10).join(macros)}

        /* ── Page lifecycle ── */
        lv_obj_t *{func_name}_create(lv_obj_t *parent);
        void {func_name}_destroy(lv_obj_t *root);
        int {func_name}_set_state(const char *state);
        void {func_name}_refresh(void);
        lv_obj_t *{func_name}_get_node(const char *node_id);

        /* ── Update functions ── */
        {chr(10).join(f'void {func_name}_set_{safe_c_identifier(n["id"])}_text(const char *text);' for n in nodes if n.get("text_macro"))}

        #endif /* {guard} */
    """)

    return {
        "ok": True,
        "c_code": c_code,
        "h_code": h_code,
        "page_name": page_name,
        "lvgl_version": version,
        "node_count": len(nodes),
        "errors": errors,
        "warnings": warnings,
    }


# ── File output ───────────────────────────────────────────────────


def write_page_files(spec: dict[str, Any], output_dir: str | Path, lvgl_version: str | None = None) -> dict[str, Any]:
    """Generate and write page C/H files.

    Args:
        spec: UI Spec v2.
        output_dir: Directory to write files.
        lvgl_version: Override version.

    Returns:
        Result dict with file paths.
    """
    result = generate_page_code(spec, lvgl_version)
    if not result["ok"]:
        return result

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    page_name = spec.get("page_name", "page")
    c_path = out / f"ui_page_{safe_c_identifier(page_name)}.c"
    h_path = out / f"ui_page_{safe_c_identifier(page_name)}.h"

    c_path.write_text(result["c_code"], encoding="utf-8", newline="\n")
    h_path.write_text(result["h_code"], encoding="utf-8", newline="\n")

    result["c_path"] = str(c_path)
    result["h_path"] = str(h_path)
    return result


# ── CLI ───────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", required=True, help="Path to UI Spec JSON")
    parser.add_argument("--output-dir", default="artifacts/lvgl_ui", help="Output directory")
    parser.add_argument("--lvgl-version", choices=["v8", "v9"], help="Override LVGL version")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    spec_path = Path(args.spec)
    if not spec_path.is_file():
        print(f"ERROR: Spec not found: {args.spec}")
        return 1

    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    result = write_page_files(spec, args.output_dir, args.lvgl_version)

    if args.json:
        # Remove large code strings for JSON output
        output = {k: v for k, v in result.items() if k not in ("c_code", "h_code")}
        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        if result["ok"]:
            print(f"Page: {result['page_name']} ({result['lvgl_version']})")
            print(f"Nodes: {result['node_count']}")
            print(f"C: {result.get('c_path', 'N/A')}")
            print(f"H: {result.get('h_path', 'N/A')}")
            for w in result["warnings"]:
                print(f"  WARN: {w}")
        else:
            for e in result["errors"]:
                print(f"  ERROR: {e}")

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
