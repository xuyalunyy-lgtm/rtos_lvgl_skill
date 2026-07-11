"""Tests for app-level C/H code generators (Router, Presenter, Model, App)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "mcp"))

from app_codegen import (
    generate_router_c,
    generate_router_h,
    generate_presenter_c,
    generate_presenter_h,
    generate_model_c,
    generate_model_h,
    generate_app_c,
    generate_app_h,
)

# ── Fixtures ───────────────────────────────────────────────────────

PAGES = [
    {"id": "home", "design": "d/home.png"},
    {"id": "detail", "design": "d/detail.png"},
    {"id": "settings", "design": "d/settings.png"},
]

ROUTES = [
    {"id": "home_to_detail", "from": "home", "to": "detail", "mode": "push", "event": "btn.clicked"},
    {"id": "detail_to_settings", "from": "detail", "to": "settings", "mode": "replace", "event": "btn.clicked"},
    {"id": "settings_back", "from": "settings", "mode": "back", "event": "btn.clicked"},
]

MODELS = [
    {
        "name": "favorites",
        "fields": [
            {"name": "is_favorited", "type": "bool", "default": False},
            {"name": "count", "type": "int32", "default": 0},
            {"name": "label", "type": "string", "max_length": 32, "default": ""},
        ],
    }
]

HOME_EVENTS = [
    {
        "node_id": "favorite_button",
        "trigger": "clicked",
        "actions": [
            {"type": "model_toggle", "target": "favorites.is_favorited"},
            {"type": "route", "route_id": "home_to_detail"},
        ],
    }
]


# ── Router ─────────────────────────────────────────────────────────


class TestRouterH:
    def test_contains_guard(self):
        code = generate_router_h("test_app", PAGES)
        assert "#ifndef UI_ROUTER_H" in code
        assert "#endif" in code

    def test_contains_page_enum(self):
        code = generate_router_h("test_app", PAGES)
        assert "PAGE_HOME" in code
        assert "PAGE_DETAIL" in code
        assert "PAGE_SETTINGS" in code
        assert "PAGE_COUNT" in code

    def test_contains_error_codes(self):
        code = generate_router_h("test_app", PAGES)
        assert "UI_ROUTER_OK" in code
        assert "UI_ROUTER_ERR_STACK_FULL" in code
        assert "UI_ROUTER_ERR_UNKNOWN_PAGE" in code
        assert "UI_ROUTER_ERR_NO_BACK" in code

    def test_contains_nav_functions(self):
        code = generate_router_h("test_app", PAGES)
        assert "ui_router_push" in code
        assert "ui_router_back" in code
        assert "ui_router_replace" in code


class TestRouterC:
    def test_contains_includes(self):
        code = generate_router_c("test_app", PAGES, ROUTES)
        assert '#include "ui_router.h"' in code

    def test_contains_factory_table(self):
        code = generate_router_c("test_app", PAGES, ROUTES)
        assert "PAGE_HOME" in code
        assert "ui_page_home_create" in code

    def test_push_implementation(self):
        code = generate_router_c("test_app", PAGES, ROUTES)
        assert "int ui_router_push" in code
        assert "LV_OBJ_FLAG_HIDDEN" in code

    def test_back_implementation(self):
        code = generate_router_c("test_app", PAGES, ROUTES)
        assert "int ui_router_back" in code
        assert "lv_obj_del" in code

    def test_replace_implementation(self):
        code = generate_router_c("test_app", PAGES, ROUTES)
        assert "int ui_router_replace" in code

    def test_max_depth(self):
        code = generate_router_c("test_app", PAGES, ROUTES, max_depth=4)
        assert "UI_ROUTER_MAX_DEPTH 4" in code


# ── Presenter ──────────────────────────────────────────────────────


class TestPresenterH:
    def test_contains_guard(self):
        code = generate_presenter_h("home")
        assert "#ifndef PRESENTER_HOME_H" in code

    def test_contains_bind_function(self):
        code = generate_presenter_h("home")
        assert "presenter_home_bind" in code


class TestPresenterC:
    def test_contains_bind_function(self):
        code = generate_presenter_c("home", HOME_EVENTS, ROUTES, MODELS)
        assert "presenter_home_bind" in code

    def test_contains_router_call(self):
        code = generate_presenter_c("home", HOME_EVENTS, ROUTES, MODELS)
        assert "ui_router_push" in code
        assert "PAGE_DETAIL" in code

    def test_contains_model_toggle(self):
        code = generate_presenter_c("home", HOME_EVENTS, ROUTES, MODELS)
        assert "model_favorites_get_is_favorited" in code
        assert "model_favorites_set_is_favorited" in code

    def test_empty_events(self):
        code = generate_presenter_c("empty", [], ROUTES, MODELS)
        assert "No event actions declared" in code or "No bindings" in code


# ── Model ──────────────────────────────────────────────────────────


class TestModelH:
    def test_contains_guard(self):
        code = generate_model_h("favorites", MODELS[0]["fields"])
        assert "#ifndef MODEL_FAVORITES_H" in code

    def test_contains_init_reset(self):
        code = generate_model_h("favorites", MODELS[0]["fields"])
        assert "model_favorites_init" in code
        assert "model_favorites_reset" in code

    def test_contains_bool_getter_setter(self):
        code = generate_model_h("favorites", MODELS[0]["fields"])
        assert "model_favorites_get_is_favorited" in code
        assert "model_favorites_set_is_favorited" in code

    def test_contains_int32_getter_setter(self):
        code = generate_model_h("favorites", MODELS[0]["fields"])
        assert "model_favorites_get_count" in code
        assert "model_favorites_set_count" in code
        assert "int32_t" in code

    def test_contains_string_getter_setter(self):
        code = generate_model_h("favorites", MODELS[0]["fields"])
        assert "model_favorites_get_label" in code
        assert "model_favorites_set_label" in code


class TestModelC:
    def test_contains_static_storage(self):
        code = generate_model_c("favorites", MODELS[0]["fields"])
        assert "static bool s_favorites_is_favorited" in code
        assert "static int32_t s_favorites_count" in code
        assert "static char s_favorites_label" in code

    def test_contains_init(self):
        code = generate_model_c("favorites", MODELS[0]["fields"])
        assert "void model_favorites_init" in code

    def test_contains_reset(self):
        code = generate_model_c("favorites", MODELS[0]["fields"])
        assert "void model_favorites_reset" in code

    def test_string_uses_strncpy(self):
        code = generate_model_c("favorites", MODELS[0]["fields"])
        assert "strncpy" in code
        assert "[33]" in code  # max_length 32 + 1

    def test_bool_default_false(self):
        code = generate_model_c("favorites", [{"name": "flag", "type": "bool", "default": False}])
        assert "= false" in code

    def test_bool_default_true(self):
        code = generate_model_c("favorites", [{"name": "flag", "type": "bool", "default": True}])
        assert "= true" in code

    def test_int32_default(self):
        code = generate_model_c("favorites", [{"name": "n", "type": "int32", "default": 42}])
        assert "= 42" in code


# ── App ────────────────────────────────────────────────────────────


class TestAppH:
    def test_contains_guard(self):
        code = generate_app_h("test_app")
        assert "#ifndef UI_APP_H" in code

    def test_contains_lifecycle(self):
        code = generate_app_h("test_app")
        assert "ui_app_start" in code
        assert "ui_app_deinit" in code
        assert "ui_app_post_event" in code

    def test_contains_event_struct(self):
        code = generate_app_h("test_app")
        assert "ui_app_event_t" in code
        assert "UI_APP_EVENT_NAVIGATE" in code


class TestAppC:
    def test_contains_includes(self):
        code = generate_app_c("test_app", "home", MODELS)
        assert '#include "ui_app.h"' in code
        assert '#include "ui_router.h"' in code
        assert '#include "model_favorites.h"' in code

    def test_contains_model_init(self):
        code = generate_app_c("test_app", "home", MODELS)
        assert "model_favorites_init" in code

    def test_contains_model_reset(self):
        code = generate_app_c("test_app", "home", MODELS)
        assert "model_favorites_reset" in code

    def test_contains_router_init(self):
        code = generate_app_c("test_app", "home", MODELS)
        assert "ui_router_init" in code
        assert "PAGE_HOME" in code

    def test_contains_async_dispatch(self):
        code = generate_app_c("test_app", "home", MODELS)
        assert "lv_async_call" in code
        assert "lv_malloc" in code

    def test_contains_deinit(self):
        code = generate_app_c("test_app", "home", MODELS)
        assert "ui_router_deinit" in code


# ── Integration: generate_app_mvp with fixture ─────────────────────


class TestGenerateAppMvp:
    def test_generates_all_files(self, tmp_path):
        """Integration: app codegen produces all expected C/H files from resolved manifest."""
        import json
        from mcp.app_codegen import (
            generate_router_c, generate_router_h,
            generate_presenter_c, generate_presenter_h,
            generate_model_c, generate_model_h,
            generate_app_c, generate_app_h,
        )
        from mcp.manifest_v2 import validate_manifest, resolve_manifest

        # Minimal v2 manifest
        manifest = {
            "schema_version": "2.0",
            "app": {"id": "test_app", "entry_page": "home",
                    "navigation": {"mode": "stack", "max_depth": 8}},
            "display": {"width": 480, "height": 800, "color_format": "RGB565"},
            "shared": {"assets": {}, "fonts": {}},
            "models": [
                {"name": "prefs", "fields": [
                    {"name": "dark_mode", "type": "bool", "default": False},
                ]},
            ],
            "pages": [
                {"id": "home", "design": "d/home.png",
                 "states": ["default"], "state_designs": {"default": "d/home.png"},
                 "events": [
                     {"node_id": "btn", "trigger": "clicked",
                      "actions": [{"type": "model_toggle", "target": "prefs.dark_mode"},
                                  {"type": "route", "route_id": "r1"}]},
                 ]},
                {"id": "detail", "design": "d/detail.png",
                 "states": ["default"], "state_designs": {"default": "d/detail.png"},
                 "events": []},
                {"id": "settings", "design": "d/settings.png",
                 "states": ["default"], "state_designs": {"default": "d/settings.png"},
                 "events": [
                     {"node_id": "back_btn", "trigger": "clicked",
                      "actions": [{"type": "route", "route_id": "r3"}]},
                 ]},
            ],
            "routes": [
                {"id": "r1", "from": "home", "to": "detail", "mode": "push", "event": "btn.clicked"},
                {"id": "r2", "from": "detail", "to": "settings", "mode": "replace", "event": "btn.clicked"},
                {"id": "r3", "from": "settings", "mode": "back", "event": "back_btn.clicked"},
            ],
        }

        validation = validate_manifest(manifest)
        assert validation["ok"], f"Validation failed: {validation['errors']}"
        resolved = resolve_manifest(manifest)

        pages = resolved["pages"]
        routes = resolved["routes"]
        models = resolved["models"]
        app_id = resolved["app"]["id"]

        out = tmp_path / "app_out"
        out.mkdir()

        # Generate all files
        (out / "ui_router.c").write_text(generate_router_c(app_id, pages, routes))
        (out / "ui_router.h").write_text(generate_router_h(app_id, pages))
        (out / "ui_app.c").write_text(generate_app_c(app_id, "home", models))
        (out / "ui_app.h").write_text(generate_app_h(app_id))

        for page in pages:
            pid = page["id"]
            (out / f"presenter_{pid}.c").write_text(
                generate_presenter_c(pid, page.get("events", []), routes, models))
            (out / f"presenter_{pid}.h").write_text(generate_presenter_h(pid))

        for model in models:
            mname = model["name"]
            (out / f"model_{mname}.c").write_text(generate_model_c(mname, model["fields"]))
            (out / f"model_{mname}.h").write_text(generate_model_h(mname, model["fields"]))

        # Verify all files exist
        expected = [
            "ui_router.c", "ui_router.h", "ui_app.c", "ui_app.h",
            "presenter_home.c", "presenter_home.h",
            "presenter_detail.c", "presenter_detail.h",
            "presenter_settings.c", "presenter_settings.h",
            "model_prefs.c", "model_prefs.h",
        ]
        for name in expected:
            assert (out / name).is_file(), f"Missing: {name}"

        # Verify content correctness
        router_c = (out / "ui_router.c").read_text()
        assert "PAGE_HOME" in router_c
        assert "ui_router_push" in router_c
        assert "ui_router_back" in router_c

        app_c = (out / "ui_app.c").read_text()
        assert "model_prefs_init" in app_c
        assert "PAGE_HOME" in app_c
        assert "lv_async_call" in app_c

        pres_c = (out / "presenter_home.c").read_text()
        assert "model_prefs_get_dark_mode" in pres_c
        assert "ui_router_push" in pres_c


def _create_minimal_png(path: Path):
    """Create a 1x1 white PNG."""
    import struct
    import zlib
    def chunk(kind: bytes, payload: bytes) -> bytes:
        crc = zlib.crc32(kind + payload) & 0xFFFFFFFF
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", crc)
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    raw = b"\x00\xff\xff\xff"
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))
