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
    "lvgl": {"version": "v9", "image_widget": {"v8": "lv_img", "v9": "lv_image"}},
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

REGRESSION_SANDBOX_CONFIG: dict[str, Any] = {
    "schema": "freertos-embedded-architect.lvgl.regression-sandbox-config.v1",
    "template_path": "assets/lvgl_regression_sandbox_template",
    "default_width": 480,
    "default_height": 800,
    "default_frames": 120,
    "timeout_seconds": 20,
    "pixel_threshold": {"max_changed_ratio": 0.01, "max_channel_delta": 8},
    "log_error_patterns": [
        "LVGL ASSERT",
        "SDL2 libraries not found",
        "SDL initialization failed",
        "image decoder failed",
        "resource missing",
        "segmentation fault",
        "access violation",
    ],
    "excluded_template_paths": [".git", ".cache", "build", "bin", "*.obj", "*.log", "temp_*"],
}

REGRESSION_SANDBOX_README = """# LVGL Regression Sandbox

Use this sandbox to build generated LVGL UI code, run it in a PC simulator,
and compare screenshots/logs against a baseline.

Flow:
1. `prepare_lvgl_regression_sandbox` creates an isolated sandbox workspace.
2. `build_lvgl_regression_sandbox` configures/builds it with CMake.
3. `run_lvgl_regression_sandbox` runs the executable and captures logs.
4. `compare_lvgl_screenshot` compares actual vs baseline PPM/BMP/PNG images.
5. `lvgl_render` builds/runs one LVGL snippet and returns PNG + object-tree JSON.
6. `run_lvgl_ui_regression` calls `lvgl_render`, then checks pixels, structure, and logs.

The template is source-only. Build outputs, screenshots, and accepted baselines
belong in caller work directories, not in the skill runtime.
"""

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
    {
        "uri": "lvgl://regression-sandbox-config",
        "name": "LVGL regression sandbox config",
        "description": "Default build, run, screenshot, and log-scan policy for LVGL UI regression.",
        "mimeType": "application/json",
    },
    {
        "uri": "lvgl://regression-sandbox-readme",
        "name": "LVGL regression sandbox README",
        "description": "MCP usage flow for the LVGL UI rendering and regression sandbox.",
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
    if uri == "lvgl://regression-sandbox-config":
        return {"uri": uri, "mimeType": "application/json", "text": json.dumps(REGRESSION_SANDBOX_CONFIG, ensure_ascii=False, indent=2)}
    if uri == "lvgl://regression-sandbox-readme":
        return {"uri": uri, "mimeType": "text/markdown", "text": REGRESSION_SANDBOX_README}
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
    if magic == b"P6":
        if idx < len(data) and data[idx:idx + 1].isspace():
            if data[idx:idx + 2] == b"\r\n":
                idx += 2
            else:
                idx += 1
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


def write_png(path: Path, width: int, height: int, pixels: list[tuple[int, int, int]]) -> None:
    import struct
    import zlib

    if width <= 0 or height <= 0:
        raise ValueError("PNG dimensions must be positive")
    if len(pixels) != width * height:
        raise ValueError("pixel count does not match PNG dimensions")

    def chunk(kind: bytes, payload: bytes) -> bytes:
        crc = zlib.crc32(kind + payload) & 0xFFFFFFFF
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", crc)

    raw = bytearray()
    for y in range(height):
        raw.append(0)  # filter type 0
        for r, g, b in pixels[y * width:(y + 1) * width]:
            raw.extend((r & 0xFF, g & 0xFF, b & 0xFF))
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b""))


def convert_image_to_png(source: Path, target: Path) -> dict[str, Any]:
    width, height, pixels = read_image(source)
    write_png(target, width, height, pixels)
    return {"path": str(target), "width": width, "height": height, "sha256": _hash_bytes(target.read_bytes())}


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


def sandbox_template_dir() -> Path:
    return ROOT / "assets" / "lvgl_regression_sandbox_template"


def _copytree_merge(src: Path, dst: Path) -> None:
    import shutil

    if not src.is_dir():
        raise ValueError(f"sandbox template not found: {src}")
    for item in src.rglob("*"):
        rel = item.relative_to(src)
        target = dst / rel
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, target)


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def _tool_available(name: str) -> str | None:
    import shutil

    found = shutil.which(name)
    return str(Path(found).resolve()) if found else None


