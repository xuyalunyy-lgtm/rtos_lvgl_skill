"""Asset pack encoder — converts PNG/JPG images to binary asset pack.

The asset pack is consumed by the native LVGL runner.
No image decoding in the native code.

Format:
  Header (magic, version, asset_count)
  Asset Table (offset, size, width, height, format, symbol)
  Pixel Data (raw RGB565/ARGB8888)

Usage:
    python mcp/lvgl_ir/asset_pack.py --input ui/ --output assets.pack
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path
from typing import Any

try:
    from PIL import Image
except ImportError:
    Image = None

# ── Constants ─────────────────────────────────────────────────────

PACK_MAGIC = b"APK\x00"
PACK_VERSION = 1
HEADER_SIZE = 16
ENTRY_SIZE = 64

FORMAT_RGB565 = 1
FORMAT_RGB565A8 = 2
FORMAT_ARGB8888 = 3
FORMAT_A8 = 4

FORMAT_MAP = {
    "RGB565": FORMAT_RGB565,
    "RGB565A8": FORMAT_RGB565A8,
    "ARGB8888": FORMAT_ARGB8888,
    "A8": FORMAT_A8,
}

_LVGL_V9_FORMATS = {
    "RGB565": ("LV_COLOR_FORMAT_RGB565", 2),
    "RGB565A8": ("LV_COLOR_FORMAT_RGB565A8", 2),
    "ARGB8888": ("LV_COLOR_FORMAT_ARGB8888", 4),
    "A8": ("LV_COLOR_FORMAT_A8", 1),
}


# ── Image conversion ──────────────────────────────────────────────


def _rgb_to_rgb565(r: int, g: int, b: int) -> int:
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)


def _pixels(img: Any) -> Any:
    """Use Pillow's deterministic flat pixel iterator across supported versions."""
    getter = getattr(img, "get_flattened_data", None)
    return getter() if getter is not None else img.getdata()


def _convert_rgb565(img: Any) -> bytes:
    """Convert image to RGB565 bytes."""
    rgb = img.convert("RGB")
    pixels = _pixels(rgb)
    out = bytearray()
    for r, g, b in pixels:
        val = _rgb_to_rgb565(r, g, b)
        out.append(val & 0xFF)
        out.append((val >> 8) & 0xFF)
    return bytes(out)


def _convert_rgb565a8(img: Any) -> tuple[bytes, bytes]:
    """Convert image to RGB565 + A8 alpha plane."""
    rgba = img.convert("RGBA")
    pixels = _pixels(rgba)
    rgb_out = bytearray()
    alpha_out = bytearray()
    for r, g, b, a in pixels:
        val = _rgb_to_rgb565(r, g, b)
        rgb_out.append(val & 0xFF)
        rgb_out.append((val >> 8) & 0xFF)
        alpha_out.append(a)
    return bytes(rgb_out), bytes(alpha_out)


def _convert_argb8888(img: Any) -> bytes:
    """Convert image to ARGB8888 bytes (A-R-G-B order)."""
    rgba = img.convert("RGBA")
    pixels = _pixels(rgba)
    out = bytearray()
    for r, g, b, a in pixels:
        out.extend((a, r, g, b))
    return bytes(out)


def _convert_a8(img: Any) -> bytes:
    """Extract alpha channel as A8 bytes."""
    rgba = img.convert("RGBA")
    pixels = _pixels(rgba)
    return bytes(a for _, _, _, a in pixels)


# ── Asset entry ───────────────────────────────────────────────────


