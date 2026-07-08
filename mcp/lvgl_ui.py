from __future__ import annotations

import json
import os
import re
import textwrap
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
LVGL_VERSIONS = {"v8", "v9"}
IMAGE_FORMATS = {"c_array", "binary", "both"}
COLOR_FORMATS = {"RGB565"}

DISPLAY_CONFIG: dict[str, Any] = {
    "schema": "freertos-embedded-architect.lvgl.display-config.v1",
    "display": {
        "width": 480,
        "height": 800,
        "orientation": "portrait",
        "color_depth": 16,
        "color_format": "RGB565",
        "dpi": 160,
    },
    "lvgl": {"version": "v8", "image_widget": {"v8": "lv_img", "v9": "lv_image"}},
    "fonts": {
        "body": {"name": "ui_font_body_16", "size": 16, "languages": ["en", "zh"]},
        "title": {"name": "ui_font_title_24", "size": 24, "languages": ["en", "zh"]},
        "number": {"name": "ui_font_number_32", "size": 32, "languages": ["digits"]},
        "icon": {"name": "ui_font_icon_16", "size": 16, "languages": ["symbols"]},
    },
    "layout_policy": {
        "preferred": ["flex", "grid"],
        "forbidden_by_default": ["lv_obj_set_pos", "lv_obj_set_x", "lv_obj_set_y"],
        "exception_marker": "LVGL_LAYOUT_EXCEPTION",
        "absolute_position_exceptions": [
            "hardware overlay alignment",
            "pixel-level calibration",
            "short-lived animation staging",
        ],
    },
    "asset_policy": {
        "default_image_output": "c_array",
        "default_color_format": "RGB565",
        "binary_allowed": True,
        "runtime_path_images": "avoid unless decoder/cache lifecycle is proven",
    },
}

THEME_SKILL = """# LVGL Theme/Layout Skill

Use `lvgl://display-config` as the first source of truth for resolution,
color depth, LVGL version, fonts, and asset format.

Hard rules:
- Prefer Flex or Grid for generated page layout.
- Do not use `lv_obj_set_pos`, `lv_obj_set_x`, or `lv_obj_set_y` unless the
  code includes `LVGL_LAYOUT_EXCEPTION: <reason>` immediately above the call.
- Reuse `lv_style_t` objects for repeated typography, card, button, and image
  styles. Avoid many one-off `lv_obj_set_style_*` calls.
- Keep image assets behind generated descriptors or a common resource layer.
- All LVGL object mutation must run on the LVGL/UI task or through
  `lv_async_call`/project equivalent.

Default page structure:
1. root screen/container sized from display config.
2. optional header/content/footer containers.
3. Flex rows/columns for repeated cards/buttons.
4. Grid only when alignment depends on fixed tracks.
5. explicit exception list for every absolute coordinate.
"""

RESOURCE_SCHEMAS: list[dict[str, Any]] = [
    {
        "uri": "lvgl://display-config",
        "name": "LVGL display config",
        "description": "Default LVGL display, font, layout, and asset policy for UI generation.",
        "mimeType": "application/json",
    },
    {
        "uri": "lvgl://theme-skill",
        "name": "LVGL theme/layout skill",
        "description": "Flex/Grid-first LVGL layout instructions for design-to-UI generation.",
        "mimeType": "text/markdown",
    },
]
RESOURCE_URIS = {item["uri"] for item in RESOURCE_SCHEMAS}


def require_choice(name: str, value: str, allowed: set[str]) -> None:
    if value not in allowed:
        raise ValueError(f"{name} must be one of {sorted(allowed)}, got {value!r}")


def get_resource_content(uri: str) -> dict[str, Any]:
    if uri == "lvgl://display-config":
        return {"uri": uri, "mimeType": "application/json", "text": json.dumps(DISPLAY_CONFIG, ensure_ascii=False, indent=2)}
    if uri == "lvgl://theme-skill":
        return {"uri": uri, "mimeType": "text/markdown", "text": THEME_SKILL}
    raise ValueError(f"unknown resource: {uri}")


