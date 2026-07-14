"""Manifest v2 — schema, validation, and resolution for multi-page LVGL apps.

Handles v1 passthrough (single-page, no changes) and full v2 validation
covering pages, routes, models, states, events, fonts, and assets.

Usage:
    from mcp.manifest_v2 import load_manifest, validate_manifest, resolve_manifest
    manifest = load_manifest("ui/manifest.json")
    result = validate_manifest(manifest)
    if result["ok"]:
        resolved = resolve_manifest(manifest)
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

# ── Constants ──────────────────────────────────────────────────────

VALID_ROUTE_MODES = {"push", "replace", "back"}
VALID_MODEL_FIELD_TYPES = {"bool", "int32", "string"}
VALID_EVENT_ACTIONS = {"route", "model_set", "model_toggle", "set_state"}
VALID_BINDING_TARGETS = {"text", "checked", "hidden", "value", "image", "page.state"}
VALID_ASSET_KINDS = {"image"}
VALID_ALPHA = {"auto", "opaque", "transparent"}
VALID_ASSET_FORMATS = {"auto", "RGB565", "RGB565A8", "ARGB8888"}
_SNAKE_CASE_RE = re.compile(r"^[a-z][a-z0-9]*(_[a-z0-9]+)*$")


# ── Public API ─────────────────────────────────────────────────────


def load_manifest(path_or_dict: str | Path | dict[str, Any]) -> dict[str, Any]:
    """Read and return a manifest. v1 passes through unchanged.

    Args:
        path_or_dict: Path to JSON file, or already-loaded dict.

    Returns:
        Manifest dict with schema_version preserved.
    """
    if isinstance(path_or_dict, dict):
        return dict(path_or_dict)
    path = Path(path_or_dict)
    if not path.is_file():
        raise FileNotFoundError(f"Manifest not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def validate_manifest(manifest: dict[str, Any], root_dir: str | Path | None = None) -> dict[str, Any]:
    """Validate manifest structure. v1 is accepted as-is.

    Returns:
        {"ok": bool, "errors": [...], "warnings": [...]}
    """
    if not isinstance(manifest, dict):
        return _fail(["Manifest must be a JSON object"])

    version = manifest.get("schema_version", "1.0")
    if version == "1.0":
        return {"ok": True, "errors": [], "warnings": ["v1 manifest — single-page mode"], "version": "1.0"}

    if version == "2.1":
        return _validate_manifest_v21(manifest, Path(root_dir).resolve() if root_dir else None)
    if version != "2.0":
        return _fail([f"Unsupported schema_version: {version!r}. Expected '1.0', '2.0', or '2.1'."])

    errors: list[str] = []
    warnings: list[str] = []

    # ── app block ──────────────────────────────────────────────────
    app = manifest.get("app")
    if not isinstance(app, dict):
        errors.append("app is required and must be an object")
    else:
        app_id = app.get("id", "")
        if not isinstance(app_id, str) or not app_id:
            errors.append("app.id is required and must be a non-empty string")
        elif not _SNAKE_CASE_RE.match(app_id):
            errors.append(f"app.id must be snake_case, got {app_id!r}")

        entry = app.get("entry_page")
        if not isinstance(entry, str) or not entry:
            errors.append("app.entry_page is required and must be a non-empty string")

        nav = app.get("navigation")
        if isinstance(nav, dict):
            mode = nav.get("mode", "stack")
            if mode != "stack":
                errors.append(f"app.navigation.mode must be 'stack', got {mode!r}")
            max_depth = nav.get("max_depth", 8)
            if not isinstance(max_depth, int) or max_depth < 1:
                errors.append(f"app.navigation.max_depth must be a positive integer, got {max_depth!r}")

    # ── display ────────────────────────────────────────────────────
    display = manifest.get("display")
    if not isinstance(display, dict):
        errors.append("display is required and must be an object")
    else:
        for field in ("width", "height"):
            val = display.get(field)
            if not isinstance(val, int) or val < 1:
                errors.append(f"display.{field} must be a positive integer, got {val!r}")

    # ── pages ──────────────────────────────────────────────────────
    pages = manifest.get("pages")
    if not isinstance(pages, list) or len(pages) == 0:
        errors.append("pages must be a non-empty array")
    else:
        page_ids: set[str] = set()
        for i, page in enumerate(pages):
            if not isinstance(page, dict):
                errors.append(f"pages[{i}] must be an object")
                continue
            pid = page.get("id", "")
            if not isinstance(pid, str) or not pid:
                errors.append(f"pages[{i}].id is required")
            elif not _SNAKE_CASE_RE.match(pid):
                errors.append(f"pages[{i}].id must be snake_case, got {pid!r}")
            elif pid in page_ids:
                errors.append(f"Duplicate page id: {pid!r}")
            else:
                page_ids.add(pid)

            # states
            states = page.get("states")
            if states is not None:
                if not isinstance(states, list) or len(states) == 0:
                    errors.append(f"pages[{i}].states must be a non-empty array if provided")
                elif "default" not in states:
                    errors.append(f"pages[{i}].states must include 'default'")
                seen_states: set[str] = set()
                for s in states:
                    if not isinstance(s, str):
                        errors.append(f"pages[{i}].states entries must be strings")
                    elif s in seen_states:
                        errors.append(f"pages[{i}].states has duplicate: {s!r}")
                    else:
                        seen_states.add(s)

            # state_designs — every declared state must have a design baseline
            state_designs = page.get("state_designs")
            if isinstance(state_designs, dict) and isinstance(states, list):
                for s in states:
                    if s not in state_designs:
                        errors.append(f"pages[{i}].state_designs missing design for state {s!r}")

            # design (default state)
            design = page.get("design")
            if not isinstance(design, str) or not design:
                errors.append(f"pages[{i}].design is required and must be a non-empty string")

            # template
            template = page.get("template")
            if template is not None and not isinstance(template, str):
                errors.append(f"pages[{i}].template must be a string")

            # events
            events = page.get("events")
            if events is not None:
                if not isinstance(events, list):
                    errors.append(f"pages[{i}].events must be an array")
                else:
                    _validate_events(events, i, errors)

        # entry_page must reference an existing page
        entry = app.get("entry_page") if isinstance(app, dict) else None
        if isinstance(entry, str) and entry and entry not in page_ids:
            errors.append(f"app.entry_page {entry!r} not found in pages")

    # ── routes ─────────────────────────────────────────────────────
    routes = manifest.get("routes")
    route_ids: set[str] = set()
    if routes is not None:
        if not isinstance(routes, list):
            errors.append("routes must be an array")
        else:
            page_ids_set = _collect_page_ids(manifest)
            for i, route in enumerate(routes):
                if not isinstance(route, dict):
                    errors.append(f"routes[{i}] must be an object")
                    continue
                rid = route.get("id", "")
                if not isinstance(rid, str) or not rid:
                    errors.append(f"routes[{i}].id is required")
                elif rid in route_ids:
                    errors.append(f"Duplicate route id: {rid!r}")
                else:
                    route_ids.add(rid)

                rfrom = route.get("from")
                if not isinstance(rfrom, str) or rfrom not in page_ids_set:
                    errors.append(f"routes[{i}].from {rfrom!r} is not a valid page id")

                mode = route.get("mode", "push")
                if mode not in VALID_ROUTE_MODES:
                    errors.append(f"routes[{i}].mode must be one of {sorted(VALID_ROUTE_MODES)}, got {mode!r}")

                if mode == "back":
                    if "to" in route:
                        errors.append(f"routes[{i}] mode=back must not have a 'to' field")
                else:
                    rto = route.get("to")
                    if not isinstance(rto, str) or rto not in page_ids_set:
                        errors.append(f"routes[{i}].to {rto!r} is not a valid page id")

                event = route.get("event")
                if not isinstance(event, str) or not event:
                    errors.append(f"routes[{i}].event is required")

    # ── models ─────────────────────────────────────────────────────
    models = manifest.get("models")
    model_names: set[str] = set()
    if models is not None:
        if not isinstance(models, list):
            errors.append("models must be an array")
        else:
            for i, model in enumerate(models):
                if not isinstance(model, dict):
                    errors.append(f"models[{i}] must be an object")
                    continue
                mname = model.get("name", "")
                if not isinstance(mname, str) or not mname:
                    errors.append(f"models[{i}].name is required")
                elif mname in model_names:
                    errors.append(f"Duplicate model name: {mname!r}")
                else:
                    model_names.add(mname)

                fields = model.get("fields")
                if not isinstance(fields, list) or len(fields) == 0:
                    errors.append(f"models[{i}].fields must be a non-empty array")
                else:
                    field_names: set[str] = set()
                    for j, field in enumerate(fields):
                        if not isinstance(field, dict):
                            errors.append(f"models[{i}].fields[{j}] must be an object")
                            continue
                        fname = field.get("name", "")
                        if not isinstance(fname, str) or not fname:
                            errors.append(f"models[{i}].fields[{j}].name is required")
                        elif fname in field_names:
                            errors.append(f"models[{i}] has duplicate field: {fname!r}")
                        else:
                            field_names.add(fname)

                        ftype = field.get("type", "")
                        if ftype not in VALID_MODEL_FIELD_TYPES:
                            errors.append(
                                f"models[{i}].fields[{j}].type must be one of "
                                f"{sorted(VALID_MODEL_FIELD_TYPES)}, got {ftype!r}"
                            )

                        if ftype == "string":
                            ml = field.get("max_length")
                            if not isinstance(ml, int) or ml < 1:
                                errors.append(
                                    f"models[{i}].fields[{j}].max_length must be a positive integer"
                                )
                            default = field.get("default")
                            if not isinstance(default, str):
                                errors.append(
                                    f"models[{i}].fields[{j}].default must be a string for string fields"
                                )

                        if ftype == "bool":
                            default = field.get("default")
                            if not isinstance(default, bool):
                                errors.append(
                                    f"models[{i}].fields[{j}].default must be a bool for bool fields"
                                )

                        if ftype == "int32":
                            default = field.get("default")
                            if not isinstance(default, int):
                                errors.append(
                                    f"models[{i}].fields[{j}].default must be an int for int32 fields"
                                )

    # ── shared ─────────────────────────────────────────────────────
    shared = manifest.get("shared")
    if shared is not None and not isinstance(shared, dict):
        errors.append("shared must be an object")

    # ── Cross-reference: event actions ─────────────────────────────
    if isinstance(pages, list) and isinstance(routes, list) and isinstance(models, list):
        _validate_event_actions(manifest, route_ids, model_names, errors)

    ok = len(errors) == 0
    return {"ok": ok, "errors": errors, "warnings": warnings, "version": "2.0"}


def resolve_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    """Flatten shared → page inheritance. Returns a fully-resolved manifest.

    Assumes validate_manifest passed. Does not mutate the input.
    """
    import copy
    resolved = copy.deepcopy(manifest)

    shared = resolved.get("shared", {})
    shared_assets = shared.get("assets", {}) if isinstance(shared, dict) else {}
    shared_fonts = shared.get("fonts", {}) if isinstance(shared, dict) else {}

    for page in resolved.get("pages", []):
        if not isinstance(page, dict):
            continue
        # Assets: page-level overrides shared
        page_assets = page.get("assets")
        if not isinstance(page_assets, dict):
            page_assets = {}
        merged_assets = {**shared_assets, **page_assets}
        page["assets"] = merged_assets

        # Fonts: page-level overrides shared
        page_fonts = page.get("fonts")
        if not isinstance(page_fonts, dict):
            page_fonts = {}
        merged_fonts = {**shared_fonts, **page_fonts}
        page["fonts"] = merged_fonts

        # State containers intentionally differ between v2.0 and v2.1.  Do
        # not coerce a validated v2.1 state map into the legacy list shape.
        states = page.get("states")
        if resolved.get("schema_version") == "2.1":
            if not isinstance(states, dict) or not states:
                page["states"] = {"default": {"design": page.get("design", "")}}
        elif not isinstance(states, list) or not states:
            page["states"] = ["default"]

    return resolved


def _validate_manifest_v21(manifest: dict[str, Any], root_dir: Path | None) -> dict[str, Any]:
    """Validate the evidence-capable multi-page contract.

    Version 2.1 deliberately does not reuse the v2.0 scaffold validator:
    verified applications need state objects, resource identities and flows,
    not just enough information to emit placeholder C files.
    """
    errors: list[str] = []
    warnings: list[str] = []
    app = manifest.get("app")
    display = manifest.get("display")
    pages = manifest.get("pages")
    routes = manifest.get("routes", [])
    models = manifest.get("models", [])
    shared = manifest.get("shared", {})

    if not isinstance(app, dict) or not _valid_id(app.get("id")):
        errors.append("app.id is required and must be snake_case")
    if not isinstance(display, dict) or not all(isinstance(display.get(k), int) and display[k] > 0 for k in ("width", "height")):
        errors.append("display.width and display.height must be positive integers")
    elif display.get("color_format", "RGB565") != "RGB565":
        errors.append("display.color_format must be RGB565 for v2.1")

    if not isinstance(pages, list) or not pages:
        return _fail(errors + ["pages must be a non-empty array"])
    page_ids: set[str] = set()
    event_keys: set[tuple[str, str]] = set()
    page_nodes: dict[str, set[str]] = {}
    for index, page in enumerate(pages):
        if not isinstance(page, dict) or not _valid_id(page.get("id")):
            errors.append(f"pages[{index}].id must be unique snake_case")
            continue
        pid = page["id"]
        if pid in page_ids:
            errors.append(f"Duplicate page id: {pid!r}")
        page_ids.add(pid)
        states = page.get("states")
        if not isinstance(states, dict) or not states or "default" not in states:
            errors.append(f"pages[{index}].states must be a non-empty object containing default")
        else:
            for state_id, state in states.items():
                if not _valid_id(state_id) or not isinstance(state, dict):
                    errors.append(f"pages[{index}].states has invalid state {state_id!r}")
                    continue
                _validate_path(state.get("design"), f"pages[{index}].states.{state_id}.design", root_dir, errors)
        nodes = page.get("nodes", [])
        if nodes is not None and not isinstance(nodes, list):
            errors.append(f"pages[{index}].nodes must be an array when supplied")
        page_nodes[pid] = {n for n in nodes if isinstance(n, str)}
        for event in page.get("events", []):
            if not isinstance(event, dict) or not isinstance(event.get("node_id"), str) or not isinstance(event.get("trigger"), str):
                errors.append(f"pages[{index}].events entries need node_id and trigger")
                continue
            event_keys.add((pid, f"{event['node_id']}.{event['trigger']}"))
            _validate_event_actions_v21(event.get("actions"), pid, errors)
        for binding in page.get("bindings", []):
            _validate_binding(binding, pid, page_nodes[pid], models, errors)
        for region in page.get("quality_regions", []):
            if not isinstance(region, dict) or region.get("kind") not in {"text", "interaction", "status"}:
                errors.append(f"pages[{index}].quality_regions must declare text, interaction, or status")

    if not isinstance(app, dict) or app.get("entry_page") not in page_ids:
        errors.append("app.entry_page must reference a page")
    nav = app.get("navigation", {}) if isinstance(app, dict) else {}
    if not isinstance(nav, dict) or nav.get("mode", "stack") != "stack" or not isinstance(nav.get("max_depth", 8), int) or nav.get("max_depth", 8) < 1:
        errors.append("app.navigation must be stack with positive max_depth")

    _validate_resource_block(shared.get("assets", {}), "shared.assets", root_dir, errors, asset=True)
    _validate_resource_block(shared.get("fonts", {}), "shared.fonts", root_dir, errors, asset=False)
    for page in pages:
        if isinstance(page, dict):
            _validate_resource_block(page.get("assets", {}), f"pages.{page.get('id', '?')}.assets", root_dir, errors, asset=True)
            _validate_resource_block(page.get("fonts", {}), f"pages.{page.get('id', '?')}.fonts", root_dir, errors, asset=False)

    route_ids: set[str] = set()
    for index, route in enumerate(routes if isinstance(routes, list) else []):
        if not isinstance(route, dict) or not _valid_id(route.get("id")):
            errors.append(f"routes[{index}].id must be snake_case")
            continue
        rid = route["id"]
        if rid in route_ids:
            errors.append(f"Duplicate route id: {rid!r}")
        route_ids.add(rid)
        src, event, mode = route.get("from"), route.get("event"), route.get("mode")
        if src not in page_ids or not isinstance(event, str) or (src, event) not in event_keys:
            errors.append(f"routes[{index}] must match a declared page event")
        if mode not in VALID_ROUTE_MODES:
            errors.append(f"routes[{index}].mode is invalid")
        if mode == "back":
            if route.get("to") is not None:
                errors.append(f"routes[{index}] back route must not declare to")
        elif route.get("to") not in page_ids:
            errors.append(f"routes[{index}].to must reference a page")

    _validate_models_v21(models, errors)
    for page in pages:
        if not isinstance(page, dict):
            continue
        for event in page.get("events", []):
            for action in event.get("actions", []) if isinstance(event, dict) else []:
                if isinstance(action, dict) and action.get("type") == "route" and action.get("route_id") not in route_ids:
                    errors.append(f"page {page.get('id')} references unknown route {action.get('route_id')!r}")

    flows = manifest.get("flows")
    if not isinstance(flows, list) or not flows:
        errors.append("flows must be a non-empty array for a v2.1 verified app")
    else:
        for index, flow in enumerate(flows):
            if not isinstance(flow, dict) or not _valid_id(flow.get("id")) or flow.get("start_page") not in page_ids or not isinstance(flow.get("steps"), list) or not flow["steps"]:
                errors.append(f"flows[{index}] requires id, start_page and non-empty steps")

    memory = manifest.get("memory")
    quality = manifest.get("quality")
    if not isinstance(memory, dict) or not isinstance(memory.get("max_runtime_asset_bytes"), int) or not isinstance(memory.get("max_dynamic_heap_bytes"), int):
        errors.append("memory must declare max_runtime_asset_bytes and max_dynamic_heap_bytes")
    if not isinstance(quality, dict) or quality.get("profile", "mvp_90") not in {"mvp_90", "golden_strict"}:
        errors.append("quality.profile must be mvp_90 or golden_strict")
    return {"ok": not errors, "errors": errors, "warnings": warnings, "version": "2.1"}


def _valid_id(value: Any) -> bool:
    return isinstance(value, str) and bool(_SNAKE_CASE_RE.match(value))


def _validate_path(value: Any, label: str, root_dir: Path | None, errors: list[str]) -> None:
    if not isinstance(value, str) or not value:
        errors.append(f"{label} is required")
        return
    if root_dir is not None:
        try:
            resolved = (root_dir / value).resolve()
            resolved.relative_to(root_dir)
        except (OSError, ValueError):
            errors.append(f"{label} must stay inside the UI package")
            return
        if not resolved.is_file():
            errors.append(f"{label} does not exist: {value}")


def _validate_resource_block(block: Any, label: str, root_dir: Path | None, errors: list[str], *, asset: bool) -> None:
    if not isinstance(block, dict):
        errors.append(f"{label} must be an object")
        return
    for role, item in block.items():
        if not _valid_id(role) or not isinstance(item, dict):
            errors.append(f"{label}.{role} must be a resource object")
            continue
        _validate_path(item.get("source"), f"{label}.{role}.source", root_dir, errors)
        if not _valid_id(item.get("symbol")):
            errors.append(f"{label}.{role}.symbol must be snake_case")
        if asset:
            if item.get("kind") not in VALID_ASSET_KINDS or item.get("alpha", "auto") not in VALID_ALPHA or item.get("format", "auto") not in VALID_ASSET_FORMATS:
                errors.append(f"{label}.{role} has invalid asset metadata")
        else:
            _validate_path(item.get("preview_bin"), f"{label}.{role}.preview_bin", root_dir, errors)
            if not isinstance(item.get("roles"), list) or not item["roles"]:
                errors.append(f"{label}.{role}.roles must be non-empty")


def _validate_models_v21(models: Any, errors: list[str]) -> None:
    if not isinstance(models, list):
        errors.append("models must be an array")
        return
    for index, model in enumerate(models):
        if not isinstance(model, dict) or not _valid_id(model.get("name")) or not isinstance(model.get("fields"), list):
            errors.append(f"models[{index}] requires name and fields")


def _validate_event_actions_v21(actions: Any, page_id: str, errors: list[str]) -> None:
    if not isinstance(actions, list) or not actions:
        errors.append(f"page {page_id} event needs actions")
        return
    for action in actions:
        if not isinstance(action, dict) or action.get("type") not in VALID_EVENT_ACTIONS:
            errors.append(f"page {page_id} has invalid event action")


def _validate_binding(binding: Any, page_id: str, node_ids: set[str], models: Any, errors: list[str]) -> None:
    if not isinstance(binding, dict):
        errors.append(f"page {page_id} binding must be an object")
        return
    node_id = binding.get("node_id")
    if not isinstance(node_id, str):
        errors.append(f"page {page_id} binding requires node_id")
    elif node_ids and node_id not in node_ids:
        errors.append(f"page {page_id} binding references undeclared node {node_id!r}")
    if binding.get("target") not in VALID_BINDING_TARGETS:
        errors.append(f"page {page_id} binding target is invalid")
    source = binding.get("source")
    if not isinstance(source, str) or (source != "page.state" and "." not in source):
        errors.append(f"page {page_id} binding source must be model.field or page.state")


# ── Internal helpers ───────────────────────────────────────────────


def _fail(errors: list[str]) -> dict[str, Any]:
    return {"ok": False, "errors": errors, "warnings": [], "version": "2.0"}


def _collect_page_ids(manifest: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    for page in manifest.get("pages", []):
        if isinstance(page, dict):
            pid = page.get("id")
            if isinstance(pid, str):
                ids.add(pid)
    return ids


def _collect_node_ids(manifest: dict[str, Any]) -> set[str]:
    """Collect all node IDs referenced in page events (from their 'node_id' field)."""
    ids: set[str] = set()
    for page in manifest.get("pages", []):
        if not isinstance(page, dict):
            continue
        for event in page.get("events", []):
            if isinstance(event, dict):
                nid = event.get("node_id")
                if isinstance(nid, str):
                    ids.add(nid)
    return ids


def _validate_events(events: list[Any], page_index: int, errors: list[str]) -> None:
    """Validate a page's events array."""
    for j, event in enumerate(events):
        if not isinstance(event, dict):
            errors.append(f"pages[{page_index}].events[{j}] must be an object")
            continue
        node_id = event.get("node_id")
        if not isinstance(node_id, str) or not node_id:
            errors.append(f"pages[{page_index}].events[{j}].node_id is required")
        trigger = event.get("trigger")
        if not isinstance(trigger, str) or not trigger:
            errors.append(f"pages[{page_index}].events[{j}].trigger is required")
        actions = event.get("actions")
        if not isinstance(actions, list) or len(actions) == 0:
            errors.append(f"pages[{page_index}].events[{j}].actions must be a non-empty array")
            continue
        for k, action in enumerate(actions):
            if not isinstance(action, dict):
                errors.append(f"pages[{page_index}].events[{j}].actions[{k}] must be an object")
                continue
            action_type = action.get("type")
            if action_type not in VALID_EVENT_ACTIONS:
                errors.append(
                    f"pages[{page_index}].events[{j}].actions[{k}].type must be one of "
                    f"{sorted(VALID_EVENT_ACTIONS)}, got {action_type!r}"
                )


