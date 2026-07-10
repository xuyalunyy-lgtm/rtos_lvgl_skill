"""Pure-stdlib image I/O — no Pillow dependency.

Provides read_png() for decoding PNG files using only struct + zlib.
Used by lvgl_ui.py as a stdlib replacement for PIL.Image.open().
"""
from __future__ import annotations

import struct
import zlib
from pathlib import Path
from typing import Any


# ── PNG decoding ────────────────────────────────────────────────

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _read_chunks(data: bytes) -> list[tuple[bytes, bytes]]:
    """Parse PNG into a list of (chunk_type, payload) tuples."""
    if data[:8] != _PNG_SIGNATURE:
        raise ValueError("not a PNG file (bad signature)")
    pos = 8
    chunks: list[tuple[bytes, bytes]] = []
    while pos < len(data):
        if pos + 8 > len(data):
            break
        length = struct.unpack(">I", data[pos:pos + 4])[0]
        ctype = data[pos + 4:pos + 8]
        payload = data[pos + 8:pos + 8 + length]
        # CRC is at pos + 8 + length, 4 bytes — we skip verification for speed
        chunks.append((ctype, payload))
        pos += 12 + length
    return chunks


def _paeth_predictor(a: int, b: int, c: int) -> int:
    """Paeth predictor for PNG row filter."""
    p = a + b - c
    pa = abs(p - a)
    pb = abs(p - b)
    pc = abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    elif pb <= pc:
        return b
    return c