def get_lvgl_theme_skill(_: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "ok": True,
        "uri": "lvgl://theme-skill",
        "display_config_uri": "lvgl://display-config",
        "content": THEME_SKILL,
        "display_config": DISPLAY_CONFIG,
    }


def safe_symbol(name: str) -> str:
    symbol = re.sub(r"[^A-Za-z0-9_]", "_", name.strip())
    symbol = re.sub(r"_+", "_", symbol).strip("_")
    if not symbol:
        symbol = "ui_image"
    if symbol[0].isdigit():
        symbol = f"ui_{symbol}"
    return symbol.lower()


def resolve_path(value: Any, *, base: Path = ROOT) -> Path:
    if value is None:
        raise ValueError("path is required")
    path = Path(str(value))
    if not path.is_absolute():
        path = base / path
    return path.resolve()

def read_ppm(path: Path) -> tuple[int, int, list[tuple[int, int, int]]]:
    data = path.read_bytes()
    idx = 0

    def token() -> bytes:
        nonlocal idx
        while idx < len(data):
            if data[idx:idx + 1] == b"#":
                while idx < len(data) and data[idx:idx + 1] not in (b"\n", b"\r"):
                    idx += 1
            elif data[idx:idx + 1].isspace():
                idx += 1
            else:
                break
        start = idx
        while idx < len(data) and not data[idx:idx + 1].isspace():
            idx += 1
        return data[start:idx]

    magic = token()
    width = int(token())
    height = int(token())
    max_value = int(token())
    if max_value <= 0 or max_value > 255:
        raise ValueError("only 8-bit PPM images are supported")
    while idx < len(data) and data[idx:idx + 1].isspace():
        idx += 1
    if magic == b"P6":
        raw = data[idx:idx + width * height * 3]
        if len(raw) != width * height * 3:
            raise ValueError("truncated PPM image data")
        return width, height, [(raw[i], raw[i + 1], raw[i + 2]) for i in range(0, len(raw), 3)]
    if magic == b"P3":
        values = [int(part) for part in data[idx:].split()]
        if len(values) < width * height * 3:
            raise ValueError("truncated PPM image data")
        pixels = [(values[i], values[i + 1], values[i + 2]) for i in range(0, width * height * 3, 3)]
        return width, height, pixels
    raise ValueError("unsupported PPM magic; expected P3 or P6")