def pack_asset(
    image_path: Path,
    symbol: str,
    color_format: str = "AUTO",
    auto_crop: bool = False,
) -> dict[str, Any]:
    """Pack a single image into asset data.

    Returns:
        Asset metadata dict with pixel data.
    """
    if Image is None:
        raise ImportError("Pillow required for asset packing")

    img = Image.open(image_path)
    width, height = img.size

    # Auto-crop alpha borders
    crop_offset = (0, 0, width, height)
    if auto_crop and img.mode == "RGBA":
        alpha = img.getchannel("A")
        bbox = alpha.getbbox()
        if bbox is None:
            return {"ok": False, "error": "Fully transparent image"}
        if bbox != (0, 0, width, height):
            img = img.crop(bbox)
            crop_offset = (bbox[0], bbox[1], bbox[2] - bbox[0], bbox[3] - bbox[1])
            width, height = img.size

    # Preserve geometry by default. Cropping transparent padding changes the
    # coordinate contract unless the scene is rewritten to compensate.

    # Convert to target format. AUTO preserves real transparency in the
    # RGB565A8 layout understood by the native LVGL runner.
    if color_format == "AUTO":
        rgba = img.convert("RGBA")
        alpha_min, _alpha_max = rgba.getchannel("A").getextrema()
        color_format = "RGB565A8" if alpha_min < 255 else "RGB565"
    fmt = FORMAT_MAP.get(color_format, FORMAT_RGB565)
    alpha_data = b""

    if fmt == FORMAT_RGB565:
        pixel_data = _convert_rgb565(img)
    elif fmt == FORMAT_RGB565A8:
        pixel_data, alpha_data = _convert_rgb565a8(img)
    elif fmt == FORMAT_ARGB8888:
        pixel_data = _convert_argb8888(img)
    elif fmt == FORMAT_A8:
        pixel_data = _convert_a8(img)
    else:
        return {"ok": False, "error": f"Unsupported format: {color_format}"}

    # Compute hash
    sha256 = hashlib.sha256(image_path.read_bytes()).hexdigest()

    return {
        "ok": True,
        "symbol": symbol,
        "source": str(image_path),
        "width": width,
        "height": height,
        "color_format": color_format,
        "format_id": fmt,
        "pixel_data": pixel_data,
        "alpha_data": alpha_data,
        "flash_bytes": len(pixel_data) + len(alpha_data),
        "sha256": sha256,
        "crop_offset": crop_offset,
    }


# ── Pack file encoding ────────────────────────────────────────────


def encode_pack(assets: list[dict[str, Any]]) -> bytes:
    """Encode multiple assets into a single .pack file.

    Format:
      Header: magic(4) + version(4) + asset_count(4) + reserved(4) = 16 bytes
      Entry table: one entry per asset (64 bytes each)
      Pixel data: concatenated
    """
    # Only successful assets are represented in both the header and table.
    # Keeping failed conversion attempts in ``asset_count`` corrupts every
    # following offset because the native reader trusts the fixed-size table.
    packed_assets = [asset for asset in assets if asset.get("ok")]

    # Build entry table and pixel data
    entries = []
    pixel_blocks = []
    offset = HEADER_SIZE + len(packed_assets) * ENTRY_SIZE

    for asset in packed_assets:
        pixel_data = asset["pixel_data"]
        alpha_data = asset.get("alpha_data", b"")
        symbol_raw = asset["symbol"].encode("ascii")
        if not symbol_raw or len(symbol_raw) > 31:
            raise ValueError("asset symbol must be 1-31 ASCII bytes")

        # Entry: symbol(32) + offset(4) + pixel_size(4) + alpha_size(4) + width(4) + height(4) + format(4) + reserved(8)
        symbol_bytes = symbol_raw.ljust(32, b"\x00")
        entry = struct.pack("<32sIIIIII8s",
            symbol_bytes,
            offset,
            len(pixel_data),
            len(alpha_data),
            asset["width"],
            asset["height"],
            asset["format_id"],
            b"\x00" * 8,
        )
        entries.append(entry)
        pixel_blocks.append(pixel_data)
        if alpha_data:
            pixel_blocks.append(alpha_data)
        offset += len(pixel_data) + len(alpha_data)

    # Build file
    header = struct.pack("<4sII4s", PACK_MAGIC, PACK_VERSION, len(packed_assets), b"\x00" * 4)
    return header + b"".join(entries) + b"".join(pixel_blocks)


# ── Pack file reading ─────────────────────────────────────────────