def _defilter_rows(raw: bytes, width: int, height: int, bpp: int) -> list[bytearray]:
    """Reverse PNG row filters and return decoded pixel rows."""
    stride = width * bpp
    rows: list[bytearray] = []
    prev_row = bytearray(stride)
    pos = 0
    for _ in range(height):
        if pos >= len(raw):
            raise ValueError("truncated PNG pixel data")
        filter_type = raw[pos]
        pos += 1
        row = bytearray(raw[pos:pos + stride])
        pos += stride

        if filter_type == 0:  # None
            pass
        elif filter_type == 1:  # Sub
            for i in range(bpp, stride):
                row[i] = (row[i] + row[i - bpp]) & 0xFF
        elif filter_type == 2:  # Up
            for i in range(stride):
                row[i] = (row[i] + prev_row[i]) & 0xFF
        elif filter_type == 3:  # Average
            for i in range(stride):
                left = row[i - bpp] if i >= bpp else 0
                up = prev_row[i]
                row[i] = (row[i] + (left + up) // 2) & 0xFF
        elif filter_type == 4:  # Paeth
            for i in range(stride):
                left = row[i - bpp] if i >= bpp else 0
                up = prev_row[i]
                up_left = prev_row[i - bpp] if i >= bpp else 0
                row[i] = (row[i] + _paeth_predictor(left, up, up_left)) & 0xFF
        else:
            raise ValueError(f"unknown PNG filter type: {filter_type}")

        rows.append(row)
        prev_row = row
    return rows


def read_png(path: Path | str) -> tuple[int, int, list[tuple[int, int, int]]]:
    """Read a PNG file and return (width, height, pixels) as RGB tuples.

    Supports color type 2 (RGB) and 6 (RGBA). Other types raise ValueError.
    Uses only stdlib (struct + zlib).
    """
    path = Path(path)
    data = path.read_bytes()
    chunks = _read_chunks(data)

    # Find IHDR
    ihdr_found = False
    width = height = bit_depth = color_type = 0
    for ctype, payload in chunks:
        if ctype == b"IHDR":
            if len(payload) < 13:
                raise ValueError("IHDR too short")
            width, height, bit_depth, color_type, _, _, _ = struct.unpack(">IIBBBBB", payload[:13])
            ihdr_found = True
            break
    if not ihdr_found:
        raise ValueError("missing IHDR chunk")

    if color_type not in (0, 2, 3, 4, 6):
        raise ValueError(f"unsupported PNG color type: {color_type}")
    if bit_depth not in (1, 2, 4, 8, 16):
        raise ValueError(f"unsupported PNG bit depth: {bit_depth}")
    if color_type == 3:
        raise ValueError("PNG palette (indexed) color not supported by stdlib reader")
    if bit_depth != 8:
        raise ValueError(f"only 8-bit PNG supported, got {bit_depth}-bit")

    # Determine bytes per pixel
    if color_type == 0:  # Grayscale
        bpp = 1
    elif color_type == 2:  # RGB
        bpp = 3
    elif color_type == 4:  # Grayscale + Alpha
        bpp = 2
    elif color_type == 6:  # RGBA
        bpp = 4
    else:
        bpp = 1

    # Collect IDAT chunks
    idat_data = b"".join(p for ctype, p in chunks if ctype == b"IDAT")
    if not idat_data:
        raise ValueError("no IDAT chunks found")

    # Decompress
    try:
        raw = zlib.decompress(idat_data)
    except zlib.error as e:
        raise ValueError(f"PNG decompression failed: {e}")

    # Defilter
    rows = _defilter_rows(raw, width, height, bpp)

    # Extract RGB pixels
    pixels: list[tuple[int, int, int]] = []
    for row in rows:
        for x in range(width):
            offset = x * bpp
            if color_type == 0:  # Gray
                g = row[offset]
                pixels.append((g, g, g))
            elif color_type == 2:  # RGB
                pixels.append((row[offset], row[offset + 1], row[offset + 2]))
            elif color_type == 4:  # Gray+Alpha
                g = row[offset]
                pixels.append((g, g, g))
            elif color_type == 6:  # RGBA
                pixels.append((row[offset], row[offset + 1], row[offset + 2]))

    return width, height, pixels


def read_png_rgba(path: Path | str) -> tuple[int, int, list[tuple[int, int, int, int]]]:
    """Read a PNG file and return (width, height, pixels) as RGBA tuples.

    Same as read_png() but preserves alpha channel for RGBA images.
    """
    path = Path(path)
    data = path.read_bytes()
    chunks = _read_chunks(data)

    ihdr_found = False
    width = height = bit_depth = color_type = 0
    for ctype, payload in chunks:
        if ctype == b"IHDR":
            width, height, bit_depth, color_type, _, _, _ = struct.unpack(">IIBBBBB", payload[:13])
            ihdr_found = True
            break
    if not ihdr_found:
        raise ValueError("missing IHDR chunk")

    if color_type not in (0, 2, 6):
        raise ValueError(f"unsupported PNG color type: {color_type} for RGBA read")
    if bit_depth != 8:
        raise ValueError(f"only 8-bit PNG supported")

    bpp = {0: 1, 2: 3, 6: 4}[color_type]
    idat_data = b"".join(p for ctype, p in chunks if ctype == b"IDAT")
    raw = zlib.decompress(idat_data)
    rows = _defilter_rows(raw, width, height, bpp)

    pixels: list[tuple[int, int, int, int]] = []
    for row in rows:
        for x in range(width):
            offset = x * bpp
            if color_type == 0:
                g = row[offset]
                pixels.append((g, g, g, 255))
            elif color_type == 2:
                pixels.append((row[offset], row[offset + 1], row[offset + 2], 255))
            elif color_type == 6:
                pixels.append((row[offset], row[offset + 1], row[offset + 2], row[offset + 3]))

    return width, height, pixels


# ── BMP reading (moved from lvgl_ui.py for consolidation) ───────

def read_bmp(path: Path | str) -> tuple[int, int, list[tuple[int, int, int]]]:
    """Read a 24-bit BMP file using only stdlib."""
    path = Path(path)
    data = path.read_bytes()
    if data[:2] != b"BM":
        raise ValueError("not a BMP file")
    offset = struct.unpack("<I", data[10:14])[0]
    width = struct.unpack("<i", data[18:22])[0]
    raw_height = struct.unpack("<i", data[22:26])[0]
    bpp = struct.unpack("<H", data[28:30])[0]
    if bpp != 24:
        raise ValueError(f"only 24-bit BMP supported, got {bpp}-bit")
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


# ── Self-test ───────────────────────────────────────────────────

def _self_test() -> int:
    """Test PNG writing and reading roundtrip."""
    import tempfile

    # Create a test image: 4x3 RGB gradient
    w, h = 4, 3
    test_pixels = []
    for y in range(h):
        for x in range(w):
            test_pixels.append((x * 60, y * 80, 128))

    with tempfile.TemporaryDirectory() as tmp:
        png_path = Path(tmp) / "test.png"
        # Use the write_png from lvgl_ui if available, otherwise inline
        _write_png(png_path, w, h, test_pixels)
        r_w, r_h, r_pixels = read_png(png_path)
        assert r_w == w, f"width mismatch: {r_w} != {w}"
        assert r_h == h, f"height mismatch: {r_h} != {h}"
        assert len(r_pixels) == w * h, f"pixel count mismatch"
        for i, (expected, actual) in enumerate(zip(test_pixels, r_pixels)):
            assert expected == actual, f"pixel {i}: {actual} != {expected}"

    print("image_io self-test passed")
    return 0


def _write_png(path: Path, width: int, height: int, pixels: list[tuple[int, int, int]]) -> None:
    """Write a minimal PNG file (RGB, 8-bit). Copied from lvgl_ui.write_png."""
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
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b"")
    )


if __name__ == "__main__":
    import sys
    if "--self-test" in sys.argv:
        raise SystemExit(_self_test())
    else:
        print("Usage: python image_io.py --self-test")
        raise SystemExit(1)
