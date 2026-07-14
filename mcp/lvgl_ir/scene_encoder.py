"""Scene encoder — converts UI Spec v2 to scene.bin binary format.

The binary format is consumed by the native LVGL headless simulator.
No JSON parsing in the native code.

Usage:
    python mcp/lvgl_ir/scene_encoder.py --spec path/to/ui_spec.json --output scene.bin
"""
from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path
from typing import Any

# ── Opcode definitions ────────────────────────────────────────────

class Op:
    """Scene command opcodes."""
    END = 0
    CREATE_SCREEN = 1
    CREATE_CONTAINER = 2
    CREATE_LABEL = 3
    CREATE_BUTTON = 4
    CREATE_IMAGE = 5
    CREATE_BAR = 6
    CREATE_SLIDER = 7
    CREATE_SWITCH = 8
    CREATE_CHECKBOX = 9
    CREATE_DROPDOWN = 10
    CREATE_SPINNER = 11
    CREATE_ARC = 12

    SET_PARENT = 20
    SET_SIZE = 21
    SET_TEXT = 22
    SET_VALUE = 23
    SET_RANGE = 24
    SET_IMAGE_SOURCE = 25

    # Layout
    SET_FLEX_FLOW = 30
    SET_FLEX_ALIGN = 31
    SET_PAD_GAP = 32
    SET_PAD = 33
    SET_GRID = 34

    # Styles
    SET_STYLE_BG_COLOR = 40
    SET_STYLE_BG_OPA = 41
    SET_STYLE_RADIUS = 42
    SET_STYLE_BORDER_WIDTH = 43
    SET_STYLE_BORDER_COLOR = 44
    SET_STYLE_SHADOW_WIDTH = 45
    SET_STYLE_TEXT_COLOR = 46
    SET_STYLE_TEXT_FONT_SIZE = 47
    SET_STYLE_TEXT_ALIGN = 48
    SET_STYLE_WIDTH = 49
    SET_STYLE_HEIGHT = 50
    SET_STYLE_TEXT_FONT = 51

    # Events
    SET_EVENT_CLICKED = 60
    SET_EVENT_VALUE_CHANGED = 61

    # Metadata
    SET_NODE_ID = 70
    SET_SOURCE_BBOX = 71


# Widget type to opcode mapping
WIDGET_OPCODES = {
    "screen": Op.CREATE_SCREEN,
    "container": Op.CREATE_CONTAINER,
    "label": Op.CREATE_LABEL,
    "button": Op.CREATE_BUTTON,
    "image": Op.CREATE_IMAGE,
    "bar": Op.CREATE_BAR,
    "slider": Op.CREATE_SLIDER,
    "switch": Op.CREATE_SWITCH,
    "checkbox": Op.CREATE_CHECKBOX,
    "dropdown": Op.CREATE_DROPDOWN,
    "spinner": Op.CREATE_SPINNER,
    "arc": Op.CREATE_ARC,
}

# Flex flow mapping
FLEX_FLOW_MAP = {
    "flex-row": 0,
    "flex-column": 1,
    "flex-row-wrap": 2,
    "flex-column-wrap": 3,
}

# Flex align mapping
FLEX_ALIGN_MAP = {
    "start": 0,
    "center": 1,
    "end": 2,
    "space-between": 3,
    "space-around": 4,
    "space-evenly": 5,
    "stretch": 6,
}

# Text align mapping
TEXT_ALIGN_MAP = {
    "left": 0,
    "center": 1,
    "right": 2,
}


# ── String table ──────────────────────────────────────────────────


class StringTable:
    """Manages string deduplication and encoding."""

    def __init__(self):
        self.strings: list[str] = []
        self.index: dict[str, int] = {}

    def add(self, s: str) -> int:
        """Add string and return its index."""
        if s in self.index:
            return self.index[s]
        idx = len(self.strings)
        self.strings.append(s)
        self.index[s] = idx
        return idx

    def encode(self) -> bytes:
        """Encode string table to bytes."""
        parts = []
        for s in self.strings:
            encoded = s.encode("utf-8") + b"\x00"
            parts.append(encoded)
        return b"".join(parts)


# ── Command encoder ───────────────────────────────────────────────


