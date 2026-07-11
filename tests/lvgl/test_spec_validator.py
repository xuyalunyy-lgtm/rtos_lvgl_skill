"""Tests for UI Spec v2 validator."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Add mcp/ to path so we can import modules directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "mcp"))

from lvgl_ir.spec_validator import validate_spec


# ── Fixtures ──────────────────────────────────────────────────────


def _minimal_spec(**overrides) -> dict:
    """Return a minimal valid spec, with optional overrides."""
    spec = {
        "schema_version": "2.0",
        "page_name": "test_page",
        "display": {"width": 480, "height": 800},
        "lvgl_version": "v9",
        "nodes": [
            {"id": "root", "type": "screen"},
            {
                "id": "label_hello",
                "type": "label",
                "parent_id": "root",
                "text": "Hello",
                "source_bbox": [10, 10, 200, 40],
            },
        ],
    }
    spec.update(overrides)
    return spec


# ── Schema version ────────────────────────────────────────────────


class TestSchemaVersion:
    def test_valid_version(self):
        result = validate_spec(_minimal_spec())
        assert result["valid"] is True
        assert result["status"] == "generated"

    def test_missing_version(self):
        spec = _minimal_spec()
        del spec["schema_version"]
        result = validate_spec(spec)
        assert result["valid"] is False
        assert any("schema_version" in e for e in result["errors"])

    def test_wrong_version(self):
        result = validate_spec(_minimal_spec(schema_version="1.0"))
        assert result["valid"] is False


# ── Node IDs ──────────────────────────────────────────────────────


class TestNodeIDs:
    def test_unique_ids_valid(self):
        result = validate_spec(_minimal_spec())
        assert result["valid"] is True

    def test_duplicate_ids_rejected(self):
        spec = _minimal_spec()
        spec["nodes"].append({"id": "label_hello", "type": "label", "parent_id": "root"})
        result = validate_spec(spec)
        assert result["valid"] is False
        assert any("Duplicate" in e for e in result["errors"])

    def test_empty_id_rejected(self):
        spec = _minimal_spec()
        spec["nodes"].append({"id": "", "type": "label", "parent_id": "root"})
        result = validate_spec(spec)
        assert result["valid"] is False


# ── Root node ─────────────────────────────────────────────────────


class TestRootNode:
    def test_no_screen_node(self):
        spec = _minimal_spec()
        spec["nodes"] = [{"id": "a", "type": "label"}]
        result = validate_spec(spec)
        assert result["valid"] is False
        assert any("root" in e.lower() or "screen" in e.lower() for e in result["errors"])

    def test_multiple_screen_nodes(self):
        spec = _minimal_spec()
        spec["nodes"].append({"id": "root2", "type": "screen"})
        result = validate_spec(spec)
        assert result["valid"] is False
        assert any("Multiple root" in e for e in result["errors"])

    def test_root_with_parent_rejected(self):
        spec = _minimal_spec()
        spec["nodes"][0]["parent_id"] = "something"
        result = validate_spec(spec)
        assert result["valid"] is False
        assert any("must not have a parent_id" in e for e in result["errors"])


# ── Parent chain ──────────────────────────────────────────────────


class TestParentChain:
    def test_valid_chain(self):
        result = validate_spec(_minimal_spec())
        assert result["valid"] is True

    def test_disconnected_node(self):
        spec = _minimal_spec()
        spec["nodes"].append({"id": "orphan", "type": "label", "parent_id": "nonexistent"})
        result = validate_spec(spec)
        assert result["valid"] is False
        assert any("does not reach root" in e for e in result["errors"])

    def test_cycle_detected(self):
        spec = _minimal_spec()
        spec["nodes"].append({"id": "a", "type": "container", "parent_id": "b"})
        spec["nodes"].append({"id": "b", "type": "container", "parent_id": "a"})
        result = validate_spec(spec)
        assert result["valid"] is False
        assert any("does not reach root" in e for e in result["errors"])

    def test_no_parent_rejected(self):
        spec = _minimal_spec()
        spec["nodes"].append({"id": "noparent", "type": "label"})
        result = validate_spec(spec)
        assert result["valid"] is False
        assert any("no parent_id" in e for e in result["errors"])


# ── Minimum children ──────────────────────────────────────────────


class TestMinChildren:
    def test_root_only_rejected(self):
        spec = _minimal_spec()
        spec["nodes"] = [{"id": "root", "type": "screen"}]
        result = validate_spec(spec)
        assert result["valid"] is False
        assert any("at least one child" in e.lower() for e in result["errors"])

    def test_one_child_ok(self):
        result = validate_spec(_minimal_spec())
        assert result["valid"] is True


# ── source_bbox ───────────────────────────────────────────────────


class TestSourceBbox:
    def test_valid_bbox(self):
        result = validate_spec(_minimal_spec())
        assert result["valid"] is True

    def test_negative_size_rejected(self):
        spec = _minimal_spec()
        spec["nodes"][1]["source_bbox"] = [10, 10, -5, 40]
        result = validate_spec(spec)
        assert result["valid"] is False
        assert any("positive" in e for e in result["errors"])

    def test_zero_size_rejected(self):
        spec = _minimal_spec()
        spec["nodes"][1]["source_bbox"] = [10, 10, 0, 40]
        result = validate_spec(spec)
        assert result["valid"] is False

    def test_out_of_bounds_warning(self):
        spec = _minimal_spec()
        spec["nodes"][1]["source_bbox"] = [0, 0, 800, 1600]
        result = validate_spec(spec)
        # Should warn but not fail
        assert len(result["warnings"]) > 0

    def test_wrong_length_rejected(self):
        spec = _minimal_spec()
        spec["nodes"][1]["source_bbox"] = [10, 10, 40]
        result = validate_spec(spec)
        assert result["valid"] is False


# ── Image src resolution ─────────────────────────────────────────


class TestImageSrc:
    def test_image_without_src_warns(self):
        spec = _minimal_spec()
        spec["nodes"].append({"id": "pic", "type": "image", "parent_id": "root"})
        result = validate_spec(spec)
        assert any("no src" in w for w in result["warnings"])


# ── LVGL version ─────────────────────────────────────────────────


class TestLvglVersion:
    def test_matching_version(self):
        result = validate_spec(_minimal_spec(), expected_lvgl_version="v9")
        assert result["valid"] is True

    def test_mismatched_version(self):
        result = validate_spec(
            _minimal_spec(lvgl_version="v8"), expected_lvgl_version="v9"
        )
        assert result["valid"] is False
        assert any("mismatch" in e.lower() for e in result["errors"])


# ── Edge cases ────────────────────────────────────────────────────


class TestEdgeCases:
    def test_not_a_dict(self):
        result = validate_spec("not a dict")  # type: ignore[arg-type]
        assert result["valid"] is False

    def test_empty_dict(self):
        result = validate_spec({})
        assert result["valid"] is False

    def test_none_input(self):
        result = validate_spec(None)  # type: ignore[arg-type]
        assert result["valid"] is False
