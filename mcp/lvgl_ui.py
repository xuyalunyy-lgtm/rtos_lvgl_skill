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

ROOT = Path(__file__).resolve().parent.parent
LVGL_VERSIONS = {"v8", "v9"}
IMAGE_FORMATS = {"c_array", "binary", "both"}
COLOR_FORMATS = {"RGB565"}
DEFAULT_FONT_CANDIDATES = [
    Path(os.environ.get("LVGL_PLACEHOLDER_TTF", "")),
    Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "simhei.ttf",
    Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "msyh.ttc",
    Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "simsun.ttc",
    Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "arial.ttf",
]
ASSET_INPUT_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".ppm", ".pnm"}
INITIAL_LOADING_DESIGN_FILE = "initial_loading.png"
INITIAL_LOADING_BACKGROUND_FILE = "background1.jpg"
INITIAL_LOADING_PET_FILE = "pet.png"

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
    "default_cache_dir": "artifacts/lvgl_render_cache",
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
belong in caller work directories. `lvgl_render` reuses `cache_dir` for the
prepared sandbox, snippet source, and CMake build cache by default.
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
- Each generated page root should reserve a custom-event listener for server
  updates and unknown project events. Network/MQTT/HTTP threads should post
  through the generated async helper instead of calling LVGL APIs directly.

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



def c_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


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



def read_image_with_system_drawing(path: Path) -> tuple[int, int, list[tuple[int, int, int]]]:
    """Read PNG/JPEG/BMP through Windows System.Drawing when Pillow is unavailable."""
    path = path.resolve()
    with tempfile.TemporaryDirectory(prefix="lvgl_img_") as tmp:
        raw_path = Path(tmp) / "pixels.rgb"
        script = textwrap.dedent(
            f"""
            Add-Type -AssemblyName System.Drawing
            $src = {json.dumps(str(path), ensure_ascii=False)}
            $raw = {json.dumps(str(raw_path), ensure_ascii=False)}
            $img = [System.Drawing.Bitmap]::FromFile($src)
            try {{
                $bytes = New-Object byte[] ($img.Width * $img.Height * 3)
                $idx = 0
                for ($y = 0; $y -lt $img.Height; $y++) {{
                    for ($x = 0; $x -lt $img.Width; $x++) {{
                        $p = $img.GetPixel($x, $y)
                        $bytes[$idx] = $p.R; $idx++
                        $bytes[$idx] = $p.G; $idx++
                        $bytes[$idx] = $p.B; $idx++
                    }}
                }}
                [System.IO.File]::WriteAllBytes($raw, $bytes)
                @{{width=$img.Width; height=$img.Height}} | ConvertTo-Json -Compress
            }} finally {{
                if ($null -ne $img) {{ $img.Dispose() }}
            }}
            """
        )
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
        if proc.returncode != 0:
            raise ValueError(f"System.Drawing image conversion failed: {proc.stderr.strip() or proc.stdout.strip()}")
        meta = json.loads(proc.stdout.strip().splitlines()[-1])
        raw = raw_path.read_bytes()
        width = int(meta["width"])
        height = int(meta["height"])
        expected = width * height * 3
        if len(raw) != expected:
            raise ValueError(f"System.Drawing returned {len(raw)} bytes, expected {expected}")
        pixels = [(raw[i], raw[i + 1], raw[i + 2]) for i in range(0, len(raw), 3)]
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
        try:
            return read_image_with_system_drawing(path)
        except Exception as fallback_exc:
            raise ValueError(f"{suffix or 'image'} conversion requires Pillow or Windows System.Drawing fallback: {fallback_exc}") from fallback_exc
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

                #ifndef {asset_macro_for(symbol)}
                #define {asset_macro_for(symbol)} (&{symbol})
                #endif

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
                /* LVGL_LAYOUT_EXCEPTION: full-screen pixel-matched background from design screenshot. */
                lv_obj_set_pos(bg, 0, 0);
                lv_obj_set_size(bg, UI_INITIAL_LOADING_WIDTH, UI_INITIAL_LOADING_HEIGHT);

                lv_obj_t *pet = {image_create}(s_page);
                {image_set_src}(pet, {pet_src_macro});
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
    target_path = resolve_path(args.get("target_path")) if args.get("target_path") else None
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
    apply_changes = bool(args.get("apply", False))
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
        patch_path = resolve_path(args["patch_path"])
        patch_path.parent.mkdir(parents=True, exist_ok=True)
        patch_path.write_text(diff + "\n", encoding="utf-8", newline="\n")
    if apply_changes:
        if target_path is None:
            raise ValueError("apply=true requires target_path")
        target_path.write_text(patched_text, encoding="utf-8", newline="\n")
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


