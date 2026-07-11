"""Contract tests for the Python asset-pack encoder.

The native runner consumes this format directly, so table size, entry count,
and data offsets are part of the public protocol rather than implementation
details.
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "mcp"))

from lvgl_ir.asset_pack import (  # noqa: E402
    ENTRY_SIZE,
    HEADER_SIZE,
    PACK_MAGIC,
    PACK_VERSION,
    encode_pack,
)


def _asset(symbol: str, pixels: bytes, alpha: bytes = b"") -> dict:
    return {
        "ok": True,
        "symbol": symbol,
        "width": 1,
        "height": 1,
        "format_id": 2 if alpha else 1,
        "pixel_data": pixels,
        "alpha_data": alpha,
    }


def test_pack_header_uses_only_successful_entries() -> None:
    data = encode_pack([
        _asset("FIRST", b"\x01\x02"),
        {"ok": False, "error": "fixture"},
        _asset("SECOND", b"\x03\x04", b"\xff"),
    ])

    magic, version, count, _reserved = struct.unpack("<4sII4s", data[:HEADER_SIZE])
    assert magic == PACK_MAGIC
    assert version == PACK_VERSION
    assert count == 2
    assert len(data) == HEADER_SIZE + 2 * ENTRY_SIZE + 2 + 2 + 1


def test_pack_offsets_are_contiguous() -> None:
    data = encode_pack([_asset("FIRST", b"\x01\x02"), _asset("SECOND", b"\x03\x04", b"\xff")])
    first = struct.unpack("<32sIIIIII8s", data[HEADER_SIZE:HEADER_SIZE + ENTRY_SIZE])
    second = struct.unpack("<32sIIIIII8s", data[HEADER_SIZE + ENTRY_SIZE:HEADER_SIZE + 2 * ENTRY_SIZE])

    first_offset, first_pixels, first_alpha = first[1:4]
    second_offset, second_pixels, second_alpha = second[1:4]
    assert first_offset == HEADER_SIZE + 2 * ENTRY_SIZE
    assert second_offset == first_offset + first_pixels + first_alpha
    assert second_offset + second_pixels + second_alpha == len(data)
