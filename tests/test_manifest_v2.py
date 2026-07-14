"""Tests for Manifest v2 — validation, resolution, and v1 passthrough."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Add mcp/ to path so we can import modules directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "mcp"))

from manifest_v2 import load_manifest, validate_manifest, resolve_manifest


FIXTURES = Path(__file__).resolve().parent / "fixtures"


# ── Helpers ────────────────────────────────────────────────────────


def _minimal_v2(**overrides) -> dict:
    """Return a minimal valid v2 manifest, with optional overrides."""
    manifest = {
        "schema_version": "2.0",
        "app": {
            "id": "test_app",
            "entry_page": "home",
            "navigation": {"mode": "stack", "max_depth": 8},
        },
        "display": {"width": 480, "height": 800, "color_format": "RGB565"},
        "shared": {"assets": {}, "fonts": {}},
        "models": [],
        "pages": [
            {
                "id": "home",
                "design": "designs/home.png",
                "states": ["default"],
                "state_designs": {"default": "designs/home.png"},
                "events": [],
            }
        ],
        "routes": [],
    }
    manifest.update(overrides)
    return manifest


# ── load_manifest ──────────────────────────────────────────────────


class TestLoadManifest:
    def test_load_from_dict(self):
        m = _minimal_v2()
        result = load_manifest(m)
        assert result["schema_version"] == "2.0"

    def test_load_from_file(self):
        path = FIXTURES / "manifest_v2_mvp.json"
        if not path.exists():
            pytest.skip("fixture not available")
        result = load_manifest(path)
        assert result["schema_version"] == "2.0"
        assert result["app"]["id"] == "affirmation_app"

    def test_load_missing_file(self):
        with pytest.raises(FileNotFoundError):
            load_manifest("/nonexistent/manifest.json")

    def test_v1_passthrough(self):
        v1 = {"schema_version": "1.0", "pages": [{"id": "page1"}]}
        result = load_manifest(v1)
        assert result["schema_version"] == "1.0"


# ── validate_manifest — v1 passthrough ─────────────────────────────


class TestValidateV1:
    def test_v1_passes(self):
        result = validate_manifest({"schema_version": "1.0", "pages": []})
        assert result["ok"] is True
        assert result["version"] == "1.0"

    def test_v1_no_validation(self):
        """v1 should not trigger v2 structural checks."""
        result = validate_manifest({"schema_version": "1.0"})
        assert result["ok"] is True


# ── validate_manifest — schema_version ─────────────────────────────


class TestSchemaVersion:
    def test_v2_valid(self):
        result = validate_manifest(_minimal_v2())
        assert result["ok"] is True
        assert result["version"] == "2.0"

    def test_unsupported_version(self):
        result = validate_manifest({"schema_version": "3.0"})
        assert result["ok"] is False
        assert any("Unsupported" in e for e in result["errors"])

    def test_resolve_v21_preserves_state_map(self):
        manifest = {
            "schema_version": "2.1",
            "pages": [{
                "id": "home",
                "states": {"default": {"design": "designs/home.png"}},
            }],
        }
        resolved = resolve_manifest(manifest)
        assert resolved["pages"][0]["states"] == manifest["pages"][0]["states"]

    def test_not_dict(self):
        result = validate_manifest("not a dict")
        assert result["ok"] is False


# ── validate_manifest — app block ──────────────────────────────────


class TestAppBlock:
    def test_missing_app(self):
        m = _minimal_v2()
        del m["app"]
        result = validate_manifest(m)
        assert result["ok"] is False
        assert any("app" in e for e in result["errors"])

    def test_empty_app_id(self):
        m = _minimal_v2(app={"id": "", "entry_page": "home"})
        result = validate_manifest(m)
        assert result["ok"] is False
        assert any("app.id" in e for e in result["errors"])

    def test_non_snake_case_id(self):
        m = _minimal_v2(app={"id": "MyApp", "entry_page": "home"})
        result = validate_manifest(m)
        assert result["ok"] is False
        assert any("snake_case" in e for e in result["errors"])

    def test_missing_entry_page(self):
        m = _minimal_v2(app={"id": "test_app"})
        result = validate_manifest(m)
        assert result["ok"] is False
        assert any("entry_page" in e for e in result["errors"])

    def test_entry_page_not_in_pages(self):
        m = _minimal_v2(app={"id": "test_app", "entry_page": "nonexistent"})
        result = validate_manifest(m)
        assert result["ok"] is False
        assert any("nonexistent" in e for e in result["errors"])


# ── validate_manifest — pages ──────────────────────────────────────


class TestPages:
    def test_empty_pages(self):
        m = _minimal_v2(pages=[])
        result = validate_manifest(m)
        assert result["ok"] is False
        assert any("pages" in e for e in result["errors"])

    def test_duplicate_page_id(self):
        m = _minimal_v2(pages=[
            {"id": "home", "design": "a.png", "states": ["default"], "state_designs": {"default": "a.png"}},
            {"id": "home", "design": "b.png", "states": ["default"], "state_designs": {"default": "b.png"}},
        ])
        result = validate_manifest(m)
        assert result["ok"] is False
        assert any("Duplicate page" in e for e in result["errors"])

    def test_page_missing_design(self):
        m = _minimal_v2(pages=[
            {"id": "home", "states": ["default"], "state_designs": {"default": "a.png"}},
        ])
        result = validate_manifest(m)
        assert result["ok"] is False
        assert any("design" in e for e in result["errors"])

    def test_states_missing_default(self):
        m = _minimal_v2(pages=[
            {"id": "home", "design": "a.png", "states": ["active"], "state_designs": {"active": "a.png"}},
        ])
        result = validate_manifest(m)
        assert result["ok"] is False
        assert any("default" in e for e in result["errors"])

    def test_state_designs_missing_state(self):
        m = _minimal_v2(pages=[
            {"id": "home", "design": "a.png", "states": ["default", "loading"],
             "state_designs": {"default": "a.png"}},
        ])
        result = validate_manifest(m)
        assert result["ok"] is False
        assert any("loading" in e for e in result["errors"])


# ── validate_manifest — routes ─────────────────────────────────────


class TestRoutes:
    def test_valid_push_route(self):
        m = _minimal_v2(pages=[
            {"id": "home", "design": "a.png", "states": ["default"], "state_designs": {"default": "a.png"}},
            {"id": "detail", "design": "b.png", "states": ["default"], "state_designs": {"default": "b.png"}},
        ], routes=[
            {"id": "r1", "from": "home", "to": "detail", "mode": "push", "event": "btn.clicked"},
        ])
        result = validate_manifest(m)
        assert result["ok"] is True

    def test_back_route_no_to(self):
        m = _minimal_v2(pages=[
            {"id": "home", "design": "a.png", "states": ["default"], "state_designs": {"default": "a.png"}},
        ], routes=[
            {"id": "r1", "from": "home", "mode": "back", "event": "btn.clicked"},
        ])
        result = validate_manifest(m)
        assert result["ok"] is True

    def test_back_route_with_to_fails(self):
        m = _minimal_v2(pages=[
            {"id": "home", "design": "a.png", "states": ["default"], "state_designs": {"default": "a.png"}},
        ], routes=[
            {"id": "r1", "from": "home", "to": "home", "mode": "back", "event": "btn.clicked"},
        ])
        result = validate_manifest(m)
        assert result["ok"] is False
        assert any("back" in e for e in result["errors"])

    def test_invalid_from_page(self):
        m = _minimal_v2(routes=[
            {"id": "r1", "from": "nonexistent", "to": "home", "mode": "push", "event": "x"},
        ])
        result = validate_manifest(m)
        assert result["ok"] is False
        assert any("nonexistent" in e for e in result["errors"])

    def test_invalid_mode(self):
        m = _minimal_v2(pages=[
            {"id": "home", "design": "a.png", "states": ["default"], "state_designs": {"default": "a.png"}},
        ], routes=[
            {"id": "r1", "from": "home", "to": "home", "mode": "navigate", "event": "x"},
        ])
        result = validate_manifest(m)
        assert result["ok"] is False
        assert any("mode" in e for e in result["errors"])

    def test_duplicate_route_id(self):
        m = _minimal_v2(pages=[
            {"id": "home", "design": "a.png", "states": ["default"], "state_designs": {"default": "a.png"}},
        ], routes=[
            {"id": "r1", "from": "home", "mode": "back", "event": "x"},
            {"id": "r1", "from": "home", "mode": "back", "event": "y"},
        ])
        result = validate_manifest(m)
        assert result["ok"] is False
        assert any("Duplicate route" in e for e in result["errors"])


# ── validate_manifest — models ─────────────────────────────────────


class TestModels:
    def test_valid_model(self):
        m = _minimal_v2(models=[
            {"name": "prefs", "fields": [
                {"name": "dark_mode", "type": "bool", "default": False},
                {"name": "count", "type": "int32", "default": 0},
                {"name": "username", "type": "string", "max_length": 32, "default": ""},
            ]},
        ])
        result = validate_manifest(m)
        assert result["ok"] is True

    def test_string_missing_max_length(self):
        m = _minimal_v2(models=[
            {"name": "m", "fields": [
                {"name": "s", "type": "string", "default": ""},
            ]},
        ])
        result = validate_manifest(m)
        assert result["ok"] is False
        assert any("max_length" in e for e in result["errors"])

    def test_bool_missing_default(self):
        m = _minimal_v2(models=[
            {"name": "m", "fields": [
                {"name": "b", "type": "bool"},
            ]},
        ])
        result = validate_manifest(m)
        assert result["ok"] is False
        assert any("default" in e for e in result["errors"])

    def test_invalid_field_type(self):
        m = _minimal_v2(models=[
            {"name": "m", "fields": [
                {"name": "x", "type": "float64", "default": 0},
            ]},
        ])
        result = validate_manifest(m)
        assert result["ok"] is False
        assert any("float64" in e for e in result["errors"])

    def test_duplicate_model_name(self):
        m = _minimal_v2(models=[
            {"name": "m", "fields": [{"name": "a", "type": "bool", "default": False}]},
            {"name": "m", "fields": [{"name": "b", "type": "int32", "default": 0}]},
        ])
        result = validate_manifest(m)
        assert result["ok"] is False
        assert any("Duplicate model" in e for e in result["errors"])


# ── validate_manifest — event actions ──────────────────────────────


class TestEventActions:
    def test_route_action_refs_unknown_route(self):
        m = _minimal_v2(events=[
            {"node_id": "btn", "trigger": "clicked", "actions": [
                {"type": "route", "route_id": "nonexistent"},
            ]},
        ])
        # Need routes defined on the page's event, not top-level
        m["pages"][0]["events"] = m.pop("events")
        result = validate_manifest(m)
        assert result["ok"] is False
        assert any("nonexistent" in e for e in result["errors"])

    def test_model_toggle_refs_unknown_model(self):
        m = _minimal_v2()
        m["pages"][0]["events"] = [
            {"node_id": "btn", "trigger": "clicked", "actions": [
                {"type": "model_toggle", "target": "unknown.flag"},
            ]},
        ]
        result = validate_manifest(m)
        assert result["ok"] is False
        assert any("unknown" in e for e in result["errors"])

    def test_model_toggle_refs_unknown_field(self):
        m = _minimal_v2(models=[
            {"name": "prefs", "fields": [{"name": "dark", "type": "bool", "default": False}]},
        ])
        m["pages"][0]["events"] = [
            {"node_id": "btn", "trigger": "clicked", "actions": [
                {"type": "model_toggle", "target": "prefs.nonexistent"},
            ]},
        ]
        result = validate_manifest(m)
        assert result["ok"] is False
        assert any("nonexistent" in e for e in result["errors"])

    def test_set_state_refs_unknown_state(self):
        m = _minimal_v2()
        m["pages"][0]["events"] = [
            {"node_id": "btn", "trigger": "clicked", "actions": [
                {"type": "set_state", "state": "nonexistent"},
            ]},
        ]
        result = validate_manifest(m)
        assert result["ok"] is False
        assert any("nonexistent" in e for e in result["errors"])

    def test_model_set_missing_dot(self):
        m = _minimal_v2(models=[
            {"name": "prefs", "fields": [{"name": "dark", "type": "bool", "default": False}]},
        ])
        m["pages"][0]["events"] = [
            {"node_id": "btn", "trigger": "clicked", "actions": [
                {"type": "model_set", "target": "prefs_dark"},
            ]},
        ]
        result = validate_manifest(m)
        assert result["ok"] is False
        assert any("model.field" in e for e in result["errors"])


# ── resolve_manifest ───────────────────────────────────────────────


class TestResolveManifest:
    def test_shared_assets_inherited(self):
        m = _minimal_v2(
            shared={"assets": {"icon_back": "icons/back.png"}, "fonts": {"body": "fonts/body.c"}},
            pages=[{
                "id": "home",
                "design": "a.png",
                "states": ["default"],
                "state_designs": {"default": "a.png"},
            }],
        )
        resolved = resolve_manifest(m)
        page = resolved["pages"][0]
        assert page["assets"]["icon_back"] == "icons/back.png"
        assert page["fonts"]["body"] == "fonts/body.c"

    def test_page_overrides_shared(self):
        m = _minimal_v2(
            shared={"assets": {"icon": "shared.png"}, "fonts": {"body": "shared.c"}},
            pages=[{
                "id": "home",
                "design": "a.png",
                "states": ["default"],
                "state_designs": {"default": "a.png"},
                "assets": {"icon": "page.png"},
                "fonts": {"body": "page.c"},
            }],
        )
        resolved = resolve_manifest(m)
        page = resolved["pages"][0]
        assert page["assets"]["icon"] == "page.png"
        assert page["fonts"]["body"] == "page.c"

    def test_default_state_added(self):
        m = _minimal_v2(pages=[{
            "id": "home",
            "design": "a.png",
        }])
        resolved = resolve_manifest(m)
        assert resolved["pages"][0]["states"] == ["default"]

    def test_does_not_mutate_input(self):
        m = _minimal_v2(shared={"assets": {"x": "y"}})
        original = json.dumps(m)
        resolve_manifest(m)
        assert json.dumps(m) == original


# ── Integration: MVP fixture ───────────────────────────────────────


class TestMVPFixture:
    @pytest.fixture
    def mvp(self):
        path = FIXTURES / "manifest_v2_mvp.json"
        return load_manifest(path)

    def test_loads(self, mvp):
        assert mvp["schema_version"] == "2.0"
        assert mvp["app"]["id"] == "affirmation_app"

    def test_validates(self, mvp):
        result = validate_manifest(mvp)
        assert result["ok"] is True, f"Errors: {result['errors']}"

    def test_resolves_shared(self, mvp):
        resolved = resolve_manifest(mvp)
        for page in resolved["pages"]:
            assert "icon_back" in page["assets"]
            assert "body" in page["fonts"]

    def test_three_pages(self, mvp):
        assert len(mvp["pages"]) == 3
        ids = {p["id"] for p in mvp["pages"]}
        assert ids == {"home", "detail", "settings"}

    def test_three_routes(self, mvp):
        assert len(mvp["routes"]) == 3
        modes = {r["mode"] for r in mvp["routes"]}
        assert modes == {"push", "replace", "back"}

    def test_model_with_bool_field(self, mvp):
        assert len(mvp["models"]) == 1
        fav = mvp["models"][0]
        assert fav["name"] == "favorites"
        assert fav["fields"][0]["type"] == "bool"
