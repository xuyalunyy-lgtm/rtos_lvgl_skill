"""Regression coverage for manifest-declared LVGL font handling."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from high_level_tools import _apply_manifest_fonts_to_spec, _native_font_bindings, _resolve_manifest_fonts, _write_user_font_bundle
from lvgl_codegen import generate_page_code


def _write_font(path: Path, symbol: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f'#include "lvgl.h"\nconst lv_font_t {symbol} = {{0}};\n', encoding="utf-8")


def test_manifest_fonts_are_resolved_and_bundled(tmp_path: Path) -> None:
    design = tmp_path / "design" / "page.png"
    design.parent.mkdir()
    design.write_bytes(b"png")
    _write_font(tmp_path / "fonts" / "title.c", "font_title")
    _write_font(tmp_path / "fonts" / "body.c", "font_body")
    _write_font(tmp_path / "fonts" / "caption.c", "font_caption")
    (tmp_path / "manifest.json").write_text(json.dumps({"pages": [{
        "design": "design/page.png",
        "template": "interactive_scene",
        "fonts": {"title": "fonts/title.c", "body": "fonts/body.c", "caption": "fonts/caption.c"},
    }]}), encoding="utf-8")

    fonts, warnings = _resolve_manifest_fonts(tmp_path, design.resolve(), page_name="page")
    assert warnings == []
    assert [(font["role"], font["symbol"]) for font in fonts] == [
        ("title", "font_title"), ("body", "font_body"), ("caption", "font_caption"),
    ]

    bundle = _write_user_font_bundle(tmp_path / "out", fonts, "page")
    assert bundle["header"] == "ui_page_fonts.h"
    assert "extern const lv_font_t font_title;" in (tmp_path / "out" / bundle["header"]).read_text(encoding="utf-8")
    assert (tmp_path / "out" / "fonts" / "title.c").is_file()
    assert "fonts/title.c" in Path(bundle["cmake_path"]).read_text(encoding="utf-8")


def test_manifest_declared_missing_font_is_rejected(tmp_path: Path) -> None:
    design = tmp_path / "page.png"
    design.write_bytes(b"png")
    (tmp_path / "manifest.json").write_text(json.dumps({"pages": [{
        "id": "page",
        "design": "page.png",
        "fonts": {"title": "missing.c", "body": "missing.c", "caption": "missing.c"},
    }]}), encoding="utf-8")

    with pytest.raises(ValueError, match="fonts.title"):
        _resolve_manifest_fonts(tmp_path, design.resolve(), page_name="page")


def test_manifest_font_roles_reach_generic_lvgl_code() -> None:
    spec = {
        "schema_version": "2.0",
        "page_name": "generic",
        "display": {"width": 480, "height": 800},
        "lvgl_version": "v9",
        "nodes": [
            {"id": "root", "type": "screen"},
            {"id": "page_title", "type": "label", "parent_id": "root", "text": "Title"},
            {"id": "body_copy", "type": "label", "parent_id": "root", "text": "Body"},
            {"id": "caption_hint", "type": "label", "parent_id": "root", "text": "Hint"},
        ],
    }
    fonts = [
        {"role": "title", "symbol": "font_title", "source": "title.c"},
        {"role": "body", "symbol": "font_body", "source": "body.c"},
        {"role": "caption", "symbol": "font_caption", "source": "caption.c"},
    ]
    _apply_manifest_fonts_to_spec(spec, fonts, {"header": "ui_generic_fonts.h", "cmake_path": "fonts.cmake"})
    result = generate_page_code(spec)

    assert result["ok"] is True
    assert '#include "ui_generic_fonts.h"' in result["c_code"]
    assert "lv_obj_set_style_text_font(s_page_title, &font_title, 0);" in result["c_code"]
    assert "lv_obj_set_style_text_font(s_body_copy, &font_body, 0);" in result["c_code"]
    assert "lv_obj_set_style_text_font(s_caption_hint, &font_caption, 0);" in result["c_code"]


def test_native_fonts_require_bin_preview_resources(tmp_path: Path) -> None:
    preview = tmp_path / "title.bin"
    preview.write_bytes(b"binfont")
    spec = {
        "nodes": [{"id": "title", "type": "label", "styles": {"font_id": "font_title"}}],
        "fonts": [{"symbol": "font_title", "preview_bin": str(preview)}],
    }
    bindings, missing = _native_font_bindings(spec)
    assert bindings == {"font_title": str(preview)}
    assert missing == []

    spec["nodes"].append({"id": "body", "type": "label", "styles": {"font_id": "font_body"}})
    bindings, missing = _native_font_bindings(spec)
    assert bindings == {"font_title": str(preview)}
    assert missing == ["font_body"]
