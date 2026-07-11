"""Regression coverage for manifest-declared LVGL font handling."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from high_level_tools import _resolve_manifest_fonts, _write_user_font_bundle


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

    fonts, warnings = _resolve_manifest_fonts(tmp_path, design.resolve())
    assert warnings == []
    assert [(font["usage"], font["symbol"]) for font in fonts] == [
        ("top", "font_title"), ("title", "font_body"), ("hint", "font_caption"),
    ]

    header_name, cmake_path = _write_user_font_bundle(tmp_path / "out", fonts)
    assert header_name == "ui_interactive_scene_fonts.h"
    assert "extern const lv_font_t font_title;" in (tmp_path / "out" / header_name).read_text(encoding="utf-8")
    assert (tmp_path / "out" / "fonts" / "title.c").is_file()
    assert "fonts/title.c" in Path(cmake_path).read_text(encoding="utf-8")


def test_manifest_declared_missing_font_is_rejected(tmp_path: Path) -> None:
    design = tmp_path / "page.png"
    design.write_bytes(b"png")
    (tmp_path / "manifest.json").write_text(json.dumps({"pages": [{
        "design": "page.png",
        "fonts": {"title": "missing.c", "body": "missing.c", "caption": "missing.c"},
    }]}), encoding="utf-8")

    with pytest.raises(ValueError, match="fonts.title"):
        _resolve_manifest_fonts(tmp_path, design.resolve())
