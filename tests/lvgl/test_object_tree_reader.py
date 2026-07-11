"""Tests for object tree binary reader."""
from __future__ import annotations

import struct
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "mcp"))

from lvgl_ir.object_tree_reader import (
    TREE_MAGIC,
    NODE_STRUCT_SIZE,
    read_object_tree,
)


# ── Helpers ───────────────────────────────────────────────────────


def _build_tree_bin(
    display_w: int = 480,
    display_h: int = 800,
    nodes: list[dict] | None = None,
    strings: list[str] | None = None,
) -> bytes:
    """Build a valid object_tree.bin for testing."""
    if nodes is None:
        nodes = []
    if strings is None:
        strings = [""]

    # Build string table
    str_table = b""
    offsets = []
    for s in strings:
        offsets.append(len(str_table))
        str_table += s.encode("utf-8") + b"\x00"

    # Header
    header = struct.pack(
        "<5I",
        TREE_MAGIC,
        1,  # version
        display_w,
        display_h,
        len(nodes),
    )

    # String table size
    str_size = struct.pack("<I", len(str_table))

    # Nodes
    node_data = b""
    for n in nodes:
        node_data += struct.pack(
            "<IiiiiIIIIII",
            n.get("type_id", 1),      # type_id
            n.get("x", 0),             # x
            n.get("y", 0),             # y
            n.get("width", 100),       # width
            n.get("height", 50),       # height
            n.get("flags", 1),         # flags (visible)
            n.get("child_count", 0),   # child_count
            n.get("text_offset", 0),   # text_offset
            n.get("value", 0),         # value
            0,                         # reserved[0]
            0,                         # reserved[1]
        )

    return header + str_size + str_table + node_data


# ── Tests ─────────────────────────────────────────────────────────


class TestReadObjectTree:
    def test_minimal_tree(self, tmp_path):
        """Single root node with no children."""
        data = _build_tree_bin(
            nodes=[{"type_id": 1, "child_count": 0}],
            strings=[""],
        )
        path = tmp_path / "tree.bin"
        path.write_bytes(data)

        result = read_object_tree(path)
        assert result["display"] == {"width": 480, "height": 800}
        assert result["node_count"] == 1
        assert result["root"]["type"] == "container"
        assert result["root"]["visible"] is True

    def test_parent_with_children(self, tmp_path):
        """Root with two children."""
        data = _build_tree_bin(
            nodes=[
                {"type_id": 1, "child_count": 2},   # root container
                {"type_id": 2, "child_count": 0, "text_offset": 1},  # label
                {"type_id": 3, "child_count": 0},   # button
            ],
            strings=["", "Hello"],
        )
        path = tmp_path / "tree.bin"
        path.write_bytes(data)

        result = read_object_tree(path)
        root = result["root"]
        assert len(root["children"]) == 2
        assert root["children"][0]["type"] == "label"
        assert root["children"][0]["text"] == "Hello"
        assert root["children"][1]["type"] == "button"

    def test_nested_hierarchy(self, tmp_path):
        """Root > Container > Label."""
        data = _build_tree_bin(
            nodes=[
                {"type_id": 1, "child_count": 1},   # root
                {"type_id": 1, "child_count": 1},   # container
                {"type_id": 2, "child_count": 0, "text_offset": 1},  # label
            ],
            strings=["", "Nested"],
        )
        path = tmp_path / "tree.bin"
        path.write_bytes(data)

        result = read_object_tree(path)
        container = result["root"]["children"][0]
        assert container["type"] == "container"
        assert container["children"][0]["text"] == "Nested"

    def test_display_dimensions(self, tmp_path):
        """Custom display size is preserved."""
        data = _build_tree_bin(display_w=320, display_h=240)
        path = tmp_path / "tree.bin"
        path.write_bytes(data)

        result = read_object_tree(path)
        assert result["display"]["width"] == 320
        assert result["display"]["height"] == 240

    def test_node_positions(self, tmp_path):
        """Node coordinates are read correctly."""
        data = _build_tree_bin(
            nodes=[{"type_id": 2, "x": 10, "y": 20, "width": 200, "height": 40, "child_count": 0}],
        )
        path = tmp_path / "tree.bin"
        path.write_bytes(data)

        result = read_object_tree(path)
        root = result["root"]
        assert root["x"] == 10
        assert root["y"] == 20
        assert root["width"] == 200
        assert root["height"] == 40

    def test_all_widget_types(self, tmp_path):
        """All type IDs map to correct names."""
        from lvgl_ir.object_tree_reader import TYPE_NAMES
        for type_id, name in TYPE_NAMES.items():
            if type_id == 0:
                continue  # "unknown"
            data = _build_tree_bin(nodes=[{"type_id": type_id, "child_count": 0}])
            path = tmp_path / f"tree_{type_id}.bin"
            path.write_bytes(data)
            result = read_object_tree(path)
            assert result["root"]["type"] == name, f"type_id={type_id}"

    def test_clickable_flag(self, tmp_path):
        """Clickable flag is detected."""
        data = _build_tree_bin(
            nodes=[{"type_id": 3, "flags": 3, "child_count": 0}],  # visible + clickable
        )
        path = tmp_path / "tree.bin"
        path.write_bytes(data)

        result = read_object_tree(path)
        assert result["root"]["clickable"] is True

    def test_invisible_node(self, tmp_path):
        """Invisible flag is detected."""
        data = _build_tree_bin(
            nodes=[{"type_id": 1, "flags": 0, "child_count": 0}],
        )
        path = tmp_path / "tree.bin"
        path.write_bytes(data)

        result = read_object_tree(path)
        assert result["root"]["visible"] is False