def read_bmp(path: Path) -> tuple[int, int, list[tuple[int, int, int]]]:
    data = path.read_bytes()
    if len(data) < 54 or data[:2] != b"BM":
        raise ValueError("not a BMP file")
    offset = int.from_bytes(data[10:14], "little")
    dib_size = int.from_bytes(data[14:18], "little")
    if dib_size < 40:
        raise ValueError("unsupported BMP DIB header")
    width = int.from_bytes(data[18:22], "little", signed=True)
    raw_height = int.from_bytes(data[22:26], "little", signed=True)
    planes = int.from_bytes(data[26:28], "little")
    bpp = int.from_bytes(data[28:30], "little")
    compression = int.from_bytes(data[30:34], "little")
    if planes != 1 or compression != 0 or bpp not in (24, 32):
        raise ValueError("only uncompressed 24/32-bit BMP images are supported")
    if width <= 0 or raw_height == 0:
        raise ValueError("invalid BMP dimensions")
    height = abs(raw_height)
    top_down = raw_height < 0
    row_stride = ((width * bpp + 31) // 32) * 4
    pixels: list[tuple[int, int, int]] = []
    for y in range(height):
        src_y = y if top_down else height - 1 - y
        row = offset + src_y * row_stride
        for x in range(width):
            pos = row + x * (bpp // 8)
            if pos + 2 >= len(data):
                raise ValueError("truncated BMP image data")
            b, g, r = data[pos], data[pos + 1], data[pos + 2]
            pixels.append((r, g, b))
    return width, height, pixels


def read_image(path: Path) -> tuple[int, int, list[tuple[int, int, int]]]:
    suffix = path.suffix.lower()
    if suffix in {".ppm", ".pnm"}:
        return read_ppm(path)
    if suffix == ".bmp":
        return read_bmp(path)
    try:
        from PIL import Image  # type: ignore
    except Exception as exc:
        raise ValueError(f"{suffix or 'image'} conversion requires Pillow; use BMP/PPM or install Pillow") from exc
    with Image.open(path) as image:
        rgb = image.convert("RGB")
        width, height = rgb.size
        pixels = list(rgb.getdata())
    return width, height, [(int(r), int(g), int(b)) for r, g, b in pixels]


def rgb565_bytes(pixels: list[tuple[int, int, int]]) -> bytes:
    out = bytearray()
    for r, g, b in pixels:
        value = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
        out.append(value & 0xFF)
        out.append((value >> 8) & 0xFF)
    return bytes(out)


def format_c_bytes(data: bytes) -> str:
    lines: list[str] = []
    for i in range(0, len(data), 12):
        chunk = data[i:i + 12]
        lines.append("    " + ", ".join(f"0x{byte:02X}" for byte in chunk) + ",")
    return "\n".join(lines)


def lvgl_image_descriptor(symbol: str, width: int, height: int, data_name: str, version: str) -> str:
    if version == "v9":
        return textwrap.dedent(
            f"""\
            const lv_image_dsc_t {symbol} = {{
                .header.magic = LV_IMAGE_HEADER_MAGIC,
                .header.cf = LV_COLOR_FORMAT_RGB565,
                .header.w = {width},
                .header.h = {height},
                .data_size = sizeof({data_name}),
                .data = {data_name},
            }};
            """
        )
    return textwrap.dedent(
        f"""\
        const lv_img_dsc_t {symbol} = {{
            .header.always_zero = 0,
            .header.w = {width},
            .header.h = {height},
            .data_size = sizeof({data_name}),
            .header.cf = LV_IMG_CF_TRUE_COLOR,
            .data = {data_name},
        }};
        """
    )

def convert_image_to_lvgl_source(args: dict[str, Any]) -> dict[str, Any]:
    input_path = resolve_path(args.get("input_path"))
    if not input_path.is_file():
        raise ValueError(f"input_path does not exist: {input_path}")
    output_dir = resolve_path(args.get("output_dir", ROOT / "artifacts" / "lvgl_assets"))
    output_dir.mkdir(parents=True, exist_ok=True)
    symbol = safe_symbol(str(args.get("name") or input_path.stem))
    output_format = str(args.get("format", "c_array"))
    color_format = str(args.get("color_format", "RGB565")).upper()
    version = str(args.get("lvgl_version", DISPLAY_CONFIG["lvgl"]["version"]))
    require_choice("format", output_format, IMAGE_FORMATS)
    require_choice("color_format", color_format, COLOR_FORMATS)
    require_choice("lvgl_version", version, LVGL_VERSIONS)

    width, height, pixels = read_image(input_path)
    raw = rgb565_bytes(pixels)
    artifacts: list[str] = []
    if output_format in {"binary", "both"}:
        bin_path = output_dir / f"{symbol}.bin"
        bin_path.write_bytes(raw)
        artifacts.append(str(bin_path))
    if output_format in {"c_array", "both"}:
        data_name = f"{symbol}_map"
        c_path = output_dir / f"{symbol}.c"
        h_path = output_dir / f"{symbol}.h"
        descriptor_type = "lv_image_dsc_t" if version == "v9" else "lv_img_dsc_t"
        c_path.write_text(
            textwrap.dedent(
                f"""\
                #include "lvgl.h"
                #include "{symbol}.h"

                #ifndef LV_ATTRIBUTE_MEM_ALIGN
                #define LV_ATTRIBUTE_MEM_ALIGN
                #endif

                #ifndef LV_ATTRIBUTE_LARGE_CONST
                #define LV_ATTRIBUTE_LARGE_CONST
                #endif

                const LV_ATTRIBUTE_MEM_ALIGN LV_ATTRIBUTE_LARGE_CONST uint8_t {data_name}[] = {{
                {format_c_bytes(raw)}
                }};

                {lvgl_image_descriptor(symbol, width, height, data_name, version)}
                """
            ),
            encoding="utf-8",
            newline="\n",
        )
        guard = f"{symbol.upper()}_H"
        h_path.write_text(
            textwrap.dedent(
                f"""\
                #ifndef {guard}
                #define {guard}

                #include "lvgl.h"

                extern const {descriptor_type} {symbol};

                #endif /* {guard} */
                """
            ),
            encoding="utf-8",
            newline="\n",
        )
        artifacts.extend([str(c_path), str(h_path)])
    return {
        "ok": True,
        "input": str(input_path),
        "width": width,
        "height": height,
        "color_format": color_format,
        "byte_order": "RGB565 little-endian bytes",
        "symbol": symbol,
        "artifacts": artifacts,
    }


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


def emit_component(component: dict[str, Any], parent: str, lines: list[str], *, lvgl_version: str = "v8") -> None:
    comp_id = safe_symbol(str(component.get("id", component.get("type", "obj"))))
    comp_type = str(component.get("type", "container"))
    var = f"{comp_id}_obj"
    if comp_type == "label":
        lines.append(f"    lv_obj_t *{var} = lv_label_create({parent});")
        lines.append(f'    lv_label_set_text({var}, "{str(component.get("text", ""))}");')
        lines.append(f"    lv_obj_add_style({var}, &s_text_style, 0);")
    elif comp_type == "button":
        lines.append(f"    lv_obj_t *{var} = lv_btn_create({parent});")
        lines.append(f"    lv_obj_add_style({var}, &s_button_style, 0);")
        text = str(component.get("text", ""))
        if text:
            label_var = f"{comp_id}_label"
            lines.append(f"    lv_obj_t *{label_var} = lv_label_create({var});")
            lines.append(f'    lv_label_set_text({label_var}, "{text}");')
            lines.append(f"    lv_obj_center({label_var});")
        event = component.get("event")
        if event:
            callback = safe_symbol(str(event))
            lines.append(f"    lv_obj_add_event_cb({var}, {callback}, LV_EVENT_CLICKED, NULL);")
    elif comp_type == "image":
        image_create = "lv_image_create" if lvgl_version == "v9" else "lv_img_create"
        image_set_src = "lv_image_set_src" if lvgl_version == "v9" else "lv_img_set_src"
        lines.append(f"    lv_obj_t *{var} = {image_create}({parent});")
        src = safe_symbol(str(component.get("src", component.get("id", "image"))))
        lines.append(f"    {image_set_src}({var}, &{src});")
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
        emit_component(child, var, lines, lvgl_version=lvgl_version)


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

    create_fn = f"ui_{page_name}_create"
    c_path = output_dir / f"ui_{page_name}.c"
    h_path = output_dir / f"ui_{page_name}.h"
    theme_h = output_dir / "ui_theme.h"
    body_lines: list[str] = []
    for component in components:
        if not isinstance(component, dict):
            raise ValueError("spec.components entries must be objects")
        emit_component(component, "root", body_lines, lvgl_version=version)
    event_stubs = "\n".join(
        f"static void {event}(lv_event_t *e)\n{{\n    (void)e;\n    /* TODO: connect generated UI event to presenter/action layer. */\n}}\n"
        for event in collect_events(components)
    )
    body = "\n".join(body_lines) if body_lines else "    /* TODO: add components from layout spec. */"
    c_path.write_text(
        textwrap.dedent(
            f"""\
            #include "ui_{page_name}.h"
            #include "ui_theme.h"

            #include <stdbool.h>

            {event_stubs}
            static lv_style_t s_text_style;
            static lv_style_t s_button_style;

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

            {body}

                return root;
            }}
            """
        ),
        encoding="utf-8",
        newline="\n",
    )
    h_guard = f"UI_{page_name.upper()}_H"
    h_path.write_text(
        textwrap.dedent(
            f"""\
            #ifndef {h_guard}
            #define {h_guard}

            #include "lvgl.h"

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


def prepare_lvgl_sim_project(args: dict[str, Any]) -> dict[str, Any]:
    output_dir = resolve_path(args.get("output_dir", ROOT / "artifacts" / "lvgl_sim"))
    output_dir.mkdir(parents=True, exist_ok=True)
    lvgl_root = str(args.get("lvgl_root") or os.environ.get("LVGL_ROOT") or "")
    sdl_ready = bool(os.environ.get("SDL2_DIR") or os.environ.get("SDL_ROOT"))
    readme = output_dir / "README.md"
    readme.write_text(
        textwrap.dedent(
            f"""\
            # LVGL simulator skeleton

            This directory is a generated placeholder for local LVGL UI checks.

            Required before native build:
            - Set `LVGL_ROOT` to a local LVGL checkout.
            - Install/configure SDL2 and expose `SDL2_DIR` or `SDL_ROOT`.
            - Copy generated `ui_*.c/.h` files into the app source list.

            Detected LVGL_ROOT: {lvgl_root or "not configured"}
            SDL configured: {sdl_ready}
            """
        ),
        encoding="utf-8",
        newline="\n",
    )
    available = bool(lvgl_root and Path(lvgl_root).exists() and sdl_ready)
    return {
        "ok": True,
        "available": available,
        "status": "ready" if available else "not_available",
        "artifacts": [str(readme)],
        "message": "simulator environment detected" if available else "set LVGL_ROOT and SDL2_DIR/SDL_ROOT to build locally",
    }


LVGL_TOOLS = {
    "get_lvgl_theme_skill": get_lvgl_theme_skill,
    "convert_image_to_lvgl_source": convert_image_to_lvgl_source,
    "generate_lvgl_layout_spec": generate_lvgl_layout_spec,
    "generate_lvgl_page_code": generate_lvgl_page_code,
    "validate_lvgl_layout_code": validate_lvgl_layout_code,
    "prepare_lvgl_sim_project": prepare_lvgl_sim_project,
}

LVGL_TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "get_lvgl_theme_skill",
        "description": "Return Flex/Grid-first LVGL UI generation rules and the default display config.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "convert_image_to_lvgl_source",
        "description": "Convert a cut image into LVGL RGB565 C-array and/or binary assets.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "input_path": {"type": "string"},
                "output_dir": {"type": "string", "default": "artifacts/lvgl_assets"},
                "name": {"type": "string"},
                "format": {"type": "string", "enum": sorted(IMAGE_FORMATS), "default": "c_array"},
                "color_format": {"type": "string", "enum": sorted(COLOR_FORMATS), "default": "RGB565"},
                "lvgl_version": {"type": "string", "enum": sorted(LVGL_VERSIONS), "default": "v8"},
            },
            "required": ["input_path"],
            "additionalProperties": False,
        },
    },
    {
        "name": "generate_lvgl_layout_spec",
        "description": "Create a Flex/Grid-first LVGL page spec skeleton from design notes and assets.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "page_name": {"type": "string", "default": "page"},
                "design_notes": {"type": "string", "default": ""},
                "assets": {"type": "array", "items": {"type": "object"}},
                "display_config_uri": {"type": "string", "default": "lvgl://display-config"},
                "layout": {"type": "string", "enum": ["auto", "flex", "grid"], "default": "auto"},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "generate_lvgl_page_code",
        "description": "Generate LVGL C/H page scaffold from a layout spec using Flex/Grid-first layout.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "spec_json": {"type": "object"},
                "spec_path": {"type": "string"},
                "output_dir": {"type": "string", "default": "artifacts/lvgl_ui"},
                "lvgl_version": {"type": "string", "enum": sorted(LVGL_VERSIONS), "default": "v8"},
            },
            "additionalProperties": True,
        },
    },
    {
        "name": "validate_lvgl_layout_code",
        "description": "Statically check LVGL code for forbidden absolute layout and asset path drift.",
        "inputSchema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
            "additionalProperties": False,
        },
    },
    {
        "name": "prepare_lvgl_sim_project",
        "description": "Create a lightweight LVGL simulator skeleton and report local LVGL/SDL readiness.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "output_dir": {"type": "string", "default": "artifacts/lvgl_sim"},
                "lvgl_root": {"type": "string"},
            },
            "additionalProperties": False,
        },
    },
]