def collect_asset_paths(args: dict[str, Any]) -> list[Path]:
    paths: list[Path] = []
    for item in args.get("input_paths") or []:
        path = resolve_path(item)
        if path.is_file():
            paths.append(path)
    if args.get("source_dir"):
        source_dir = resolve_path(args["source_dir"])
        recursive = bool(args.get("recursive", True))
        iterator = source_dir.rglob("*") if recursive else source_dir.glob("*")
        for path in iterator:
            if path.is_file() and path.suffix.lower() in ASSET_INPUT_EXTENSIONS:
                paths.append(path)
    unique: dict[str, Path] = {}
    for path in paths:
        unique[str(path.resolve())] = path.resolve()
    return sorted(unique.values(), key=lambda item: str(item).lower())


def command_from_template(template: Any, values: dict[str, str]) -> list[str]:
    if isinstance(template, str):
        parts = shlex.split(template, posix=False)
    elif isinstance(template, list):
        parts = [str(item) for item in template]
    else:
        raise ValueError("converter_command/converter_args_template must be string or list")
    return [part.format(**values) for part in parts]


def default_asset_symbol(path: Path, prefix: str) -> str:
    stem = safe_symbol(path.stem)
    if stem.endswith("_map"):
        return stem
    return f"{safe_symbol(prefix)}_{stem}_map"


def write_asset_registry(output_dir: Path, assets: list[dict[str, Any]], *, lvgl_version: str) -> list[str]:
    descriptor_type = "lv_image_dsc_t" if lvgl_version == "v9" else "lv_img_dsc_t"
    h_path = output_dir / "ui_assets.h"
    c_path = output_dir / "ui_assets.c"
    cmake_path = output_dir / "ui_assets_sources.cmake"
    guard = "UI_ASSETS_H"
    externs = "\n".join(f"extern const {descriptor_type} {item['symbol']};" for item in assets if item.get("ok"))
    asset_macros = "\n\n".join(
        f"#ifndef {asset_macro_for(str(item['symbol']))}\n#define {asset_macro_for(str(item['symbol']))} (&{item['symbol']})\n#endif"
        for item in assets
        if item.get("ok")
    )
    entries = "\n".join(f"    {{\"{item['name']}\", &{item['symbol']}}}," for item in assets if item.get("ok"))
    sources = [Path(path) for item in assets for path in item.get("artifacts", []) if str(path).endswith(".c") and Path(path).name != "ui_assets.c"]
    rel_sources = "\n".join(f"    ${{CMAKE_CURRENT_LIST_DIR}}/{source.name}" for source in sources)
    h_path.write_text(
        textwrap.dedent(
            f"""\
            #ifndef {guard}
            #define {guard}

            #include "lvgl.h"
            #include <stddef.h>

            {externs}

            {asset_macros}

            typedef struct {{
                const char *name;
                const {descriptor_type} *image;
            }} ui_asset_entry_t;

            extern const ui_asset_entry_t ui_asset_registry[];
            extern const size_t ui_asset_registry_count;

            #endif /* {guard} */
            """
        ),
        encoding="utf-8",
        newline="\n",
    )
    c_path.write_text(
        textwrap.dedent(
            f"""\
            #include "ui_assets.h"

            const ui_asset_entry_t ui_asset_registry[] = {{
            {entries}
            }};

            const size_t ui_asset_registry_count = sizeof(ui_asset_registry) / sizeof(ui_asset_registry[0]);
            """
        ),
        encoding="utf-8",
        newline="\n",
    )
    cmake_path.write_text(
        "set(UI_ASSET_SOURCES\n" + rel_sources + "\n    ${CMAKE_CURRENT_LIST_DIR}/ui_assets.c\n)\n",
        encoding="utf-8",
        newline="\n",
    )
    return [str(h_path), str(c_path), str(cmake_path)]