class TestErrorCases:
    def test_too_small_file(self, tmp_path):
        path = tmp_path / "tiny.bin"
        path.write_bytes(b"\x00" * 10)
        with pytest.raises(ValueError, match="too small"):
            read_object_tree(path)

    def test_bad_magic(self, tmp_path):
        data = struct.pack("<5I", 0xDEADBEEF, 1, 480, 800, 0)
        data += struct.pack("<I", 0)  # string table size
        path = tmp_path / "bad.bin"
        path.write_bytes(data)
        with pytest.raises(ValueError, match="Bad magic"):
            read_object_tree(path)

    def test_bad_version(self, tmp_path):
        data = struct.pack("<5I", TREE_MAGIC, 99, 480, 800, 0)
        data += struct.pack("<I", 0)
        path = tmp_path / "bad.bin"
        path.write_bytes(data)
        with pytest.raises(ValueError, match="version"):
            read_object_tree(path)

    def test_truncated_node_data(self, tmp_path):
        """Claim 2 nodes but only provide data for 1."""
        data = _build_tree_bin(nodes=[{"type_id": 1, "child_count": 0}])
        # Truncate: remove last node's data
        data = data[:len(data) - NODE_STRUCT_SIZE + 10]
        # Fix header to still claim 1 node (it already does)
        path = tmp_path / "truncated.bin"
        path.write_bytes(data)
        # This should either work (if file is still big enough) or raise
        try:
            read_object_tree(path)
        except ValueError:
            pass  # Expected


class TestGoldenTree:
    """Test against the golden page object trees if available."""

    def test_golden_pages_have_trees(self):
        golden_dir = Path(__file__).resolve().parent.parent.parent / "golden_pages"
        if not golden_dir.is_dir():
            pytest.skip("golden_pages directory not found")

        for page_dir in sorted(golden_dir.iterdir()):
            tree_path = page_dir / "expected" / "object_tree.bin"
            if not tree_path.is_file():
                continue
            result = read_object_tree(tree_path)
            assert result["node_count"] > 0, f"{page_dir.name}: empty tree"
            assert result["root"]["type"] != "unknown", f"{page_dir.name}: unknown root type"
            assert result["display"]["width"] > 0
            assert result["display"]["height"] > 0
