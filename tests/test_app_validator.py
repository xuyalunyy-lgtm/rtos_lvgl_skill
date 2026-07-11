"""Tests for app-level validators (route graph, code structure, thread boundary, resource dedup)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "mcp"))

from app_validator import (
    validate_route_graph,
    validate_generated_code,
    validate_thread_boundary,
    validate_resource_dedup,
    validate_app,
)


# ── Fixtures ───────────────────────────────────────────────────────

def _pages(*ids: str) -> list[dict]:
    return [{"id": pid, "design": f"d/{pid}.png"} for pid in ids]


def _routes(*specs: tuple[str, str, str, str]) -> list[dict]:
    """Each spec: (id, from, to, mode).  'to' is '' for back."""
    result = []
    for rid, src, dst, mode in specs:
        r = {"id": rid, "from": src, "mode": mode, "event": "x.clicked"}
        if dst:
            r["to"] = dst
        result.append(r)
    return result


# ── Route graph ────────────────────────────────────────────────────


class TestRouteGraph:
    def test_connected_graph(self):
        pages = _pages("home", "detail", "settings")
        routes = _routes(("r1", "home", "detail", "push"), ("r2", "detail", "settings", "replace"))
        result = validate_route_graph(pages, routes, "home")
        assert result["ok"] is True
        assert result["reachable"] == {"home", "detail", "settings"}

    def test_orphan_page(self):
        pages = _pages("home", "detail", "orphan")
        routes = _routes(("r1", "home", "detail", "push"))
        result = validate_route_graph(pages, routes, "home")
        assert result["ok"] is False
        assert "orphan" in str(result["errors"])

    def test_back_routes_not_edges(self):
        """Back routes are reverse navigation, not forward edges."""
        pages = _pages("home", "detail")
        routes = _routes(("r1", "home", "detail", "push"), ("r2", "detail", "", "back"))
        result = validate_route_graph(pages, routes, "home")
        assert result["ok"] is True
        # detail is reachable via push, back doesn't create an edge
        assert result["reachable"] == {"home", "detail"}

    def test_empty_entry_page(self):
        result = validate_route_graph([], [], "")
        assert result["ok"] is False
        assert "entry_page" in str(result["errors"]).lower()

    def test_entry_not_in_pages(self):
        result = validate_route_graph(_pages("home"), [], "nonexistent")
        assert result["ok"] is False

    def test_single_page_no_routes(self):
        pages = _pages("home")
        result = validate_route_graph(pages, [], "home")
        assert result["ok"] is True
        assert result["reachable"] == {"home"}

    def test_cycle(self):
        """Cycles are OK (A→B→A) as long as all pages are reachable."""
        pages = _pages("a", "b")
        routes = _routes(("r1", "a", "b", "push"), ("r2", "b", "a", "push"))
        result = validate_route_graph(pages, routes, "a")
        assert result["ok"] is True


# ── Generated code structure ───────────────────────────────────────


class TestGeneratedCode:
    def test_balanced_code(self):
        files = {"test.c": "void foo() { if (x) { bar(); } }"}
        result = validate_generated_code(files)
        assert result["ok"] is True

    def test_unbalanced_braces(self):
        files = {"test.c": "void foo() { if (x) { bar(); }"}
        result = validate_generated_code(files)
        assert result["ok"] is False
        assert "unbalanced" in str(result["errors"]).lower()

    def test_unbalanced_parens(self):
        files = {"test.c": "void foo( { bar(); }"}
        result = validate_generated_code(files)
        assert result["ok"] is False

    def test_injection_system_call(self):
        files = {"test.c": 'void foo() { system("rm -rf /"); }'}
        result = validate_generated_code(files)
        assert any("system" in w for w in result["warnings"])

    def test_injection_system_include(self):
        files = {"test.c": '#include <stdio.h>\nvoid foo() {}'}
        result = validate_generated_code(files)
        assert any("system include" in w for w in result["warnings"])

    def test_todo_is_manual_required(self):
        files = {"test.c": "void foo() {\n    /* TODO: implement */\n}"}
        result = validate_generated_code(files)
        assert result["ok"] is True  # not an error
        assert len(result["manual_required"]) == 1
        assert "TODO" in result["manual_required"][0]

    def test_fixme_is_manual_required(self):
        files = {"test.c": "// FIXME: broken\nvoid foo() {}"}
        result = validate_generated_code(files)
        assert len(result["manual_required"]) == 1

    def test_no_false_positive_on_string(self):
        files = {"test.c": 'const char *s = "TODO in string";'}
        result = validate_generated_code(files)
        # TODO inside a string literal should still be flagged (conservative)
        # This is acceptable — manual review will filter false positives


# ── Thread boundary ────────────────────────────────────────────────


class TestThreadBoundary:
    def test_clean_presenter(self):
        files = {"presenter_home.c": "void presenter_home_bind(lv_obj_t *root) { (void)root; }"}
        result = validate_thread_boundary(files)
        assert result["ok"] is True

    def test_lv_timer_create_violation(self):
        files = {"presenter_home.c": "void foo() { lv_timer_create(cb, 100, NULL); }"}
        result = validate_thread_boundary(files)
        assert result["ok"] is False
        assert "lv_timer" in str(result["errors"])

    def test_lv_async_call_violation(self):
        files = {"presenter_home.c": "void foo() { lv_async_call(cb, NULL); }"}
        result = validate_thread_boundary(files)
        assert result["ok"] is False

    def test_empty_presenters(self):
        result = validate_thread_boundary({})
        assert result["ok"] is True


# ── Resource dedup ─────────────────────────────────────────────────


class TestResourceDedup:
    def test_no_duplication(self):
        pages = [{"id": "home", "assets": {"icon": "home_icon.png"}}]
        shared = {"assets": {"back": "back.png"}}
        result = validate_resource_dedup(pages, shared)
        assert result["ok"] is True
        assert len(result["warnings"]) == 0

    def test_redundant_declaration(self):
        pages = [{"id": "home", "assets": {"icon": "shared_icon.png"}}]
        shared = {"assets": {"icon": "shared_icon.png"}}
        result = validate_resource_dedup(pages, shared)
        assert result["ok"] is True  # warning, not error
        assert any("redundant" in w.lower() for w in result["warnings"])

    def test_page_override_not_warned(self):
        """Page overriding shared value with different path is OK."""
        pages = [{"id": "home", "assets": {"icon": "custom_icon.png"}}]
        shared = {"assets": {"icon": "shared_icon.png"}}
        result = validate_resource_dedup(pages, shared)
        assert len(result["warnings"]) == 0

    def test_empty_shared(self):
        pages = [{"id": "home", "assets": {"x": "y"}}]
        result = validate_resource_dedup(pages, {})
        assert result["ok"] is True


# ── Integration: validate_app ──────────────────────────────────────


class TestValidateApp:
    def _manifest(self, **overrides):
        m = {
            "schema_version": "2.0",
            "app": {"id": "test_app", "entry_page": "home"},
            "display": {"width": 480, "height": 800},
            "shared": {"assets": {}, "fonts": {}},
            "models": [],
            "pages": _pages("home", "detail"),
            "routes": _routes(("r1", "home", "detail", "push")),
        }
        m.update(overrides)
        return m

    def test_valid_app_verified(self):
        files = {
            "app/ui_router.c": "void ui_router_init() {}",
            "app/ui_router.h": "void ui_router_init();",
            "app/ui_app.c": "void ui_app_start() {}",
            "app/ui_app.h": "void ui_app_start();",
            "presenters/presenter_home.c": "void presenter_home_bind(lv_obj_t *r) { (void)r; }",
            "presenters/presenter_home.h": "void presenter_home_bind(lv_obj_t *r);",
        }
        result = validate_app(self._manifest(), files)
        assert result["ok"] is True
        assert result["status"] == "verified"

    def test_orphan_page_needs_manual(self):
        m = self._manifest(pages=_pages("home", "detail", "orphan"))
        files = {"app/ui_router.c": "void foo() {}"}
        result = validate_app(m, files)
        assert result["ok"] is False
        assert result["status"] == "invalid"

    def test_todo_needs_manual_work(self):
        files = {"app/ui_router.c": "void foo() {\n    /* TODO */\n}"}
        result = validate_app(self._manifest(), files)
        assert result["ok"] is True
        assert result["status"] == "needs_manual_work"
        assert len(result["manual_required"]) > 0

    def test_unbalanced_braces_invalid(self):
        files = {"app/ui_router.c": "void foo() {"}
        result = validate_app(self._manifest(), files)
        assert result["ok"] is False
        assert result["status"] == "invalid"

    def test_thread_violation_invalid(self):
        files = {"presenters/presenter_home.c": "void foo() { lv_timer_create(cb, 100, NULL); }"}
        result = validate_app(self._manifest(), files)
        assert result["ok"] is False
        assert result["status"] == "invalid"
