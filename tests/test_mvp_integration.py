"""End-to-end integration test for multi-page MVP pipeline.

Exercises: manifest → validate → resolve → codegen → validate_app → evidence.
Uses the 3-page MVP fixture (home→detail→settings, push/replace/back, favorites model).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "mcp"))

from manifest_v2 import load_manifest, validate_manifest, resolve_manifest
from app_codegen import (
    generate_router_c, generate_router_h,
    generate_presenter_c, generate_presenter_h,
    generate_model_c, generate_model_h,
    generate_app_c, generate_app_h,
)
from app_validator import validate_app


FIXTURES = Path(__file__).resolve().parent / "fixtures"
MVP_MANIFEST = FIXTURES / "manifest_v2_mvp.json"


# ── Helpers ────────────────────────────────────────────────────────


def _generate_app_scaffold(resolved: dict) -> dict[str, str]:
    """Generate all app-level C/H files from a resolved manifest.

    Returns {relative_path: content} dict.
    """
    files: dict[str, str] = {}
    app_id = resolved["app"]["id"]
    entry_page = resolved["app"]["entry_page"]
    pages = resolved.get("pages", [])
    routes = resolved.get("routes", [])
    models = resolved.get("models", [])
    max_depth = resolved.get("app", {}).get("navigation", {}).get("max_depth", 8)

    # Router
    files["app/ui_router.c"] = generate_router_c(app_id, pages, routes, max_depth)
    files["app/ui_router.h"] = generate_router_h(app_id, pages, max_depth)

    # App
    files["app/ui_app.c"] = generate_app_c(app_id, entry_page, models)
    files["app/ui_app.h"] = generate_app_h(app_id)

    # Presenters
    for page in pages:
        pid = page["id"]
        files[f"presenters/presenter_{pid}.c"] = generate_presenter_c(
            pid, page.get("events", []), routes, models)
        files[f"presenters/presenter_{pid}.h"] = generate_presenter_h(pid)

    # Models
    for model in models:
        mname = model["name"]
        files[f"models/model_{mname}.c"] = generate_model_c(mname, model["fields"])
        files[f"models/model_{mname}.h"] = generate_model_h(mname, model["fields"])

    return files


# ── Full pipeline: MVP fixture ─────────────────────────────────────


class TestMVPPipeline:
    """End-to-end: load → validate → resolve → codegen → validate_app."""

    @pytest.fixture
    def resolved(self):
        manifest = load_manifest(MVP_MANIFEST)
        result = validate_manifest(manifest)
        assert result["ok"], f"Validation failed: {result['errors']}"
        return resolve_manifest(manifest)

    @pytest.fixture
    def files(self, resolved):
        return _generate_app_scaffold(resolved)

    @pytest.fixture
    def validation(self, resolved, files):
        return validate_app(resolved, files)

    # ── Manifest ──

    def test_manifest_loads(self, resolved):
        assert resolved["schema_version"] == "2.0"
        assert resolved["app"]["id"] == "affirmation_app"

    def test_three_pages_resolved(self, resolved):
        assert len(resolved["pages"]) == 3
        ids = {p["id"] for p in resolved["pages"]}
        assert ids == {"home", "detail", "settings"}

    def test_shared_inherited(self, resolved):
        for page in resolved["pages"]:
            assert "icon_back" in page["assets"]
            assert "body" in page["fonts"]

    def test_model_present(self, resolved):
        assert len(resolved["models"]) == 1
        assert resolved["models"][0]["name"] == "favorites"

    # ── Generated files ──

    def test_all_files_generated(self, files):
        expected = [
            "app/ui_router.c", "app/ui_router.h",
            "app/ui_app.c", "app/ui_app.h",
            "presenters/presenter_home.c", "presenters/presenter_home.h",
            "presenters/presenter_detail.c", "presenters/presenter_detail.h",
            "presenters/presenter_settings.c", "presenters/presenter_settings.h",
            "models/model_favorites.c", "models/model_favorites.h",
        ]
        for path in expected:
            assert path in files, f"Missing: {path}"

    def test_file_count(self, files):
        # 2 router + 2 app + 6 presenters (3 pages × 2) + 2 models (1 model × 2)
        assert len(files) >= 12

    # ── Router ──

    def test_router_has_all_pages(self, files):
        router_c = files["app/ui_router.c"]
        assert "PAGE_HOME" in router_c
        assert "PAGE_DETAIL" in router_c
        assert "PAGE_SETTINGS" in router_c

    def test_router_has_push_back_replace(self, files):
        router_c = files["app/ui_router.c"]
        assert "ui_router_push" in router_c
        assert "ui_router_back" in router_c
        assert "ui_router_replace" in router_c

    def test_router_has_error_codes(self, files):
        router_h = files["app/ui_router.h"]
        assert "UI_ROUTER_ERR_STACK_FULL" in router_h
        assert "UI_ROUTER_ERR_NO_BACK" in router_h

    def test_router_max_depth(self, files):
        router_c = files["app/ui_router.c"]
        assert "UI_ROUTER_MAX_DEPTH 8" in router_c

    # ── Presenter ──

    def test_home_presenter_binds_favorite(self, files):
        pres_c = files["presenters/presenter_home.c"]
        assert "model_favorites" in pres_c
        assert "is_favorited" in pres_c

    def test_home_presenter_binds_route(self, files):
        pres_c = files["presenters/presenter_home.c"]
        assert "ui_router_push" in pres_c
        assert "PAGE_DETAIL" in pres_c

    def test_settings_presenter_binds_back(self, files):
        pres_c = files["presenters/presenter_settings.c"]
        assert "ui_router_back" in pres_c

    # ── Model ──

    def test_model_has_bool_field(self, files):
        model_h = files["models/model_favorites.h"]
        assert "model_favorites_get_is_favorited" in model_h
        assert "model_favorites_set_is_favorited" in model_h

    def test_model_default_false(self, files):
        model_c = files["models/model_favorites.c"]
        assert "= false" in model_c

    # ── App ──

    def test_app_inits_model(self, files):
        app_c = files["app/ui_app.c"]
        assert "model_favorites_init" in app_c

    def test_app_pushes_entry_page(self, files):
        app_c = files["app/ui_app.c"]
        assert "PAGE_HOME" in app_c

    def test_app_has_async_dispatch(self, files):
        app_c = files["app/ui_app.c"]
        assert "lv_async_call" in app_c
        assert "lv_malloc" in app_c

    # ── Validation ──

    def test_validation_passes(self, validation):
        assert validation["ok"] is True, f"Errors: {validation['errors']}"

    def test_status_is_verified(self, validation):
        assert validation["status"] == "verified"

    def test_no_manual_required(self, validation):
        assert len(validation["manual_required"]) == 0

    def test_route_graph_ok(self, validation):
        rg = validation["details"]["route_graph"]
        assert rg["ok"] is True
        assert rg["reachable"] == {"home", "detail", "settings"}

    def test_code_structure_ok(self, validation):
        cs = validation["details"]["code_structure"]
        assert cs["ok"] is True

    def test_thread_boundary_ok(self, validation):
        tb = validation["details"]["thread_boundary"]
        assert tb["ok"] is True


# ── Negative tests ─────────────────────────────────────────────────


class TestMVPPipelineNegative:
    """Verify that validation catches problems."""

    def test_orphan_page_detected(self):
        manifest = load_manifest(MVP_MANIFEST)
        # Add an orphan page
        manifest["pages"].append({
            "id": "orphan",
            "design": "designs/orphan.png",
            "states": ["default"],
            "state_designs": {"default": "designs/orphan.png"},
        })
        resolved = resolve_manifest(manifest)
        files = _generate_app_scaffold(resolved)
        result = validate_app(resolved, files)
        assert result["ok"] is False
        assert result["status"] == "invalid"
        assert any("orphan" in e for e in result["errors"])

    def test_todo_marks_needs_manual(self):
        manifest = load_manifest(MVP_MANIFEST)
        resolved = resolve_manifest(manifest)
        files = _generate_app_scaffold(resolved)
        # Inject a TODO
        files["app/ui_router.c"] += "\n/* TODO: add animation */\n"
        result = validate_app(resolved, files)
        assert result["ok"] is True
        assert result["status"] == "needs_manual_work"
        assert len(result["manual_required"]) > 0

    def test_unbalanced_braces_invalid(self):
        manifest = load_manifest(MVP_MANIFEST)
        resolved = resolve_manifest(manifest)
        files = _generate_app_scaffold(resolved)
        # Break brace balance
        files["app/ui_router.c"] += "\nvoid broken() {\n"
        result = validate_app(resolved, files)
        assert result["ok"] is False
        assert result["status"] == "invalid"

    def test_thread_violation_invalid(self):
        manifest = load_manifest(MVP_MANIFEST)
        resolved = resolve_manifest(manifest)
        files = _generate_app_scaffold(resolved)
        # Inject unsafe LVGL call in presenter
        files["presenters/presenter_home.c"] += "\nvoid bad() { lv_timer_create(NULL, 100, NULL); }\n"
        result = validate_app(resolved, files)
        assert result["ok"] is False
        assert result["status"] == "invalid"
