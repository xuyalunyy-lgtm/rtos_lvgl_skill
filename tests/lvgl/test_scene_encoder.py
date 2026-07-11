"""Tests for scene encoder — UI Spec → scene.bin."""
import json
import struct
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "mcp"))

from lvgl_ir.scene_encoder import encode_spec, StringTable, CommandBuffer, Op


# ── StringTable ───────────────────────────────────────────────────


class TestStringTable:
    def test_empty(self):
        st = StringTable()
        assert st.add("") == 0
        assert len(st.strings) == 1

    def test_dedup(self):
        st = StringTable()
        idx1 = st.add("hello")
        idx2 = st.add("hello")
        assert idx1 == idx2
        assert len(st.strings) == 1

    def test_multiple(self):
        st = StringTable()
        st.add("a")
        st.add("b")
        st.add("c")
        assert len(st.strings) == 3

    def test_encode(self):
        st = StringTable()
        st.add("hi")
        encoded = st.encode()
        assert encoded == b"hi\x00"


# ── CommandBuffer ─────────────────────────────────────────────────


class TestCommandBuffer:
    def test_create_widget(self):
        st = StringTable()
        cb = CommandBuffer(st)
        cb.create_widget(Op.CREATE_LABEL, 1)
        cb.end()
        data = cb.encode()
        # header: opcode(2) + size(2) + node_id(4) = 8 bytes per command
        assert len(data) == 16  # create + end

    def test_set_text(self):
        st = StringTable()
        cb = CommandBuffer(st)
        cb.set_text(1, "hello")
        cb.end()
        data = cb.encode()
        # set_text command: header(8) + string_index(4) = 12 bytes
        assert len(data) == 20  # set_text + end
        # Verify string was added
        assert "hello" in st.strings


# ── encode_spec ───────────────────────────────────────────────────


class TestEncodeSpec:
    MINIMAL_SPEC = {
        "schema_version": "2.0",
        "page_name": "test",
        "display": {"width": 480, "height": 800},
        "lvgl_version": "v9",
        "nodes": [
            {"id": "root", "type": "screen"},
            {"id": "title", "type": "label", "parent_id": "root", "text": "Hello"},
        ],
    }

    def test_header_magic(self):
        data = encode_spec(self.MINIMAL_SPEC)
        magic = struct.unpack("<I", data[:4])[0]
        assert magic == 0x004E4353  # "SCN\0"

    def test_header_version(self):
        data = encode_spec(self.MINIMAL_SPEC)
        version = struct.unpack("<I", data[4:8])[0]
        assert version == 2

    def test_node_count(self):
        data = encode_spec(self.MINIMAL_SPEC)
        count = struct.unpack("<I", data[8:12])[0]
        assert count == 2

    def test_minimal_size(self):
        data = encode_spec(self.MINIMAL_SPEC)
        assert len(data) > 32  # at least header

    def test_empty_nodes(self):
        spec = {"schema_version": "2.0", "nodes": []}
        data = encode_spec(spec)
        count = struct.unpack("<I", data[8:12])[0]
        assert count == 0

    def test_complex_spec(self):
        spec = {
            "schema_version": "2.0",
            "page_name": "home",
            "display": {"width": 480, "height": 800},
            "lvgl_version": "v9",
            "theme": {"primary_color": "#2196F3", "background_color": "#FFFFFF"},
            "nodes": [
                {"id": "root", "type": "screen"},
                {"id": "header", "type": "container", "parent_id": "root",
                 "layout": {"mode": "flex-row", "gap": 10}},
                {"id": "title", "type": "label", "parent_id": "header", "text": "Home"},
                {"id": "btn", "type": "button", "parent_id": "header",
                 "styles": {"bg_color": "#2196F3", "radius": 12}},
                {"id": "content", "type": "container", "parent_id": "root"},
                {"id": "card", "type": "container", "parent_id": "content",
                 "styles": {"bg_color": "#F5F5FA", "radius": 8}},
            ],
        }
        data = encode_spec(spec)
        count = struct.unpack("<I", data[8:12])[0]
        assert count == 6


# ── Golden page specs ─────────────────────────────────────────────


class TestGoldenPageSpecs:
    """Verify all golden page specs can be encoded."""

    GOLDEN_DIR = ROOT / "golden_pages"

    @pytest.mark.parametrize("page_name", [
        d.name for d in GOLDEN_DIR.iterdir() if d.is_dir()
    ] if GOLDEN_DIR.exists() else [])
    def test_encode_golden_spec(self, page_name):
        spec_path = self.GOLDEN_DIR / page_name / "expected" / "ui_spec.json"
        if not spec_path.is_file():
            pytest.skip(f"No ui_spec.json for {page_name}")

        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        data = encode_spec(spec)

        # Verify basic structure
        assert len(data) > 32
        magic = struct.unpack("<I", data[:4])[0]
        assert magic == 0x004E4353