def _validate_event_actions(
    manifest: dict[str, Any],
    route_ids: set[str],
    model_names: set[str],
    errors: list[str],
) -> None:
    """Cross-reference event actions against routes and models."""
    page_states: dict[str, set[str]] = {}
    for page in manifest.get("pages", []):
        if isinstance(page, dict):
            pid = page.get("id", "")
            states = page.get("states")
            if isinstance(states, list):
                page_states[pid] = set(states)
            else:
                page_states[pid] = {"default"}

    model_fields: dict[str, set[str]] = {}
    for model in manifest.get("models", []):
        if isinstance(model, dict):
            mname = model.get("name", "")
            fields = model.get("fields", [])
            if isinstance(fields, list):
                model_fields[mname] = {
                    f.get("name", "") for f in fields if isinstance(f, dict)
                }

    for page in manifest.get("pages", []):
        if not isinstance(page, dict):
            continue
        pid = page.get("id", "")
        for event in page.get("events", []):
            if not isinstance(event, dict):
                continue
            for action in event.get("actions", []):
                if not isinstance(action, dict):
                    continue
                action_type = action.get("type")

                if action_type == "route":
                    ref = action.get("route_id", "")
                    if ref not in route_ids:
                        errors.append(
                            f"Event action references unknown route_id {ref!r} "
                            f"(in page {pid!r})"
                        )

                elif action_type == "model_set" or action_type == "model_toggle":
                    target = action.get("target", "")
                    if "." not in target:
                        errors.append(
                            f"Event action {action_type!r} target must be 'model.field', "
                            f"got {target!r} (in page {pid!r})"
                        )
                    else:
                        mname, fname = target.split(".", 1)
                        if mname not in model_names:
                            errors.append(
                                f"Event action references unknown model {mname!r} "
                                f"(in page {pid!r})"
                            )
                        elif fname not in model_fields.get(mname, set()):
                            errors.append(
                                f"Event action references unknown field {fname!r} "
                                f"in model {mname!r} (in page {pid!r})"
                            )

                elif action_type == "set_state":
                    state = action.get("state", "")
                    if state not in page_states.get(pid, set()):
                        errors.append(
                            f"Event action set_state references unknown state {state!r} "
                            f"(in page {pid!r})"
                        )