class CommandBuffer:
    """Accumulates scene commands."""

    def __init__(self, strings: StringTable):
        self.strings = strings
        self.commands: list[bytes] = []

    def _emit(self, opcode: int, node_id: int, data: bytes = b""):
        """Emit a command."""
        header = struct.pack("<HHI", opcode, len(data), node_id)
        self.commands.append(header + data)

    def create_widget(self, opcode: int, node_id: int):
        self._emit(opcode, node_id)

    def set_parent(self, node_id: int, parent_id: int):
        self._emit(Op.SET_PARENT, node_id, struct.pack("<I", parent_id))

    def set_size(self, node_id: int, width: int, height: int):
        self._emit(Op.SET_SIZE, node_id, struct.pack("<ii", width, height))

    def set_text(self, node_id: int, text: str):
        idx = self.strings.add(text)
        self._emit(Op.SET_TEXT, node_id, struct.pack("<I", idx))

    def set_value(self, node_id: int, value: int):
        self._emit(Op.SET_VALUE, node_id, struct.pack("<i", value))

    def set_range(self, node_id: int, min_val: int, max_val: int):
        self._emit(Op.SET_RANGE, node_id, struct.pack("<ii", min_val, max_val))

    def set_image_source(self, node_id: int, src: str):
        idx = self.strings.add(src)
        self._emit(Op.SET_IMAGE_SOURCE, node_id, struct.pack("<I", idx))

    def set_flex_flow(self, node_id: int, flow: str):
        self._emit(Op.SET_FLEX_FLOW, node_id, struct.pack("<I", FLEX_FLOW_MAP.get(flow, 1)))

    def set_flex_align(self, node_id: int, main: str, cross: str, track: str = "start"):
        data = struct.pack("<III", FLEX_ALIGN_MAP.get(main, 0), FLEX_ALIGN_MAP.get(cross, 0), FLEX_ALIGN_MAP.get(track, 0))
        self._emit(Op.SET_FLEX_ALIGN, node_id, data)

    def set_pad_gap(self, node_id: int, gap: int):
        self._emit(Op.SET_PAD_GAP, node_id, struct.pack("<I", gap))

    def set_pad(self, node_id: int, top: int, bottom: int, left: int, right: int):
        self._emit(Op.SET_PAD, node_id, struct.pack("<iiii", top, bottom, left, right))

    def set_style_bg_color(self, node_id: int, color: int):
        self._emit(Op.SET_STYLE_BG_COLOR, node_id, struct.pack("<I", color))

    def set_style_bg_opa(self, node_id: int, opa: int):
        self._emit(Op.SET_STYLE_BG_OPA, node_id, struct.pack("<I", opa))

    def set_style_radius(self, node_id: int, radius: int):
        self._emit(Op.SET_STYLE_RADIUS, node_id, struct.pack("<I", radius))

    def set_style_border_width(self, node_id: int, width: int):
        self._emit(Op.SET_STYLE_BORDER_WIDTH, node_id, struct.pack("<I", width))

    def set_style_border_color(self, node_id: int, color: int):
        self._emit(Op.SET_STYLE_BORDER_COLOR, node_id, struct.pack("<I", color))

    def set_style_text_color(self, node_id: int, color: int):
        self._emit(Op.SET_STYLE_TEXT_COLOR, node_id, struct.pack("<I", color))

    def set_style_text_align(self, node_id: int, align: str):
        self._emit(Op.SET_STYLE_TEXT_ALIGN, node_id, struct.pack("<I", TEXT_ALIGN_MAP.get(align, 0)))

    def set_style_text_font(self, node_id: int, font_id: str):
        idx = self.strings.add(font_id)
        self._emit(Op.SET_STYLE_TEXT_FONT, node_id, struct.pack("<I", idx))

    def set_style_width(self, node_id: int, width: int):
        self._emit(Op.SET_STYLE_WIDTH, node_id, struct.pack("<i", width))

    def set_style_height(self, node_id: int, height: int):
        self._emit(Op.SET_STYLE_HEIGHT, node_id, struct.pack("<i", height))

    def set_event_clicked(self, node_id: int):
        self._emit(Op.SET_EVENT_CLICKED, node_id)

    def set_node_id(self, node_id: int, name: str):
        idx = self.strings.add(name)
        self._emit(Op.SET_NODE_ID, node_id, struct.pack("<I", idx))

    def set_source_bbox(self, node_id: int, x: int, y: int, w: int, h: int):
        self._emit(Op.SET_SOURCE_BBOX, node_id, struct.pack("<iiii", x, y, w, h))

    def end(self):
        self._emit(Op.END, 0)

    def encode(self) -> bytes:
        return b"".join(self.commands)


# ── Hex color parsing ─────────────────────────────────────────────


def _parse_color(color_str: str) -> int:
    """Parse '#RRGGBB' to 0x00RRGGBB."""
    if not color_str:
        return 0
    color_str = color_str.lstrip("#")
    try:
        return int(color_str, 16)
    except ValueError:
        return 0


# ── Scene encoding ────────────────────────────────────────────────