def convert_assets_to_lvgl(args: dict[str, Any]) -> dict[str, Any]:
    output_dir = resolve_path(args.get("output_dir", ROOT / "artifacts" / "lvgl_assets"))
    output_dir.mkdir(parents=True, exist_ok=True)
    project_config = args.get("project_config") or {}
    if not isinstance(project_config, dict):
        raise ValueError("project_config must be an object")
    lvgl_version = str(args.get("lvgl_version", project_config.get("lvgl_version", DISPLAY_CONFIG["lvgl"]["version"])))
    require_choice("lvgl_version", lvgl_version, LVGL_VERSIONS)
    color_format = str(args.get("color_format", project_config.get("color_format", "RGB565"))).upper()
    asset_prefix = str(args.get("asset_prefix", project_config.get("asset_prefix", "ui_img")))
    output_format = str(args.get("format", "c_array"))
    require_choice("format", output_format, IMAGE_FORMATS)
    paths = collect_asset_paths(args)
    if not paths:
        raise ValueError("no input assets found")

    converter_template = args.get("converter_command") or args.get("converter_args_template")
    converter_path = str(args.get("converter_path") or os.environ.get("LVGL_IMAGE_CONVERTER", "")).strip()
    strict_converter = bool(args.get("strict_converter", False))
    converted: list[dict[str, Any]] = []
    for asset in paths:
        symbol = default_asset_symbol(asset, asset_prefix)
        name = safe_symbol(asset.stem)
        values = {
            "input": str(asset),
            "output_dir": str(output_dir),
            "output": str(output_dir / f"{symbol}.c"),
            "name": name,
            "symbol": symbol,
            "color_format": color_format,
            "lvgl_version": lvgl_version,
        }
        result: dict[str, Any] = {"name": name, "symbol": symbol, "input": str(asset), "ok": False, "artifacts": []}
        if converter_template or converter_path:
            if converter_template:
                cmd = command_from_template(converter_template, values)
            else:
                cmd = [converter_path, "{input}", "--output", "{output}", "--name", "{symbol}", "--cf", "{color_format}"]
                cmd = [part.format(**values) for part in cmd]
            proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, encoding="utf-8", errors="replace", timeout=int(args.get("timeout_seconds", 120)))
            result.update({"converter": cmd, "stdout": proc.stdout, "stderr": proc.stderr, "exit_code": proc.returncode})
            result["ok"] = proc.returncode == 0
            if result["ok"]:
                result["artifacts"] = [str(path) for path in output_dir.glob(f"{symbol}*")]
            elif strict_converter:
                converted.append(result)
                continue
        if not result["ok"]:
            if color_format != "RGB565":
                result["error"] = f"fallback converter supports RGB565 only, got {color_format}; provide converter_command for this format"
            else:
                try:
                    fallback = convert_image_to_lvgl_source({"input_path": str(asset), "output_dir": str(output_dir), "name": symbol, "format": output_format, "lvgl_version": lvgl_version})
                    result.update(fallback)
                    result["name"] = name
                    result["symbol"] = fallback.get("symbol", symbol)
                except Exception as exc:
                    result["error"] = str(exc)
        converted.append(result)
    registry_assets = [item for item in converted if item.get("ok")]
    registry_artifacts = write_asset_registry(output_dir, registry_assets, lvgl_version=lvgl_version) if registry_assets else []
    manifest_path = output_dir / "ui_assets_manifest.json"
    manifest = {"ok": all(bool(item.get("ok")) for item in converted), "assets": converted, "registry_artifacts": registry_artifacts}
    _write_json(manifest_path, manifest)
    return {**manifest, "artifacts": sorted(set(registry_artifacts + [str(manifest_path)] + [path for item in converted for path in item.get("artifacts", [])]))}


def default_font_path() -> Path | None:
    for candidate in DEFAULT_FONT_CANDIDATES:
        if str(candidate) and candidate.is_file():
            return candidate
    return None


def find_lv_font_conv(explicit: Any = None) -> str | None:
    if explicit:
        path = str(explicit)
        return path if Path(path).exists() else shutil.which(path)
    return shutil.which("lv_font_conv") or shutil.which("lv_font_conv.cmd")


def unique_glyph_text(text: str) -> str:
    glyphs = []
    seen: set[str] = set()
    for ch in text:
        if ch in seen or ch in {"\r", "\n", "\t"}:
            continue
        seen.add(ch)
        glyphs.append(ch)
    return "".join(glyphs)