def _run_process(argv: list[str], *, cwd: Path, timeout: int, path_prefix: str = "") -> dict[str, Any]:
    import subprocess

    env = os.environ.copy()
    if path_prefix:
        env["PATH"] = path_prefix + os.pathsep + env.get("PATH", "")
    try:
        proc = subprocess.run(argv, cwd=cwd, env=env, capture_output=True, encoding="utf-8", errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        return {
            "argv": argv,
            "cwd": str(cwd),
            "exit_code": -1,
            "stdout": (exc.stdout or "") if isinstance(exc.stdout, str) else "",
            "stderr": (exc.stderr or "") if isinstance(exc.stderr, str) else "",
            "timeout": True,
            "message": f"process timed out after {timeout}s",
        }
    return {"argv": argv, "cwd": str(cwd), "exit_code": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr, "timeout": False}


def prepare_lvgl_regression_sandbox(args: dict[str, Any]) -> dict[str, Any]:
    output_dir = resolve_path(args.get("output_dir", ROOT / "artifacts" / "lvgl_regression_sandbox"))
    output_dir.mkdir(parents=True, exist_ok=True)
    _copytree_merge(sandbox_template_dir(), output_dir)

    config = dict(REGRESSION_SANDBOX_CONFIG)
    config["width"] = int(args.get("width", DISPLAY_CONFIG["display"]["width"]))
    config["height"] = int(args.get("height", DISPLAY_CONFIG["display"]["height"]))
    config["lvgl_root"] = str(args.get("lvgl_root", ""))
    config["sdl2_root"] = str(args.get("sdl2_root", ""))
    config["sdl2_dir"] = str(args.get("sdl2_dir", ""))
    config["ui_under_test_dir"] = str(args.get("ui_under_test_dir", ""))
    config["ui_entry_function"] = str(args.get("ui_entry_function", ""))
    config["ui_header"] = str(args.get("ui_header", ""))
    config["prepared_from"] = str(sandbox_template_dir())
    if config["ui_entry_function"]:
        header = config["ui_header"] or "ui_under_test.h"
        entry = safe_symbol(config["ui_entry_function"])
        (output_dir / "src" / "ui_under_test_default.c").write_text(
            textwrap.dedent(
                f"""\
                #include "ui_under_test_default.h"
                #include "{header}"

                extern lv_obj_t *{entry}(lv_obj_t *parent);

                lv_obj_t *ui_under_test_create(lv_obj_t *parent)
                {{
                    return {entry}(parent);
                }}
                """
            ),
            encoding="utf-8",
            newline="\n",
        )
    _write_json(output_dir / "sandbox_config.json", config)

    return {
        "ok": True,
        "sandbox_dir": str(output_dir),
        "template_dir": str(sandbox_template_dir()),
        "artifacts": [str(output_dir / "sandbox_config.json"), str(output_dir / "CMakeLists.txt")],
        "next_steps": ["build_lvgl_regression_sandbox", "run_lvgl_regression_sandbox", "compare_lvgl_screenshot"],
    }


def _sandbox_config(sandbox_dir: Path) -> dict[str, Any]:
    path = sandbox_dir / "sandbox_config.json"
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return dict(REGRESSION_SANDBOX_CONFIG)


def build_lvgl_regression_sandbox(args: dict[str, Any]) -> dict[str, Any]:
    sandbox_dir = resolve_path(args.get("sandbox_dir"))
    if not (sandbox_dir / "CMakeLists.txt").is_file():
        raise ValueError(f"not a regression sandbox: {sandbox_dir}")
    build_dir = resolve_path(args.get("build_dir", sandbox_dir / "build"))
    build_dir.mkdir(parents=True, exist_ok=True)
    cmake = str(args.get("cmake") or _tool_available("cmake") or "")
    if not cmake:
        return {"ok": True, "available": False, "status": "not_available", "message": "cmake not found", "artifacts": []}

    config = _sandbox_config(sandbox_dir)
    lvgl_root = str(args.get("lvgl_root") or config.get("lvgl_root") or os.environ.get("LVGL_ROOT") or "")
    sdl2_root = str(args.get("sdl2_root") or config.get("sdl2_root") or os.environ.get("SDL2_ROOT") or "")
    sdl2_dir = str(args.get("sdl2_dir") or config.get("sdl2_dir") or os.environ.get("SDL2_DIR") or "")
    ui_under_test_dir = str(args.get("ui_under_test_dir") or config.get("ui_under_test_dir") or "")
    width = int(args.get("width", config.get("width", DISPLAY_CONFIG["display"]["width"])))
    height = int(args.get("height", config.get("height", DISPLAY_CONFIG["display"]["height"])))
    generator = str(args.get("generator", ""))
    toolchain_bin = str(args.get("toolchain_bin") or os.environ.get("MINGW_BIN") or "")
    if not generator and _tool_available("ninja"):
        generator = "Ninja"
    if not generator and toolchain_bin and (Path(toolchain_bin) / "mingw32-make.exe").is_file():
        generator = "MinGW Makefiles"
    timeout = int(args.get("timeout_seconds", 120))
    parallel = int(args.get("parallel", os.environ.get("LVGL_RENDER_PARALLEL", "4")))

    configure = [cmake, "-S", str(sandbox_dir), "-B", str(build_dir), f"-DREGRESSION_WIDTH={width}", f"-DREGRESSION_HEIGHT={height}"]
    if generator:
        configure.extend(["-G", generator])
    if lvgl_root:
        configure.append(f"-DLVGL_ROOT={lvgl_root}")
    if sdl2_root:
        configure.append(f"-DSDL2_ROOT={sdl2_root}")
    if sdl2_dir:
        configure.append(f"-DSDL2_DIR={sdl2_dir}")
    if ui_under_test_dir:
        configure.append(f"-DUI_UNDER_TEST_DIR={ui_under_test_dir}")
    configured = _run_process(configure, cwd=sandbox_dir, timeout=timeout, path_prefix=toolchain_bin)
    if configured["exit_code"] != 0:
        return {"ok": False, "available": True, "status": "configure_failed", "configure": configured, "artifacts": [str(build_dir)]}

    build_cmd = [cmake, "--build", str(build_dir), "--config", str(args.get("build_type", "Debug"))]
    if parallel > 1:
        build_cmd.extend(["--parallel", str(parallel)])
    built = _run_process(build_cmd, cwd=sandbox_dir, timeout=timeout, path_prefix=toolchain_bin)
    status = "built" if built["exit_code"] == 0 else ("timeout" if built.get("timeout") else "build_failed")
    return {
        "ok": built["exit_code"] == 0,
        "available": True,
        "status": status,
        "configure": configured,
        "build": built,
        "artifacts": [str(build_dir)],
    }


def _guess_executable(sandbox_dir: Path, build_dir: Path) -> Path | None:
    names = ["lvgl_regression_sandbox.exe", "lvgl_regression_sandbox"]
    roots = [build_dir, build_dir / "Debug", build_dir / "Release", sandbox_dir / "bin"]
    for root in roots:
        for name in names:
            candidate = root / name
            if candidate.is_file():
                return candidate
    matches = list(build_dir.rglob("lvgl_regression_sandbox.exe")) + list(build_dir.rglob("lvgl_regression_sandbox"))
    return matches[0] if matches else None


def _scan_log(text: str, patterns: list[str]) -> list[str]:
    lower = text.lower()
    return [pattern for pattern in patterns if pattern.lower() in lower]


def run_lvgl_regression_sandbox(args: dict[str, Any]) -> dict[str, Any]:
    sandbox_dir = resolve_path(args.get("sandbox_dir"))
    build_dir = resolve_path(args.get("build_dir", sandbox_dir / "build"))
    executable = Path(str(args.get("executable"))) if args.get("executable") else _guess_executable(sandbox_dir, build_dir)
    if executable is None or not executable.is_file():
        return {"ok": True, "available": False, "status": "not_available", "message": "sandbox executable not found", "artifacts": []}

    output_dir = resolve_path(args.get("output_dir", sandbox_dir / "regression_out"))
    output_dir.mkdir(parents=True, exist_ok=True)
    timeout = int(args.get("timeout_seconds", REGRESSION_SANDBOX_CONFIG["timeout_seconds"]))
    run = _run_process([str(executable)], cwd=sandbox_dir, timeout=timeout)
    log_path = output_dir / "run.log"
    log_text = run.get("stdout", "") + "\n" + run.get("stderr", "")
    log_path.write_text(log_text, encoding="utf-8", newline="\n")

    artifacts = [str(log_path)]
    produced_dir = build_dir / "regression"
    if produced_dir.is_dir():
        import shutil

        for pattern in ("*.ppm", "*.bmp", "*.png", "*.json"):
            for produced in produced_dir.glob(pattern):
                target = output_dir / produced.name
                shutil.copy2(produced, target)
                artifacts.append(str(target))

    issues = _scan_log(log_text, list(REGRESSION_SANDBOX_CONFIG["log_error_patterns"]))
    return {
        "ok": run["exit_code"] == 0 and not issues,
        "available": True,
        "status": "passed" if run["exit_code"] == 0 and not issues else "failed",
        "run": run,
        "log_issues": issues,
        "artifacts": sorted(set(artifacts)),
    }


def _hash_bytes(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()


def compare_lvgl_screenshot(args: dict[str, Any]) -> dict[str, Any]:
    actual = resolve_path(args.get("actual_path"))
    baseline = resolve_path(args.get("baseline_path"))
    if not actual.is_file():
        raise ValueError(f"actual_path does not exist: {actual}")
    if not baseline.is_file():
        raise ValueError(f"baseline_path does not exist: {baseline}")
    max_changed_ratio = float(args.get("max_changed_ratio", REGRESSION_SANDBOX_CONFIG["pixel_threshold"]["max_changed_ratio"]))
    max_channel_delta = int(args.get("max_channel_delta", REGRESSION_SANDBOX_CONFIG["pixel_threshold"]["max_channel_delta"]))

    aw, ah, ap = read_image(actual)
    bw, bh, bp = read_image(baseline)
    if (aw, ah) != (bw, bh):
        return {
            "ok": False,
            "status": "dimension_mismatch",
            "actual": {"path": str(actual), "width": aw, "height": ah, "sha256": _hash_bytes(actual.read_bytes())},
            "baseline": {"path": str(baseline), "width": bw, "height": bh, "sha256": _hash_bytes(baseline.read_bytes())},
        }

    changed = 0
    max_delta = 0
    for a, b in zip(ap, bp):
        delta = max(abs(a[0] - b[0]), abs(a[1] - b[1]), abs(a[2] - b[2]))
        max_delta = max(max_delta, delta)
        if delta > max_channel_delta:
            changed += 1
    total = max(1, len(ap))
    changed_ratio = changed / total
    ok = changed_ratio <= max_changed_ratio
    return {
        "ok": ok,
        "status": "passed" if ok else "pixel_diff_failed",
        "width": aw,
        "height": ah,
        "changed_pixels": changed,
        "total_pixels": total,
        "changed_ratio": changed_ratio,
        "max_channel_delta": max_delta,
        "threshold": {"max_changed_ratio": max_changed_ratio, "max_channel_delta": max_channel_delta},
        "actual_sha256": _hash_bytes(actual.read_bytes()),
        "baseline_sha256": _hash_bytes(baseline.read_bytes()),
        "artifacts": [str(actual), str(baseline)],
    }


def list_lvgl_regression_artifacts(args: dict[str, Any]) -> dict[str, Any]:
    sandbox_dir = resolve_path(args.get("sandbox_dir"))
    patterns = ["*.ppm", "*.bmp", "*.png", "*.log", "*.json"]
    files: list[str] = []
    for pattern in patterns:
        files.extend(str(path) for path in sandbox_dir.rglob(pattern) if path.is_file())
    return {"ok": True, "sandbox_dir": str(sandbox_dir), "artifacts": sorted(set(files))}


def _first_artifact(artifacts: list[str], suffixes: tuple[str, ...], *, prefer: str = "") -> Path | None:
    paths = [Path(item) for item in artifacts if str(item).lower().endswith(suffixes)]
    if prefer:
        for path in paths:
            if path.name.lower() == prefer.lower():
                return path
    return paths[0] if paths else None


def _copy_image_for_probe(source: Path, output_dir: Path) -> Path:
    import shutil

    target = output_dir / f"screen{source.suffix.lower() or '.ppm'}"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return target


def _default_object_tree(width: int, height: int, screenshot_path: Path, *, source: str, available: bool = False) -> dict[str, Any]:
    return {
        "schema": "freertos-embedded-architect.lvgl.object-tree.v1",
        "source": source,
        "screenshot": str(screenshot_path),
        "display": {"width": width, "height": height},
        "introspection": {
            "available": available,
            "note": "C-side object_tree.json was not produced; this fallback only preserves screen bounds.",
        },
        "tree": {"type": "screen", "x": 0, "y": 0, "w": width, "h": height, "children": []},
    }


def _write_snippet_source(args: dict[str, Any], output_dir: Path) -> tuple[Path, str, str] | None:
    c_code = args.get("c_code")
    if not c_code:
        return None
    entry = safe_symbol(str(args.get("ui_entry_function") or "ui_snippet_create"))
    header = str(args.get("ui_header") or "ui_snippet.h")
    snippet_dir = output_dir / "snippet"
    snippet_dir.mkdir(parents=True, exist_ok=True)
    header_text = str(args.get("c_header") or textwrap.dedent(
        f"""\
        #ifndef UI_SNIPPET_H
        #define UI_SNIPPET_H

        #include "lvgl.h"

        lv_obj_t *{entry}(lv_obj_t *parent);

        #endif /* UI_SNIPPET_H */
        """
    ))
    (snippet_dir / header).write_text(header_text, encoding="utf-8", newline="\n")
    source = str(c_code)
    if "lvgl.h" not in source:
        source = f'#include "lvgl.h"\n#include "{header}"\n\n' + source
    (snippet_dir / "ui_snippet.c").write_text(source, encoding="utf-8", newline="\n")
    return snippet_dir, entry, header


def _load_or_create_object_tree(artifacts: list[str], screenshot_path: Path, output_dir: Path, *, source: str) -> Path:
    existing = _first_artifact(artifacts, (".json",), prefer="object_tree.json")
    target = output_dir / "object_tree.json"
    if existing is not None and existing.is_file():
        if existing.resolve() != target.resolve():
            target.write_bytes(existing.read_bytes())
        return target
    width, height, _ = read_image(screenshot_path)
    _write_json(target, _default_object_tree(width, height, screenshot_path, source=source))
    return target


def _summarize_tree(tree: dict[str, Any]) -> dict[str, Any]:
    from collections import Counter

    nodes: list[dict[str, Any]] = []

    def walk(node: Any) -> None:
        if not isinstance(node, dict):
            return
        nodes.append(node)
        for child in node.get("children", []) or []:
            walk(child)

    walk(tree.get("tree"))
    types = Counter(str(node.get("type", "unknown")) for node in nodes)
    texts = sorted(str(node.get("text")) for node in nodes if node.get("text") not in (None, ""))
    return {"node_count": len(nodes), "types": dict(sorted(types.items())), "texts": texts}


def compare_lvgl_object_tree(args: dict[str, Any]) -> dict[str, Any]:
    actual = resolve_path(args.get("actual_path"))
    baseline = resolve_path(args.get("baseline_path"))
    if not actual.is_file():
        raise ValueError(f"actual_path does not exist: {actual}")
    if not baseline.is_file():
        raise ValueError(f"baseline_path does not exist: {baseline}")
    actual_tree = json.loads(actual.read_text(encoding="utf-8"))
    baseline_tree = json.loads(baseline.read_text(encoding="utf-8"))
    actual_summary = _summarize_tree(actual_tree)
    baseline_summary = _summarize_tree(baseline_tree)
    diffs: list[str] = []
    if actual_summary["node_count"] != baseline_summary["node_count"]:
        diffs.append("node_count")
    if actual_summary["types"] != baseline_summary["types"]:
        diffs.append("types")
    if actual_summary["texts"] != baseline_summary["texts"]:
        diffs.append("texts")
    return {
        "ok": not diffs,
        "status": "passed" if not diffs else "structure_diff_failed",
        "diffs": diffs,
        "actual": actual_summary,
        "baseline": baseline_summary,
        "artifacts": [str(actual), str(baseline)],
    }


def lvgl_render(args: dict[str, Any]) -> dict[str, Any]:
    output_dir = resolve_path(args.get("output_dir", ROOT / "artifacts" / "lvgl_render"))
    output_dir.mkdir(parents=True, exist_ok=True)
    mode = str(args.get("render_mode", "auto"))
    require_choice("render_mode", mode, {"auto", "probe"})

    diagnostics_path = output_dir / "diagnostics.json"
    png_path = output_dir / "render.png"
    object_tree_path = output_dir / "object_tree.json"

    if mode == "probe":
        probe_source = resolve_path(args.get("probe_image_path", sandbox_template_dir() / "baselines" / "probe.ppm"))
        screenshot_path = _copy_image_for_probe(probe_source, output_dir)
        png_meta = convert_image_to_png(screenshot_path, png_path)
        width, height, _ = read_image(screenshot_path)
        _write_json(object_tree_path, _default_object_tree(width, height, screenshot_path, source="probe", available=False))
        diagnostics = {"ok": True, "available": True, "status": "probe", "log_issues": [], "mode": mode}
        _write_json(diagnostics_path, diagnostics)
        return {
            "ok": True,
            "available": True,
            "status": "probe",
            "screenshot_path": str(screenshot_path),
            "png_path": str(png_path),
            "png": png_meta,
            "object_tree_path": str(object_tree_path),
            "diagnostics_path": str(diagnostics_path),
            "artifacts": [str(screenshot_path), str(png_path), str(object_tree_path), str(diagnostics_path)],
        }

    snippet = _write_snippet_source(args, output_dir)
    render_args = dict(args)
    sandbox_dir = resolve_path(args.get("sandbox_dir", output_dir / "sandbox"))
    render_args["output_dir"] = str(sandbox_dir)
    if snippet is not None:
        snippet_dir, entry, header = snippet
        render_args["ui_under_test_dir"] = str(snippet_dir)
        render_args["ui_entry_function"] = entry
        render_args["ui_header"] = header

    prepared = prepare_lvgl_regression_sandbox(render_args)
    sandbox_path = Path(prepared["sandbox_dir"])
    build_dir = resolve_path(args.get("build_dir", sandbox_path / "build"))
    built = build_lvgl_regression_sandbox({**args, "sandbox_dir": str(sandbox_path), "build_dir": str(build_dir)})
    diagnostics: dict[str, Any] = {"mode": mode, "prepare": prepared, "build": built, "log_issues": []}
    if not built.get("ok"):
        diagnostics.update({"ok": False, "available": built.get("available", True), "status": built.get("status", "build_failed")})
        _write_json(diagnostics_path, diagnostics)
        return {"ok": False, "available": built.get("available", True), "status": "build_failed", "stage": "build", "diagnostics_path": str(diagnostics_path), "prepare": prepared, "build": built, "artifacts": prepared.get("artifacts", []) + built.get("artifacts", []) + [str(diagnostics_path)]}
    if built.get("available") is False:
        diagnostics.update({"ok": True, "available": False, "status": "not_available"})
        _write_json(diagnostics_path, diagnostics)
        return {"ok": True, "available": False, "status": "not_available", "stage": "build", "diagnostics_path": str(diagnostics_path), "prepare": prepared, "build": built, "artifacts": prepared.get("artifacts", []) + [str(diagnostics_path)]}

    ran = run_lvgl_regression_sandbox({**args, "sandbox_dir": str(sandbox_path), "build_dir": str(build_dir), "output_dir": str(output_dir / "run")})
    artifacts = list(prepared.get("artifacts", [])) + list(built.get("artifacts", [])) + list(ran.get("artifacts", []))
    screenshot = _first_artifact(list(ran.get("artifacts", [])), (".ppm", ".bmp", ".png"), prefer="screen.ppm")
    diagnostics.update({"run": ran, "log_issues": ran.get("log_issues", [])})
    if screenshot is None or not screenshot.is_file():
        diagnostics.update({"ok": False, "available": True, "status": "screenshot_missing"})
        _write_json(diagnostics_path, diagnostics)
        return {"ok": False, "available": True, "status": "screenshot_missing", "stage": "run", "diagnostics_path": str(diagnostics_path), "prepare": prepared, "build": built, "run": ran, "artifacts": artifacts + [str(diagnostics_path)]}

    png_meta = convert_image_to_png(screenshot, png_path)
    object_tree_path = _load_or_create_object_tree(list(ran.get("artifacts", [])), screenshot, output_dir, source="sandbox")
    diagnostics.update({"ok": bool(ran.get("ok")), "available": True, "status": ran.get("status", "failed"), "screenshot_path": str(screenshot), "png_path": str(png_path), "object_tree_path": str(object_tree_path)})
    _write_json(diagnostics_path, diagnostics)
    return {
        "ok": bool(ran.get("ok")),
        "available": True,
        "status": "passed" if ran.get("ok") else "failed",
        "stage": "complete",
        "screenshot_path": str(screenshot),
        "png_path": str(png_path),
        "png": png_meta,
        "object_tree_path": str(object_tree_path),
        "diagnostics_path": str(diagnostics_path),
        "prepare": prepared,
        "build": built,
        "run": ran,
        "artifacts": sorted(set(artifacts + [str(screenshot), str(png_path), str(object_tree_path), str(diagnostics_path)])),
    }


def run_lvgl_ui_regression(args: dict[str, Any]) -> dict[str, Any]:
    rendered = lvgl_render(args)
    if rendered.get("available") is False:
        return {"ok": True, "available": False, "stage": "render", "render": rendered, "artifacts": rendered.get("artifacts", [])}
    if not rendered.get("ok"):
        return {"ok": False, "available": True, "stage": "render", "render": rendered, "artifacts": rendered.get("artifacts", [])}

    comparison: dict[str, Any] | None = None
    baseline = args.get("baseline_path")
    actual_screenshot = rendered.get("screenshot_path")
    if baseline and actual_screenshot:
        comparison = compare_lvgl_screenshot({**args, "actual_path": str(actual_screenshot), "baseline_path": str(baseline)})

    structure: dict[str, Any] | None = None
    baseline_tree = args.get("baseline_object_tree_path")
    actual_tree = rendered.get("object_tree_path")
    if baseline_tree and actual_tree:
        structure = compare_lvgl_object_tree({"actual_path": str(actual_tree), "baseline_path": str(baseline_tree)})

    log_issues = []
    diagnostics_path = rendered.get("diagnostics_path")
    if diagnostics_path and Path(str(diagnostics_path)).is_file():
        diagnostics = json.loads(Path(str(diagnostics_path)).read_text(encoding="utf-8"))
        log_issues = diagnostics.get("log_issues", []) or []

    ok = bool(rendered.get("ok")) and (comparison is None or bool(comparison.get("ok"))) and (structure is None or bool(structure.get("ok"))) and not log_issues
    return {
        "ok": ok,
        "available": True,
        "stage": "complete",
        "render": rendered,
        "comparison": comparison,
        "structure": structure,
        "log_issues": log_issues,
        "artifacts": rendered.get("artifacts", []),
    }


LVGL_TOOLS = {
    "get_lvgl_theme_skill": get_lvgl_theme_skill,
    "convert_image_to_lvgl_source": convert_image_to_lvgl_source,
    "generate_lvgl_layout_spec": generate_lvgl_layout_spec,
    "generate_lvgl_page_code": generate_lvgl_page_code,
    "validate_lvgl_layout_code": validate_lvgl_layout_code,
    "prepare_lvgl_sim_project": prepare_lvgl_sim_project,
    "prepare_lvgl_regression_sandbox": prepare_lvgl_regression_sandbox,
    "build_lvgl_regression_sandbox": build_lvgl_regression_sandbox,
    "run_lvgl_regression_sandbox": run_lvgl_regression_sandbox,
    "compare_lvgl_screenshot": compare_lvgl_screenshot,
    "compare_lvgl_object_tree": compare_lvgl_object_tree,
    "lvgl_render": lvgl_render,
    "run_lvgl_ui_regression": run_lvgl_ui_regression,
    "list_lvgl_regression_artifacts": list_lvgl_regression_artifacts,
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
    {
        "name": "prepare_lvgl_regression_sandbox",
        "description": "Copy the LVGL UI rendering/regression sandbox template into an isolated work directory.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "output_dir": {"type": "string", "default": "artifacts/lvgl_regression_sandbox"},
                "width": {"type": "integer", "default": 480},
                "height": {"type": "integer", "default": 800},
                "lvgl_root": {"type": "string"},
                "sdl2_root": {"type": "string"},
                "sdl2_dir": {"type": "string"},
                "ui_under_test_dir": {"type": "string"},
                "ui_entry_function": {"type": "string"},
                "ui_header": {"type": "string"},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "build_lvgl_regression_sandbox",
        "description": "Configure and build a prepared LVGL regression sandbox with CMake.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "sandbox_dir": {"type": "string"},
                "build_dir": {"type": "string"},
                "lvgl_root": {"type": "string"},
                "sdl2_root": {"type": "string"},
                "sdl2_dir": {"type": "string"},
                "ui_under_test_dir": {"type": "string"},
                "generator": {"type": "string"},
                "toolchain_bin": {"type": "string"},
                "build_type": {"type": "string", "default": "Debug"},
                "timeout_seconds": {"type": "integer", "default": 120},
                "parallel": {"type": "integer", "default": 4},
            },
            "required": ["sandbox_dir"],
            "additionalProperties": False,
        },
    },
    {
        "name": "run_lvgl_regression_sandbox",
        "description": "Run a built LVGL regression sandbox executable and scan runtime logs.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "sandbox_dir": {"type": "string"},
                "build_dir": {"type": "string"},
                "executable": {"type": "string"},
                "output_dir": {"type": "string"},
                "timeout_seconds": {"type": "integer", "default": 20},
            },
            "required": ["sandbox_dir"],
            "additionalProperties": False,
        },
    },
    {
        "name": "compare_lvgl_screenshot",
        "description": "Compare actual and baseline LVGL screenshots using pixel thresholds.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "actual_path": {"type": "string"},
                "baseline_path": {"type": "string"},
                "max_changed_ratio": {"type": "number", "default": 0.01},
                "max_channel_delta": {"type": "integer", "default": 8},
            },
            "required": ["actual_path", "baseline_path"],
            "additionalProperties": False,
        },
    },
    {
        "name": "compare_lvgl_object_tree",
        "description": "Compare actual and baseline LVGL object-tree JSON by node count, widget types, and label text.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "actual_path": {"type": "string"},
                "baseline_path": {"type": "string"},
            },
            "required": ["actual_path", "baseline_path"],
            "additionalProperties": False,
        },
    },
    {
        "name": "lvgl_render",
        "description": "Render one LVGL C snippet or UI entry through the local sandbox and return PNG screenshot plus object-tree JSON.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "c_code": {"type": "string"},
                "c_header": {"type": "string"},
                "output_dir": {"type": "string", "default": "artifacts/lvgl_render"},
                "render_mode": {"type": "string", "enum": ["auto", "probe"], "default": "auto"},
                "width": {"type": "integer", "default": 480},
                "height": {"type": "integer", "default": 800},
                "lvgl_root": {"type": "string"},
                "sdl2_root": {"type": "string"},
                "sdl2_dir": {"type": "string"},
                "ui_under_test_dir": {"type": "string"},
                "ui_entry_function": {"type": "string", "default": "ui_snippet_create"},
                "ui_header": {"type": "string", "default": "ui_snippet.h"},
                "toolchain_bin": {"type": "string"},
                "generator": {"type": "string"},
                "build_dir": {"type": "string"},
                "timeout_seconds": {"type": "integer", "default": 120},
                "parallel": {"type": "integer", "default": 4},
            },
            "additionalProperties": True,
        },
    },
    {
        "name": "run_lvgl_ui_regression",
        "description": "Call lvgl_render, then compare screenshot pixels, optional object-tree JSON, and runtime log issues against baselines.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "output_dir": {"type": "string"},
                "baseline_path": {"type": "string"},
                "baseline_object_tree_path": {"type": "string"},
                "c_code": {"type": "string"},
                "render_mode": {"type": "string", "enum": ["auto", "probe"], "default": "auto"},
                "lvgl_root": {"type": "string"},
                "sdl2_root": {"type": "string"},
                "sdl2_dir": {"type": "string"},
                "ui_under_test_dir": {"type": "string"},
                "toolchain_bin": {"type": "string"},
                "timeout_seconds": {"type": "integer", "default": 120},
                "parallel": {"type": "integer", "default": 4},
            },
            "additionalProperties": True,
        },
    },
    {
        "name": "list_lvgl_regression_artifacts",
        "description": "List screenshots, logs, JSON files, and other regression artifacts in a sandbox.",
        "inputSchema": {
            "type": "object",
            "properties": {"sandbox_dir": {"type": "string"}},
            "required": ["sandbox_dir"],
            "additionalProperties": False,
        },
    },

]