def encode_spec(spec: dict[str, Any]) -> bytes:
    """Encode UI Spec v2 to scene.bin bytes.

    Args:
        spec: UI Spec v2 dict.

    Returns:
        scene.bin bytes.
    """
    strings = StringTable()
    cmds = CommandBuffer(strings)

    # Reserve space for header (will be filled later)
    header_size = 32

    nodes = spec.get("nodes", [])
    node_id_map: dict[str, int] = {}

    # Assign numeric IDs
    for i, node in enumerate(nodes):
        node_id = node.get("id", f"node_{i}")
        node_id_map[node_id] = i + 1  # 0 is reserved for END

    # Encode nodes
    for i, node in enumerate(nodes):
        node_id = node.get("id", f"node_{i}")
        numeric_id = node_id_map[node_id]
        node_type = node.get("type", "container")

        # Create widget
        opcode = WIDGET_OPCODES.get(node_type, Op.CREATE_CONTAINER)
        cmds.create_widget(opcode, numeric_id)

        # Set node ID name
        cmds.set_node_id(numeric_id, node_id)

        # Set parent
        parent_id = node.get("parent_id")
        if parent_id and parent_id in node_id_map:
            cmds.set_parent(numeric_id, node_id_map[parent_id])

        # Set text
        text = node.get("text", "")
        if text and node_type in ("label", "button", "checkbox"):
            cmds.set_text(numeric_id, text)

        # Set image source
        src = node.get("src", "")
        if src and node_type == "image":
            cmds.set_image_source(numeric_id, src)

        # Set value
        if "value" in node and node_type in ("bar", "slider"):
            cmds.set_value(numeric_id, node["value"])

        # Set range
        if "range_min" in node and "range_max" in node and node_type in ("bar", "slider"):
            cmds.set_range(numeric_id, node["range_min"], node["range_max"])

        # Set source bbox
        bbox = node.get("source_bbox", [])
        if len(bbox) == 4:
            cmds.set_source_bbox(numeric_id, bbox[0], bbox[1], bbox[2], bbox[3])

        # Set styles
        styles = node.get("styles", {})
        if styles:
            _encode_styles(cmds, numeric_id, styles)

        # Set layout
        layout = node.get("layout", {})
        if layout:
            _encode_layout(cmds, numeric_id, layout)

        # Set events
        for event in spec.get("events", []):
            if event.get("node_id") == node_id:
                event_type = event.get("event_type", "")
                if event_type == "clicked":
                    cmds.set_event_clicked(numeric_id)

    # End scene
    cmds.end()

    # Build binary
    string_bytes = strings.encode()
    command_bytes = cmds.encode()

    # Header: magic(4) + version(4) + node_count(4) + string_table_offset(4) + string_table_size(4) + command_offset(4) + command_size(4) + reserved(4)
    magic = b"SCN\x00"
    version = 2
    node_count = len(nodes)
    string_table_offset = header_size
    string_table_size = len(string_bytes)
    command_offset = header_size + string_table_size
    command_size = len(command_bytes)

    header = struct.pack("<4sIIIIIII",
        magic,
        version,
        node_count,
        string_table_offset,
        string_table_size,
        command_offset,
        command_size,
        0,  # reserved
    )

    return header + string_bytes + command_bytes


def _encode_styles(cmds: CommandBuffer, node_id: int, styles: dict[str, Any]):
    """Encode style properties."""
    if "bg_color" in styles:
        cmds.set_style_bg_color(node_id, _parse_color(styles["bg_color"]))
    if "bg_opa" in styles:
        cmds.set_style_bg_opa(node_id, styles["bg_opa"])
    if "radius" in styles:
        cmds.set_style_radius(node_id, styles["radius"])
    if "border_width" in styles:
        cmds.set_style_border_width(node_id, styles["border_width"])
    if "border_color" in styles:
        cmds.set_style_border_color(node_id, _parse_color(styles["border_color"]))
    if "text_color" in styles:
        cmds.set_style_text_color(node_id, _parse_color(styles["text_color"]))
    if "text_align" in styles:
        cmds.set_style_text_align(node_id, str(styles["text_align"]))
    font_id = styles.get("font_id", styles.get("font", ""))
    if isinstance(font_id, str) and font_id.strip():
        cmds.set_style_text_font(node_id, font_id.strip().lstrip("&"))
    if "width" in styles and styles["width"] > 0:
        cmds.set_style_width(node_id, styles["width"])
    if "height" in styles and styles["height"] > 0:
        cmds.set_style_height(node_id, styles["height"])
    if "pad_top" in styles:
        cmds.set_pad(node_id,
                     styles.get("pad_top", 0),
                     styles.get("pad_bottom", 0),
                     styles.get("pad_left", 0),
                     styles.get("pad_right", 0))


def _encode_layout(cmds: CommandBuffer, node_id: int, layout: dict[str, Any]):
    """Encode layout properties."""
    mode = layout.get("mode", "flex-column")
    if mode.startswith("flex"):
        cmds.set_flex_flow(node_id, mode)
        if "flex_justify" in layout:
            cmds.set_flex_align(node_id, layout["flex_justify"], layout.get("flex_align", "start"))
        if "gap" in layout:
            cmds.set_pad_gap(node_id, layout["gap"])


# ── CLI ───────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", required=True, help="Path to UI Spec JSON")
    parser.add_argument("--output", required=True, help="Output scene.bin path")
    args = parser.parse_args()

    spec_path = Path(args.spec)
    if not spec_path.is_file():
        print(f"ERROR: Spec not found: {args.spec}")
        return 1

    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    scene_bytes = encode_spec(spec)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(scene_bytes)

    print(f"Encoded {len(spec.get('nodes', []))} nodes → {len(scene_bytes)} bytes")
    print(f"Output: {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