def generate_font_glyph(args: dict[str, Any]) -> dict[str, Any]:
    output_dir = resolve_path(args.get("output_dir", ROOT / "artifacts" / "lvgl_fonts"))
    output_dir.mkdir(parents=True, exist_ok=True)
    layout = None
    texts: list[str] = []
    if args.get("layout_json") is not None or args.get("layout_path"):
        layout = load_json_like(args, "layout_json", "layout_path")
        texts.extend(walk_text_values(layout))
    if args.get("text"):
        texts.append(str(args["text"]))
    if args.get("text_path"):
        texts.append(resolve_path(args["text_path"]).read_text(encoding="utf-8"))
    text = "".join(texts)
    glyphs = unique_glyph_text(text)
    if not glyphs:
        glyphs = unique_glyph_text(str(args.get("fallback_text", "Loading...0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz")))
    size = int(args.get("size", 16))
    bpp = int(args.get("bpp", 4))
    font_name = safe_symbol(str(args.get("font_name", f"ui_font_design_{size}")))
    font_path = resolve_path(args["font_path"]) if args.get("font_path") else default_font_path()
    converter = find_lv_font_conv(args.get("converter_path"))
    c_path = output_dir / f"{font_name}.c"
    h_path = output_dir / f"{font_name}.h"
    manifest_path = output_dir / f"{font_name}_manifest.json"
    placeholder_h = output_dir / "ui_font_placeholder.h"
    placeholder_target = font_name if converter and font_path else f"lv_font_montserrat_{size}"
    placeholder_h.write_text(
        textwrap.dedent(
            f"""\
            #ifndef UI_FONT_PLACEHOLDER_H
            #define UI_FONT_PLACEHOLDER_H

            #include "lvgl.h"

            #ifndef UI_FONT_DESIGN_{size}
            #define UI_FONT_DESIGN_{size} {placeholder_target}
            #endif

            #endif /* UI_FONT_PLACEHOLDER_H */
            """
        ),
        encoding="utf-8",
        newline="\n",
    )
    h_path.write_text(
        textwrap.dedent(
            f"""\
            #ifndef {font_name.upper()}_H
            #define {font_name.upper()}_H

            #include "lvgl.h"

            extern const lv_font_t {font_name};

            #endif /* {font_name.upper()}_H */
            """
        ),
        encoding="utf-8",
        newline="\n",
    )
    cmd: list[str] = []
    run: dict[str, Any] | None = None
    ok = False
    if converter and font_path:
        cmd = [
            converter,
            "--font", str(font_path),
            "--symbols", glyphs,
            "--size", str(size),
            "--format", "lvgl",
            "--bpp", str(bpp),
            "--lv-font-name", font_name,
            "-o", str(c_path),
        ]
        cmd.extend(str(item) for item in args.get("extra_args", []))
        proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, encoding="utf-8", errors="replace", timeout=int(args.get("timeout_seconds", 120)))
        run = {"command": cmd, "exit_code": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}
        ok = proc.returncode == 0 and c_path.is_file()
    manifest = {
        "ok": ok,
        "font_name": font_name,
        "size": size,
        "bpp": bpp,
        "glyph_count": len(glyphs),
        "glyphs": glyphs,
        "font_path": str(font_path) if font_path else "",
        "converter": converter or "",
        "run": run,
        "placeholder_header": str(placeholder_h),
        "message": "font generated" if ok else "lv_font_conv or font_path unavailable/failed; placeholder macro header generated",
    }
    _write_json(manifest_path, manifest)
    artifacts = [str(h_path), str(placeholder_h), str(manifest_path)]
    if c_path.is_file():
        artifacts.insert(0, str(c_path))
    return {**manifest, "artifacts": artifacts}

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
    config["sdl2_bin"] = str(args.get("sdl2_bin", ""))
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
    ninja_bin = str(args.get("ninja_bin") or os.environ.get("NINJA_BIN") or "")
    c_compiler = str(args.get("c_compiler") or os.environ.get("CC") or "")
    cxx_compiler = str(args.get("cxx_compiler") or os.environ.get("CXX") or "")
    ninja_prefix = ""
    if ninja_bin:
        ninja_path = Path(ninja_bin)
        ninja_prefix = str(ninja_path.parent if ninja_path.name.lower() in {"ninja", "ninja.exe"} else ninja_path)
    ninja_available = bool(_tool_available("ninja") or (ninja_prefix and (Path(ninja_prefix) / "ninja.exe").is_file()))
    if not generator and ninja_available:
        generator = "Ninja"
    if not generator and toolchain_bin and (Path(toolchain_bin) / "mingw32-make.exe").is_file():
        generator = "MinGW Makefiles"
    timeout = int(args.get("timeout_seconds", 120))
    parallel = int(args.get("parallel", os.environ.get("LVGL_RENDER_PARALLEL", "4")))
    path_prefix = os.pathsep.join(part for part in (ninja_prefix, toolchain_bin) if part)

    configure = [cmake, "-S", str(sandbox_dir), "-B", str(build_dir), f"-DREGRESSION_WIDTH={width}", f"-DREGRESSION_HEIGHT={height}"]
    if generator:
        configure.extend(["-G", generator])
    if c_compiler:
        configure.append(f"-DCMAKE_C_COMPILER={c_compiler}")
    if cxx_compiler:
        configure.append(f"-DCMAKE_CXX_COMPILER={cxx_compiler}")
    if lvgl_root:
        configure.append(f"-DLVGL_ROOT={lvgl_root}")
    if sdl2_root:
        configure.append(f"-DSDL2_ROOT={sdl2_root}")
    if sdl2_dir:
        configure.append(f"-DSDL2_DIR={sdl2_dir}")
    configure.append(f"-DUI_UNDER_TEST_DIR={ui_under_test_dir}")
    configured = _run_process(configure, cwd=sandbox_dir, timeout=timeout, path_prefix=path_prefix)
    if configured["exit_code"] != 0:
        return {"ok": False, "available": True, "status": "configure_failed", "configure": configured, "artifacts": [str(build_dir)]}

    build_cmd = [cmake, "--build", str(build_dir), "--config", str(args.get("build_type", "Debug"))]
    if parallel > 1:
        build_cmd.extend(["--parallel", str(parallel)])
    built = _run_process(build_cmd, cwd=sandbox_dir, timeout=timeout, path_prefix=path_prefix)
    status = "built" if built["exit_code"] == 0 else ("timeout" if built.get("timeout") else "build_failed")
    return {
        "ok": built["exit_code"] == 0,
        "available": True,
        "status": status,
        "generator": generator,
        "path_prefix": path_prefix,
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
    config = _sandbox_config(sandbox_dir)
    toolchain_bin = str(args.get("toolchain_bin") or os.environ.get("MINGW_BIN") or "")
    sdl2_bin = str(args.get("sdl2_bin") or config.get("sdl2_bin") or os.environ.get("SDL2_BIN") or "")
    sdl2_dir = Path(str(args.get("sdl2_dir") or config.get("sdl2_dir") or os.environ.get("SDL2_DIR") or ""))
    if not sdl2_bin and sdl2_dir:
        for candidate in (
            sdl2_dir.parent / "x86_64-w64-mingw32" / "bin",
            sdl2_dir.parent / "i686-w64-mingw32" / "bin",
            sdl2_dir.parent / "bin",
        ):
            if (candidate / "SDL2.dll").is_file():
                sdl2_bin = str(candidate)
                break
    path_prefix = os.pathsep.join(part for part in (sdl2_bin, toolchain_bin) if part)
    run = _run_process([str(executable)], cwd=sandbox_dir, timeout=timeout, path_prefix=path_prefix)
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
        "runtime_path_prefix": path_prefix,
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


def _write_snippet_source(args: dict[str, Any], snippet_dir: Path) -> tuple[Path, str, str] | None:
    c_code = args.get("c_code")
    if not c_code:
        return None
    entry = safe_symbol(str(args.get("ui_entry_function") or "ui_snippet_create"))
    header = str(args.get("ui_header") or "ui_snippet.h")
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


def lvgl_render_cache_dir(args: dict[str, Any]) -> Path:
    return resolve_path(args.get("cache_dir", ROOT / REGRESSION_SANDBOX_CONFIG["default_cache_dir"]))


def lvgl_render(args: dict[str, Any]) -> dict[str, Any]:
    output_dir = resolve_path(args.get("output_dir", ROOT / "artifacts" / "lvgl_render"))
    output_dir.mkdir(parents=True, exist_ok=True)
    mode = str(args.get("render_mode", "auto"))
    require_choice("render_mode", mode, {"auto", "probe"})
    cache_dir = lvgl_render_cache_dir(args)
    cache_dir.mkdir(parents=True, exist_ok=True)

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

    snippet_dir_arg = resolve_path(args.get("snippet_dir", cache_dir / "snippet"))
    snippet = _write_snippet_source(args, snippet_dir_arg)
    render_args = dict(args)
    sandbox_dir = resolve_path(args.get("sandbox_dir", cache_dir / "sandbox"))
    build_dir = resolve_path(args.get("build_dir", cache_dir / "build"))
    render_args["output_dir"] = str(sandbox_dir)
    if snippet is not None:
        snippet_dir, entry, header = snippet
        render_args["ui_under_test_dir"] = str(snippet_dir)
        render_args["ui_entry_function"] = entry
        render_args["ui_header"] = header

    prepared = prepare_lvgl_regression_sandbox(render_args)
    sandbox_path = Path(prepared["sandbox_dir"])
    built = build_lvgl_regression_sandbox({**args, "sandbox_dir": str(sandbox_path), "build_dir": str(build_dir)})
    diagnostics: dict[str, Any] = {
        "mode": mode,
        "cache_dir": str(cache_dir),
        "sandbox_dir": str(sandbox_path),
        "build_dir": str(build_dir),
        "prepare": prepared,
        "build": built,
        "log_issues": [],
    }
    if not built.get("ok"):
        diagnostics.update({"ok": False, "available": built.get("available", True), "status": built.get("status", "build_failed")})
        _write_json(diagnostics_path, diagnostics)
        return {
            "ok": False,
            "available": built.get("available", True),
            "status": built.get("status", "build_failed"),
            "stage": "build",
            "diagnostics_path": str(diagnostics_path),
            "cache_dir": str(cache_dir),
            "sandbox_dir": str(sandbox_path),
            "build_dir": str(build_dir),
            "prepare": prepared,
            "build": built,
            "artifacts": prepared.get("artifacts", []) + built.get("artifacts", []) + [str(diagnostics_path)],
        }
    if built.get("available") is False:
        diagnostics.update({"ok": True, "available": False, "status": "not_available"})
        _write_json(diagnostics_path, diagnostics)
        return {
            "ok": True,
            "available": False,
            "status": "not_available",
            "stage": "build",
            "diagnostics_path": str(diagnostics_path),
            "cache_dir": str(cache_dir),
            "sandbox_dir": str(sandbox_path),
            "build_dir": str(build_dir),
            "prepare": prepared,
            "build": built,
            "artifacts": prepared.get("artifacts", []) + [str(diagnostics_path)],
        }

    ran = run_lvgl_regression_sandbox({**args, "sandbox_dir": str(sandbox_path), "build_dir": str(build_dir), "output_dir": str(output_dir / "run")})
    artifacts = list(prepared.get("artifacts", [])) + list(built.get("artifacts", [])) + list(ran.get("artifacts", []))
    screenshot = _first_artifact(list(ran.get("artifacts", [])), (".ppm", ".bmp", ".png"), prefer="screen.ppm")
    diagnostics.update({"run": ran, "log_issues": ran.get("log_issues", [])})
    if screenshot is None or not screenshot.is_file():
        diagnostics.update({"ok": False, "available": True, "status": "screenshot_missing"})
        _write_json(diagnostics_path, diagnostics)
        return {
            "ok": False,
            "available": True,
            "status": "screenshot_missing",
            "stage": "run",
            "diagnostics_path": str(diagnostics_path),
            "cache_dir": str(cache_dir),
            "sandbox_dir": str(sandbox_path),
            "build_dir": str(build_dir),
            "prepare": prepared,
            "build": built,
            "run": ran,
            "artifacts": artifacts + [str(diagnostics_path)],
        }

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
        "cache_dir": str(cache_dir),
        "sandbox_dir": str(sandbox_path),
        "build_dir": str(build_dir),
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


try:
    from initial_loading_auto import generate_initial_loading_page as generate_initial_loading_page
except Exception:
    pass

try:
    from interactive_scene_auto import generate_interactive_scene_page as generate_interactive_scene_page
except Exception:
    pass

LVGL_TOOLS = {
    "get_lvgl_theme_skill": get_lvgl_theme_skill,
    "convert_image_to_lvgl_source": convert_image_to_lvgl_source,
    "generate_lvgl_layout_spec": generate_lvgl_layout_spec,
    "generate_lvgl_page_code": generate_lvgl_page_code,
    "generate_initial_loading_page": generate_initial_loading_page,
    "generate_interactive_scene_page": generate_interactive_scene_page,
    "generate_font_glyph": generate_font_glyph,
    "convert_assets_to_lvgl": convert_assets_to_lvgl,
    "analyze_layout_and_patch": analyze_layout_and_patch,
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
        "description": "Return Flex/Grid-first LVGL UI generation rules and default display config. Use before generating any LVGL page to load layout constraints (no absolute positioning, Flex/Grid preferred).",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "convert_image_to_lvgl_source",
        "description": "Convert a cut image (PNG/JPG/BMP) into LVGL RGB565 C-array header and/or binary asset. Returns generated file paths. Use when user provides design cut images for LVGL UI.",
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
        "description": "Create Flex/Grid-first LVGL page spec JSON from design notes and asset list. Returns spec object for generate_lvgl_page_code. Use as step 1 of LVGL page generation pipeline.",
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
        "description": "Generate LVGL C/H page scaffold from a layout spec. Returns .c/.h file paths with Flex/Grid layout, event handlers, and state machine. Use as step 2 of LVGL page generation pipeline.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "spec_json": {"type": "object"},
                "spec_path": {"type": "string"},
                "output_dir": {"type": "string", "default": "artifacts/lvgl_ui"},
                "lvgl_version": {"type": "string", "enum": sorted(LVGL_VERSIONS), "default": "v8"},
                "custom_events_enabled": {"type": "boolean", "default": True},
                "server_update_event_name": {"type": "string", "default": "auto"},
                "state_machine_enabled": {"type": "boolean", "default": True},
                "states": {"type": "array", "items": {"type": "string"}, "default": ["init", "loading", "ready", "error"]},
            },
            "additionalProperties": True,
        },
    },
    {
        "name": "generate_initial_loading_page",
        "description": "Generate the pixel-matched initial loading LVGL page from ui/initial_loading.png, background1.jpg, and pet.png.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "design_dir": {"type": "string", "default": "ui"},
                "output_dir": {"type": "string", "default": "artifacts/lvgl_ui/initial_loading"},
                "page_name": {"type": "string", "default": "initial_loading"},
                "design_path": {"type": "string"},
                "background_path": {"type": "string"},
                "pet_path": {"type": "string"},
                "loading_path": {"type": "string", "description": "Optional loading reference template for bbox calibration; defaults to ui/loadiing2.png when present."},
                "loading_reference_path": {"type": "string", "description": "Alias for loading_path."},
                "background_src": {"type": "string", "default": "S:/ui/background1.jpg"},
                "pet_src": {"type": "string", "default": "S:/ui/pet.png"},
                "background_src_macro": {"type": "string", "default": "UI_IMG_SRC_INITIAL_LOADING_BG"},
                "pet_src_macro": {"type": "string", "default": "UI_IMG_SRC_INITIAL_LOADING_PET"},
                "auto_analyze": {"type": "boolean", "default": True},
                "return_mode": {"type": "string", "enum": ["compact", "full"], "default": "full", "description": "Full preserves the legacy manifest-shaped response; compact returns key bboxes and artifact paths."},
                "title_text": {"type": "string", "default": "Loading"},
                "body_text": {"type": "string", "default": "Please wait"},
                "title_text_macro": {"type": "string", "default": "UI_TEXT_INITIAL_LOADING_TITLE"},
                "body_text_macro": {"type": "string", "default": "UI_TEXT_INITIAL_LOADING_BODY"},
                "lvgl_version": {"type": "string", "enum": sorted(LVGL_VERSIONS), "default": "v9"},
                "custom_events_enabled": {"type": "boolean", "default": True},
                "server_update_event_name": {"type": "string", "default": "auto"},
                "state_machine_enabled": {"type": "boolean", "default": True},
                "states": {"type": "array", "items": {"type": "string"}, "default": ["init", "loading", "ready", "error"]},
                "width": {"type": "integer", "default": 480},
                "height": {"type": "integer", "default": 800},
                "pet_x": {"type": "integer", "default": 118},
                "pet_y": {"type": "integer", "default": 111},
                "pet_w": {"type": "integer", "default": 271},
                "pet_h": {"type": "integer", "default": 391},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "generate_interactive_scene_page",
        "description": "Generate the interactive scene LVGL page from the no-favorite design screenshot and mood cut assets.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "design_dir": {"type": "string", "default": "ui"},
                "output_dir": {"type": "string", "default": "artifacts/lvgl_ui/interactive_scene"},
                "page_name": {"type": "string", "default": "interactive_scene"},
                "design_path": {"type": "string"},
                "background_path": {"type": "string"},
                "pet_path": {"type": "string"},
                "normal_path": {"type": "string"},
                "happy_path": {"type": "string"},
                "sad_path": {"type": "string"},
                "angry_path": {"type": "string"},
                "background_src": {"type": "string", "default": "S:/ui/background1.jpg"},
                "pet_src": {"type": "string", "default": "S:/ui/pet.png"},
                "normal_src": {"type": "string", "default": "S:/ui/mood_normal.png"},
                "happy_src": {"type": "string", "default": "S:/ui/mood_happy.png"},
                "sad_src": {"type": "string", "default": "S:/ui/mood_sad.png"},
                "angry_src": {"type": "string", "default": "S:/ui/mood_angry.png"},
                "background_src_macro": {"type": "string", "default": "UI_IMG_SRC_INTERACTIVE_BG"},
                "pet_src_macro": {"type": "string", "default": "UI_IMG_SRC_INTERACTIVE_PET"},
                "normal_src_macro": {"type": "string", "default": "UI_IMG_SRC_MOOD_NORMAL"},
                "happy_src_macro": {"type": "string", "default": "UI_IMG_SRC_MOOD_HAPPY"},
                "sad_src_macro": {"type": "string", "default": "UI_IMG_SRC_MOOD_SAD"},
                "angry_src_macro": {"type": "string", "default": "UI_IMG_SRC_MOOD_ANGRY"},
                "title_text": {"type": "string", "default": "How are you feeling?"},
                "hint_text": {"type": "string", "default": "Choose a mood"},
                "title_text_macro": {"type": "string", "default": "UI_TEXT_INTERACTIVE_SCENE_TITLE"},
                "hint_text_macro": {"type": "string", "default": "UI_TEXT_INTERACTIVE_SCENE_HINT"},
                "auto_analyze": {"type": "boolean", "default": True},
                "return_mode": {"type": "string", "enum": ["compact", "full"], "default": "full", "description": "Full preserves the legacy manifest-shaped response; compact returns key bboxes and artifact paths."},
                "lvgl_version": {"type": "string", "enum": sorted(LVGL_VERSIONS), "default": "v9"},
                "custom_events_enabled": {"type": "boolean", "default": True},
                "server_update_event_name": {"type": "string", "default": "auto"},
                "state_machine_enabled": {"type": "boolean", "default": True},
                "states": {"type": "array", "items": {"type": "string"}, "default": ["idle", "interacting", "selected", "error"]},
                "width": {"type": "integer", "default": 480},
                "height": {"type": "integer", "default": 800},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "analyze_layout_and_patch",
        "description": "Compare a visual-model JSON tree with existing LVGL C code and produce an incremental patch instead of regenerating the file.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "layout_json": {"type": "object"},
                "layout_path": {"type": "string"},
                "target_path": {"type": "string"},
                "existing_code": {"type": "string"},
                "patch_path": {"type": "string"},
                "apply": {"type": "boolean", "default": False},
                "parent_var": {"type": "string", "default": "root"},
                "lvgl_version": {"type": "string", "enum": sorted(LVGL_VERSIONS), "default": "v9"},
                "exception_reason": {"type": "string", "default": "visual model incremental layout patch"},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "convert_assets_to_lvgl",
        "description": "Batch-convert PNG/JPG/BMP/PPM cut assets to LVGL image descriptors and emit ui_assets registry files.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "input_paths": {"type": "array", "items": {"type": "string"}},
                "source_dir": {"type": "string"},
                "recursive": {"type": "boolean", "default": True},
                "output_dir": {"type": "string", "default": "artifacts/lvgl_assets"},
                "project_config": {"type": "object"},
                "converter_path": {"type": "string"},
                "converter_command": {"type": ["string", "array"]},
                "converter_args_template": {"type": ["string", "array"]},
                "strict_converter": {"type": "boolean", "default": False},
                "asset_prefix": {"type": "string", "default": "ui_img"},
                "format": {"type": "string", "enum": sorted(IMAGE_FORMATS), "default": "c_array"},
                "color_format": {"type": "string", "default": "RGB565"},
                "lvgl_version": {"type": "string", "enum": sorted(LVGL_VERSIONS), "default": "v9"},
                "timeout_seconds": {"type": "integer", "default": 120},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "generate_font_glyph",
        "description": "Extract glyphs from layout/text and run local lv_font_conv to generate a compact LVGL font plus placeholder macro header.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "layout_json": {"type": "object"},
                "layout_path": {"type": "string"},
                "text": {"type": "string"},
                "text_path": {"type": "string"},
                "fallback_text": {"type": "string"},
                "font_path": {"type": "string"},
                "converter_path": {"type": "string"},
                "output_dir": {"type": "string", "default": "artifacts/lvgl_fonts"},
                "font_name": {"type": "string"},
                "size": {"type": "integer", "default": 16},
                "bpp": {"type": "integer", "default": 4},
                "extra_args": {"type": "array", "items": {"type": "string"}},
                "timeout_seconds": {"type": "integer", "default": 120},
            },
            "additionalProperties": False,
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
                "sdl2_bin": {"type": "string"},
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
                "sdl2_bin": {"type": "string"},
                "ui_under_test_dir": {"type": "string"},
                "generator": {"type": "string"},
                "toolchain_bin": {"type": "string"},
                "ninja_bin": {"type": "string"},
                "c_compiler": {"type": "string"},
                "cxx_compiler": {"type": "string"},
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
                "sdl2_dir": {"type": "string"},
                "sdl2_bin": {"type": "string"},
                "toolchain_bin": {"type": "string"},
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
                "sdl2_bin": {"type": "string"},
                "ui_under_test_dir": {"type": "string"},
                "ui_entry_function": {"type": "string", "default": "ui_snippet_create"},
                "ui_header": {"type": "string", "default": "ui_snippet.h"},
                "toolchain_bin": {"type": "string"},
                "ninja_bin": {"type": "string"},
                "c_compiler": {"type": "string"},
                "cxx_compiler": {"type": "string"},
                "generator": {"type": "string"},
                "build_dir": {"type": "string"},
                "timeout_seconds": {"type": "integer", "default": 120},
                "parallel": {"type": "integer", "default": 4},
                "cache_dir": {"type": "string", "default": "artifacts/lvgl_render_cache"},
                "snippet_dir": {"type": "string"},
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
                "sdl2_bin": {"type": "string"},
                "ui_under_test_dir": {"type": "string"},
                "toolchain_bin": {"type": "string"},
                "ninja_bin": {"type": "string"},
                "c_compiler": {"type": "string"},
                "cxx_compiler": {"type": "string"},
                "timeout_seconds": {"type": "integer", "default": 120},
                "parallel": {"type": "integer", "default": 4},
                "cache_dir": {"type": "string", "default": "artifacts/lvgl_render_cache"},
                "snippet_dir": {"type": "string"},
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