def list_pack_symbols(pack_path: str | Path) -> list[str]:
    """Read a .pack file and return the list of asset symbols it contains.

    Returns an empty list if the file is not a valid asset pack.
    """
    path = Path(pack_path)
    data = path.read_bytes()
    if len(data) < HEADER_SIZE:
        return []

    magic, version, asset_count = struct.unpack("<4sII", data[:12])
    if magic != PACK_MAGIC or version != PACK_VERSION:
        return []

    symbols: list[str] = []
    for i in range(asset_count):
        entry_offset = HEADER_SIZE + i * ENTRY_SIZE
        if entry_offset + ENTRY_SIZE > len(data):
            break
        symbol_bytes = data[entry_offset:entry_offset + 32]
        # Null-terminated ASCII
        null_pos = symbol_bytes.find(b"\x00")
        if null_pos >= 0:
            symbol_bytes = symbol_bytes[:null_pos]
        try:
            symbols.append(symbol_bytes.decode("ascii"))
        except UnicodeDecodeError:
            continue
    return symbols


# ── Manifest generation ───────────────────────────────────────────


def generate_manifest(assets: list[dict[str, Any]], output_dir: Path) -> dict[str, Any]:
    """Generate asset manifest JSON."""
    manifest = {
        "schema_version": "1.0",
        "assets": [],
        "fonts": [],
        "total_flash_bytes": 0,
        "total_ram_bytes": 0,
    }

    for asset in assets:
        if not asset.get("ok"):
            continue
        manifest["assets"].append({
            "symbol": asset["symbol"],
            "source": asset["source"],
            "width": asset["width"],
            "height": asset["height"],
            "color_format": asset["color_format"],
            "flash_bytes": asset["flash_bytes"],
            "sha256": asset["sha256"],
        })
        manifest["total_flash_bytes"] += asset["flash_bytes"]

    manifest_path = output_dir / "asset_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest


def _format_c_bytes(data: bytes, *, columns: int = 12) -> str:
    """Format raw image bytes deterministically for a generated C array."""
    return "\n".join(
        "    " + ", ".join(f"0x{byte:02X}" for byte in data[index:index + columns]) + ","
        for index in range(0, len(data), columns)
    )


