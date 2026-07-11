"""Object tree binary reader — converts native runner output to JSON.

Parses the binary object_tree.bin produced by the native LVGL runner
and outputs a hierarchical JSON tree for comparison and inspection.

Binary format (little-endian):
  Header: magic(4) + version(4) + display_width(4) + display_height(4) + node_count(4) = 20 bytes
  String table size: uint32
  String table: concatenated null-terminated strings
  Nodes: node_count × 40-byte structs

Usage:
    from mcp.lvgl_ir.object_tree_reader import read_object_tree
    tree = read_object_tree("artifacts/render/object_tree.bin")
"""
from __future__ import annotations

import struct
from pathlib import Path
from typing import Any

TREE_MAGIC = 0x00454554  # "TEE\0" as little-endian uint32
HEADER_SIZE = 20
STRING_SIZE_FIELD = 4
NODE_STRUCT_SIZE = 44  # 11 × uint32/int32 (includes 2 reserved)

TYPE_NAMES = {
    0: "unknown",
    1: "container",
    2: "label",
    3: "button",
    4: "image",
    5: "bar",
    6: "slider",
    7: "switch",
    8: "checkbox",
    9: "dropdown",
    10: "arc",
    11: "spinner",
}


def read_object_tree(path: str | Path) -> dict[str, Any]:
    """Read a binary object_tree.bin and return a JSON-serializable dict.

    Returns:
        {
            "display": {"width": int, "height": int},
            "node_count": int,
            "root": {node dict with "children": [...]},
        }

    Raises:
        ValueError: If the file is not a valid object tree.
    """
    data = Path(path).read_bytes()

    # ── Header ────────────────────────────────────────────────────
    if len(data) < HEADER_SIZE + STRING_SIZE_FIELD:
        raise ValueError(f"Object tree file too small ({len(data)} bytes)")

    magic, version, display_w, display_h, node_count = struct.unpack(
        "<5I", data[:HEADER_SIZE]
    )
    if magic != TREE_MAGIC:
        raise ValueError(
            f"Bad magic: 0x{magic:08X} (expected 0x{TREE_MAGIC:08X})"
        )
    if version != 1:
        raise ValueError(f"Unsupported version: {version}")

    # ── String table ──────────────────────────────────────────────
    str_table_size = struct.unpack("<I", data[HEADER_SIZE:HEADER_SIZE + 4])[0]
    str_table_start = HEADER_SIZE + STRING_SIZE_FIELD
    str_table_end = str_table_start + str_table_size

    if str_table_end > len(data):
        raise ValueError("String table extends beyond file")

    raw_strings = data[str_table_start:str_table_end]
    strings = _parse_string_table(raw_strings)

    # ── Nodes ─────────────────────────────────────────────────────
    nodes_start = str_table_end
    expected_end = nodes_start + node_count * NODE_STRUCT_SIZE
    if expected_end > len(data):
        raise ValueError(
            f"Node data extends beyond file: need {expected_end}, have {len(data)}"
        )

    flat_nodes: list[dict[str, Any]] = []
    for i in range(node_count):
        offset = nodes_start + i * NODE_STRUCT_SIZE
        fields = struct.unpack("<IiiiiIIIIII", data[offset:offset + NODE_STRUCT_SIZE])
        type_id, x, y, w, h, flags, child_count, text_offset, value = fields[:9]
        # fields[9:11] are reserved

        text = ""
        if text_offset > 0 and text_offset < len(raw_strings):
            # Find the null-terminated string at this offset
            end = raw_strings.find(b"\x00", text_offset)
            if end < 0:
                end = len(raw_strings)
            try:
                text = raw_strings[text_offset:end].decode("utf-8", errors="replace")
            except Exception:
                text = ""

        flat_nodes.append({
            "type": TYPE_NAMES.get(type_id, f"unknown_{type_id}"),
            "type_id": type_id,
            "x": x,
            "y": y,
            "width": w,
            "height": h,
            "visible": bool(flags & 1),
            "clickable": bool(flags & 2),
            "child_count": child_count,
            "text": text,
            "value": value,
        })

    # ── Build hierarchy ───────────────────────────────────────────
    root = _build_tree(flat_nodes)

    return {
        "display": {"width": display_w, "height": display_h},
        "node_count": node_count,
        "root": root,
    }


def _parse_string_table(raw: bytes) -> list[str]:
    """Split null-terminated string table into a list."""
    strings: list[str] = []
    start = 0
    for i, byte in enumerate(raw):
        if byte == 0:
            try:
                strings.append(raw[start:i].decode("utf-8", errors="replace"))
            except Exception:
                strings.append("")
            start = i + 1
    # Trailing string without null terminator
    if start < len(raw):
        try:
            strings.append(raw[start:].decode("utf-8", errors="replace"))
        except Exception:
            strings.append("")
    return strings


def _build_tree(flat_nodes: list[dict[str, Any]]) -> dict[str, Any]:
    """Convert flat node list to hierarchical tree using child_count.

    The flat list is in pre-order (depth-first). Each node's child_count
    tells us how many subsequent nodes belong to it.
    """
    index = 0

    def _next_node() -> dict[str, Any]:
        nonlocal index
        if index >= len(flat_nodes):
            return {"type": "unknown", "children": []}

        node = flat_nodes[index]
        index += 1

        children: list[dict[str, Any]] = []
        for _ in range(node.get("child_count", 0)):
            children.append(_next_node())

        result: dict[str, Any] = {
            "type": node["type"],
            "x": node["x"],
            "y": node["y"],
            "width": node["width"],
            "height": node["height"],
            "visible": node["visible"],
            "clickable": node["clickable"],
        }
        if node.get("text"):
            result["text"] = node["text"]
        if node.get("value"):
            result["value"] = node["value"]
        if children:
            result["children"] = children

        return result

    return _next_node()
