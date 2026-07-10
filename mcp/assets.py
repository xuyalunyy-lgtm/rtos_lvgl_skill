from __future__ import annotations

import hashlib
import json
import os
import shutil
import shlex
import subprocess
import tempfile
import textwrap
from pathlib import Path
from typing import Any

try:
    from schemas import ASSET_INPUT_EXTENSIONS, COLOR_FORMATS, DEFAULT_FONT_CANDIDATES, DISPLAY_CONFIG, IMAGE_FORMATS, LVGL_VERSIONS, ROOT
    from codegen import asset_macro_for, load_json_like, require_choice, resolve_path, safe_symbol, walk_text_values
except ImportError:  # pragma: no cover - package import fallback
    from .schemas import ASSET_INPUT_EXTENSIONS, COLOR_FORMATS, DEFAULT_FONT_CANDIDATES, DISPLAY_CONFIG, IMAGE_FORMATS, LVGL_VERSIONS, ROOT
    from .codegen import asset_macro_for, load_json_like, require_choice, resolve_path, safe_symbol, walk_text_values


# ── Converter Preset Allowlist ──────────────────────────────────────
# Only these presets may be used for image conversion. Arbitrary commands
# are no longer accepted via MCP to prevent command injection.

CONVERTER_PRESETS: dict[str, dict[str, Any]] = {
    "lv_img_conv": {
        "description": "LVGL official image converter (Node.js)",
        "binary": "lv_img_conv",
        "template": [
            "lv_img_conv", "{input}",
            "--output", "{output_dir}",
            "--name", "{symbol}",
            "--cf", "{color_format}",
            "--format", "c_array",
        ],
    },
    "lvgl_image_converter": {
        "description": "Python-based LVGL image converter",
        "binary": "python",
        "template": [
            "python", "-m", "lvgl_image_converter",
            "{input}", "-o", "{output}",
            "--name", "{symbol}", "--cf", "{color_format}",
        ],
    },
}


def _check_preset_binary(preset_name: str) -> str | None:
    """Check if the preset's binary is available in PATH. Returns error msg or None."""
    preset = CONVERTER_PRESETS.get(preset_name)
    if preset is None:
        return f"Unknown converter preset: {preset_name}. Available: {sorted(CONVERTER_PRESETS)}"
    binary = preset["binary"]
    if shutil.which(binary) is None:
        return f"Converter binary '{binary}' not found in PATH. Install it first."
    return None


def _hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")

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
    if suffix == ".png":
        from image_io import read_png as _read_png
        return _read_png(path)
    # JPG/other formats: try Windows System.Drawing fallback (no Pillow needed)
    try:
        return read_image_with_system_drawing(path)
    except Exception as fallback_exc:
        raise ValueError(f"{suffix or 'image'} conversion requires System.Drawing fallback (Windows) or Pillow: {fallback_exc}") from fallback_exc

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

    converter_preset = str(args.get("converter_preset", "")).strip()
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
        if converter_preset:
            err = _check_preset_binary(converter_preset)
            if err:
                result["error"] = err
                converted.append(result)
                continue
            preset = CONVERTER_PRESETS[converter_preset]
            cmd = [part.format(**values) for part in preset["template"]]
            proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, encoding="utf-8", errors="replace", timeout=int(args.get("timeout_seconds", 120)))
            result.update({"converter": converter_preset, "command": cmd, "stdout": proc.stdout, "stderr": proc.stderr, "exit_code": proc.returncode})
            result["ok"] = proc.returncode == 0
            if result["ok"]:
                result["artifacts"] = [str(path) for path in output_dir.glob(f"{symbol}*")]
            elif strict_converter:
                converted.append(result)
                continue
        if not result["ok"]:
            if color_format != "RGB565":
                result["error"] = f"fallback converter supports RGB565 only, got {color_format}; provide converter_preset for this format"
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

def find_lv_font_conv() -> str | None:
    """Find lv_font_conv binary. Checks LV_FONT_CONV env var first, then PATH."""
    env_path = os.environ.get("LV_FONT_CONV", "").strip()
    if env_path and Path(env_path).exists():
        return env_path
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
    converter = find_lv_font_conv()
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

__all__ = [
    "convert_assets_to_lvgl",
    "convert_image_to_lvgl_source",
    "convert_image_to_png",
    "generate_font_glyph",
    "read_image",
]