def write_lvgl_v9_c_assets(assets: list[dict[str, Any]], output_dir: str | Path, *, stem: str = "ui_auto_assets") -> dict[str, Any]:
    """Emit real LVGL v9 image descriptors for packed assets.

    ``asset.pack`` is useful to the native simulator but cannot satisfy a
    firmware link reference such as ``LV_IMAGE_DECLARE(ui_pet)``.  This writer
    emits one C translation unit per asset containing the exact same byte
    order as the pack: RGB pixels followed by the A8 plane for RGB565A8
    images.  Per-asset units keep compiler memory and incremental builds
    bounded even for full-screen backgrounds.
    """
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    valid = [asset for asset in assets if asset.get("ok")]
    if len(valid) != len(assets):
        raise ValueError("cannot emit LVGL C assets when asset conversion failed")
    if not valid:
        raise ValueError("cannot emit LVGL C assets without assets")

    for asset in valid:
        symbol = asset.get("symbol")
        if not isinstance(symbol, str) or not symbol.isidentifier():
            raise ValueError(f"invalid C asset symbol: {symbol!r}")
        if asset.get("color_format") not in _LVGL_V9_FORMATS:
            raise ValueError(f"unsupported LVGL v9 color format: {asset.get('color_format')!r}")

    header_path = root / f"{stem}.h"
    cmake_path = root / f"{stem}.cmake"
    guard = "".join(char.upper() if char.isalnum() else "_" for char in stem) + "_H"

    header_path.write_text(
        f"#ifndef {guard}\n#define {guard}\n\n#include \"lvgl.h\"\n\n"
        + "\n".join(f"LV_IMAGE_DECLARE({asset['symbol']});" for asset in valid)
        + f"\n\n#endif /* {guard} */\n",
        encoding="utf-8",
        newline="\n",
    )

    source_paths: list[Path] = []
    for asset in valid:
        symbol = str(asset["symbol"])
        source_path = root / f"{symbol}.c"
        source_paths.append(source_path)
        color_format, bytes_per_pixel = _LVGL_V9_FORMATS[str(asset["color_format"])]
        pixel_data = bytes(asset["pixel_data"])
        alpha_data = bytes(asset.get("alpha_data", b""))
        data = pixel_data + alpha_data
        width, height = int(asset["width"]), int(asset["height"])
        if not data:
            raise ValueError(f"asset {symbol} has no pixel data")
        chunks = [
            '#include "lvgl.h"',
            f'#include "{header_path.name}"',
            "",
            "#ifndef LV_ATTRIBUTE_MEM_ALIGN",
            "#define LV_ATTRIBUTE_MEM_ALIGN",
            "#endif",
            "#ifndef LV_ATTRIBUTE_LARGE_CONST",
            "#define LV_ATTRIBUTE_LARGE_CONST",
            "#endif",
            "",
            f"static const LV_ATTRIBUTE_MEM_ALIGN LV_ATTRIBUTE_LARGE_CONST uint8_t {symbol}_map[] = {{",
            _format_c_bytes(data),
            "};",
            f"const lv_image_dsc_t {symbol} = {{",
            "    .header.magic = LV_IMAGE_HEADER_MAGIC,",
            f"    .header.cf = {color_format},",
            "    .header.flags = 0,",
            f"    .header.w = {width},",
            f"    .header.h = {height},",
            f"    .header.stride = {width * bytes_per_pixel},",
            "    .header.reserved_2 = 0,",
            f"    .data_size = sizeof({symbol}_map),",
            f"    .data = {symbol}_map,",
            "    .reserved = NULL,",
            "};",
        ]
        source_path.write_text("\n".join(chunks) + "\n", encoding="utf-8", newline="\n")
    cmake_path.write_text(
        "set(UI_AUTO_ASSET_SOURCES\n"
        + "".join(f"    \"${{CMAKE_CURRENT_LIST_DIR}}/{path.name}\"\n" for path in source_paths)
        + ")\n",
        encoding="utf-8",
        newline="\n",
    )
    return {
        "header": str(header_path),
        "sources": [str(path) for path in source_paths],
        "cmake": str(cmake_path),
        "symbols": [str(asset["symbol"]) for asset in valid],
        "total_flash_bytes": sum(int(asset["flash_bytes"]) for asset in valid),
    }


# ── CLI ───────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Input directory or single image")
    parser.add_argument("--output", required=True, help="Output .pack file")
    parser.add_argument("--format", default="AUTO", choices=["AUTO", "RGB565", "RGB565A8", "ARGB8888", "A8"])
    parser.add_argument("--prefix", default="ui_img", help="Symbol prefix")
    parser.add_argument("--crop", action="store_true", help="Crop transparent borders (changes image geometry)")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"ERROR: Input not found: {args.input}")
        return 1

    # Collect images
    if input_path.is_file():
        images = [input_path]
    else:
        images = sorted([
            p for p in input_path.iterdir()
            if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".bmp"}
        ])

    if not images:
        print("ERROR: No images found")
        return 1

    # Pack each image
    assets = []
    for img_path in images:
        symbol = f"{args.prefix}_{img_path.stem}".upper()
        result = pack_asset(img_path, symbol, args.format, args.crop)
        assets.append(result)
        if result["ok"]:
            print(f"  {img_path.name}: {result['width']}x{result['height']} {args.format} ({result['flash_bytes']} bytes)")
        else:
            print(f"  {img_path.name}: FAILED - {result.get('error')}")

    # Encode pack file
    pack_data = encode_pack(assets)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(pack_data)

    # Generate manifest
    generate_manifest(assets, output_path.parent)

    ok_count = sum(1 for a in assets if a.get("ok"))
    print(f"\nPacked {ok_count}/{len(assets)} assets → {len(pack_data)} bytes")
    print(f"Output: {output_path}")
    return 0 if ok_count == len(assets) else 1


if __name__ == "__main__":
    sys.exit(main())
