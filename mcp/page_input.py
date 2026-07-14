"""User-editable page input contract for deterministic LVGL generation."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


ASSET_TYPES = {
    "full_screen_background",
    "transparent_character",
    "status_icon",
    "control_icon",
    "decorative_image",
    "state_image",
}
SCALE_POLICIES = {"original", "contain", "stretch", "code_drawn"}
ELEMENT_TYPES = {"container", "label", "button", "bar", "slider", "switch", "checkbox", "dropdown", "roller", "spinner", "arc"}
STYLE_COLOR_FIELDS = {"bg_color", "border_color", "text_color"}
STYLE_INTEGER_FIELDS = {
    "bg_opa", "border_width", "radius", "shadow_width",
    "pad_top", "pad_bottom", "pad_left", "pad_right", "width", "height",
}
STYLE_FIELDS = STYLE_COLOR_FIELDS | STYLE_INTEGER_FIELDS | {"text_align"}


def _page_id(design_path: str) -> str:
    stem = Path(design_path).stem.lower()
    value = re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", stem)).strip("_")
    if not value or not value[0].isalpha():
        return "page"
    return value


def _bbox(value: Any) -> list[int] | None:
    if (
        isinstance(value, list)
        and len(value) == 4
        and all(isinstance(item, int) and not isinstance(item, bool) for item in value)
        and value[2] > 0
        and value[3] > 0
    ):
        return list(value)
    return None


def _asset_node_id(symbol: str) -> str:
    value = re.sub(r"_+", "_", re.sub(r"[^A-Za-z0-9_]+", "_", symbol)).strip("_").lower()
    return f"asset_{value}"


def _validate_styles(styles: Any, label: str, errors: list[str]) -> None:
    if not isinstance(styles, dict):
        errors.append(f"{label} must be an object")
        return
    unsupported = sorted(set(styles) - STYLE_FIELDS)
    if unsupported:
        errors.append(f"{label} has unsupported fields: {', '.join(unsupported)}")
    for field in STYLE_COLOR_FIELDS.intersection(styles):
        if not isinstance(styles[field], str) or not re.fullmatch(r"#[0-9A-Fa-f]{6}", styles[field]):
            errors.append(f"{label}.{field} must be #RRGGBB")
    for field in STYLE_INTEGER_FIELDS.intersection(styles):
        value = styles[field]
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            errors.append(f"{label}.{field} must be a non-negative integer")
        elif field == "bg_opa" and value > 255:
            errors.append(f"{label}.bg_opa must be between 0 and 255")
    if "text_align" in styles and styles["text_align"] not in {"left", "center", "right"}:
        errors.append(f"{label}.text_align must be left, center, or right")


def build_page_input_template(
    *,
    design_path: str,
    display: dict[str, Any],
    asset_intents: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """Build a concise draft whose candidate values can be confirmed by a user."""
    width = int(display.get("width", 480))
    height = int(display.get("height", 800))
    page_id = _page_id(design_path)
    assets: list[dict[str, Any]] = []
    for item in asset_intents or []:
        symbol = str(item.get("symbol", "")).strip()
        if not symbol:
            continue
        assets.append({
            "symbol": symbol,
            "type": item.get("type", "decorative_image"),
            "source": item.get("file_hint", ""),
            "bbox": _bbox(item.get("estimated_bbox")),
            "scale": "original",
            "preserve_canvas": bool(item.get("preserve_source_canvas", False)),
            "page": page_id,
            "state": str(item.get("state") or "default"),
            "layer": str(item.get("layer") or "content"),
            "reuse_scope": "shared" if item.get("allow_shared_source") else "page",
        })
    return {
        "schema_version": "1.0",
        "status": "draft",
        "page_id": page_id,
        "display": [width, height],
        "design": design_path,
        "coordinate_space": {
            "design_width": width,
            "design_height": height,
            "display_mapping": "1:1",
        },
        "bbox_policy": {"include_transparent_padding": True},
        "screen": {"bg_color": "#FFFFFF", "full_screen_tap": False},
        "assets": assets,
        "fonts": [],
        "elements": [],
        "interactions": {
            "transition": "none",
            "targets": [],
            "persistent_state": [],
        },
        "notes": "",
    }


def write_page_input(path: str | Path, payload: dict[str, Any]) -> str:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return str(target)


def load_page_input(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    if not source.is_file():
        raise ValueError(f"page_input_path not found: {path}")
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"unable to read page_input_path: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("page_input_path must contain a JSON object")
    return payload


def validate_page_input(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate only user-owned decisions; physical assets are resolved later."""
    errors: list[str] = []
    if payload.get("schema_version") != "1.0":
        errors.append("schema_version must be '1.0'")
    if payload.get("status") != "confirmed":
        errors.append("status must be 'confirmed' after user review")
    if not isinstance(payload.get("page_id"), str) or not re.fullmatch(r"[a-z][a-z0-9_]*", payload["page_id"]):
        errors.append("page_id must be snake_case")
    display = payload.get("display")
    if not (
        isinstance(display, list)
        and len(display) == 2
        and all(isinstance(item, int) and not isinstance(item, bool) and item > 0 for item in display)
    ):
        errors.append("display must be [width, height] with positive integers")
    if not isinstance(payload.get("design"), str) or not payload["design"].strip():
        errors.append("design must be a non-empty path")

    coordinate = payload.get("coordinate_space")
    if not isinstance(coordinate, dict):
        errors.append("coordinate_space must be an object")
    elif not (
        isinstance(coordinate.get("design_width"), int) and coordinate["design_width"] > 0
        and isinstance(coordinate.get("design_height"), int) and coordinate["design_height"] > 0
        and isinstance(coordinate.get("display_mapping"), str) and coordinate["display_mapping"].strip()
    ):
        errors.append("coordinate_space requires design_width, design_height, and display_mapping")

    bbox_policy = payload.get("bbox_policy")
    if not isinstance(bbox_policy, dict) or not isinstance(bbox_policy.get("include_transparent_padding"), bool):
        errors.append("bbox_policy.include_transparent_padding must be boolean")

    assets = payload.get("assets")
    asset_node_ids: set[str] = set()
    if not isinstance(assets, list) or not assets:
        errors.append("assets must contain at least one confirmed asset")
    else:
        seen: set[str] = set()
        portable_seen: set[str] = set()
        for index, asset in enumerate(assets):
            label = f"assets[{index}]"
            if not isinstance(asset, dict):
                errors.append(f"{label} must be an object")
                continue
            symbol = asset.get("symbol")
            if not isinstance(symbol, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", symbol) or len(symbol) > 31:
                errors.append(f"{label}.symbol must be a C identifier")
            elif symbol in seen:
                errors.append(f"{label}.symbol is duplicated")
            elif symbol.casefold() in portable_seen:
                errors.append(f"{label}.symbol collides on case-insensitive filesystems")
            else:
                seen.add(symbol)
                portable_seen.add(symbol.casefold())
                asset_node_ids.add(_asset_node_id(symbol))
            if asset.get("type") not in ASSET_TYPES:
                errors.append(f"{label}.type is invalid")
            if not isinstance(asset.get("source"), str) or not asset["source"].strip():
                errors.append(f"{label}.source must be non-empty")
            if _bbox(asset.get("bbox")) is None:
                errors.append(f"{label}.bbox must be [x, y, width, height]")
            if asset.get("scale") not in SCALE_POLICIES:
                errors.append(f"{label}.scale is invalid")
            if not isinstance(asset.get("preserve_canvas"), bool):
                errors.append(f"{label}.preserve_canvas must be boolean")
            for field in ("page", "state", "layer", "reuse_scope"):
                if not isinstance(asset.get(field), str) or not asset[field].strip():
                    errors.append(f"{label}.{field} must be non-empty")

    fonts = payload.get("fonts")
    font_roles: set[str] = set()
    if not isinstance(fonts, list):
        errors.append("fonts must be an array")
    else:
        for index, font in enumerate(fonts):
            label = f"fonts[{index}]"
            if not isinstance(font, dict):
                errors.append(f"{label} must be an object")
                continue
            if not isinstance(font.get("role"), str) or not re.fullmatch(r"[a-z][a-z0-9_]*", font["role"]):
                errors.append(f"{label}.role must be snake_case")
            elif font["role"] in font_roles:
                errors.append(f"{label}.role is duplicated")
            else:
                font_roles.add(font["role"])
            if not isinstance(font.get("source"), str) or not font["source"].strip():
                errors.append(f"{label}.source must be non-empty")
            size = font.get("size")
            if size is not None and (not isinstance(size, int) or isinstance(size, bool) or size <= 0):
                errors.append(f"{label}.size must be a positive integer or null")

    screen = payload.get("screen", {})
    if not isinstance(screen, dict):
        errors.append("screen must be an object")
    else:
        bg_color = screen.get("bg_color", "#FFFFFF")
        if not isinstance(bg_color, str) or not re.fullmatch(r"#[0-9A-Fa-f]{6}", bg_color):
            errors.append("screen.bg_color must be #RRGGBB")
        if not isinstance(screen.get("full_screen_tap", False), bool):
            errors.append("screen.full_screen_tap must be boolean")

    elements = payload.get("elements")
    if not isinstance(elements, list):
        errors.append("elements must be an array")
    else:
        element_ids: set[str] = set()
        for index, element in enumerate(elements):
            label = f"elements[{index}]"
            if not isinstance(element, dict):
                errors.append(f"{label} must be an object")
                continue
            element_id = element.get("id")
            if not isinstance(element_id, str) or not re.fullmatch(r"[a-z][a-z0-9_]*", element_id):
                errors.append(f"{label}.id must be snake_case")
            elif element_id in element_ids:
                errors.append(f"{label}.id is duplicated")
            elif element_id == "root" or element_id in asset_node_ids:
                errors.append(f"{label}.id collides with a generated node")
            else:
                element_ids.add(element_id)
            if element.get("type") not in ELEMENT_TYPES:
                errors.append(f"{label}.type is invalid")
            if _bbox(element.get("bbox")) is None:
                errors.append(f"{label}.bbox must be [x, y, width, height]")
            if element.get("type") in {"label", "button"} and not isinstance(element.get("text"), str):
                errors.append(f"{label}.text must be a string")
            _validate_styles(element.get("styles", {}), f"{label}.styles", errors)
            font_role = element.get("font_role")
            if font_role is not None and font_role not in font_roles:
                errors.append(f"{label}.font_role references an unknown font role")
            parent_id = element.get("parent_id", "root")
            if not isinstance(parent_id, str) or not re.fullmatch(r"[a-z][a-z0-9_]*", parent_id):
                errors.append(f"{label}.parent_id must be snake_case")
            text_macro = element.get("text_macro")
            if text_macro is not None and (not isinstance(text_macro, str) or not re.fullmatch(r"[A-Z_][A-Z0-9_]*", text_macro)):
                errors.append(f"{label}.text_macro must be an uppercase C identifier")
            for field in ("value", "range_min", "range_max"):
                value = element.get(field)
                if value is not None and (not isinstance(value, int) or isinstance(value, bool)):
                    errors.append(f"{label}.{field} must be an integer")
            layout = element.get("layout")
            if layout is not None:
                if not isinstance(layout, dict):
                    errors.append(f"{label}.layout must be an object")
                else:
                    if layout.get("mode", "flex-column") not in {"flex-column", "flex-row", "grid"}:
                        errors.append(f"{label}.layout.mode is invalid")
                    if "gap" in layout and (not isinstance(layout["gap"], int) or isinstance(layout["gap"], bool) or layout["gap"] < 0):
                        errors.append(f"{label}.layout.gap must be a non-negative integer")
                    if layout.get("flex_justify", "start") not in {"start", "center", "end", "space-between", "space-around"}:
                        errors.append(f"{label}.layout.flex_justify is invalid")
        valid_node_ids = {"root", *asset_node_ids, *element_ids}
        for index, element in enumerate(elements):
            if isinstance(element, dict) and isinstance(element.get("parent_id", "root"), str):
                parent_id = element.get("parent_id", "root")
                if parent_id not in valid_node_ids:
                    errors.append(f"elements[{index}].parent_id references an unknown node")
        if fonts and not elements:
            errors.append("elements must declare the text nodes that use confirmed fonts")

    interactions = payload.get("interactions")
    if not isinstance(interactions, dict):
        errors.append("interactions must be an object")
    elif not (
        isinstance(interactions.get("transition"), str) and interactions["transition"].strip()
        and isinstance(interactions.get("targets"), list)
        and isinstance(interactions.get("persistent_state"), list)
    ):
        errors.append("interactions requires transition, targets, and persistent_state")
    return {"ok": not errors, "errors": errors}


def page_input_to_asset_intents(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "symbol": asset["symbol"],
            "type": asset["type"],
            "file_hint": asset["source"],
            "required": True,
            "state": asset["state"],
            "layer": asset["layer"],
            "estimated_bbox": list(asset["bbox"]),
            "allow_shared_source": asset["reuse_scope"] != "page",
            "preserve_source_canvas": asset["preserve_canvas"],
        }
        for asset in payload["assets"]
    ]


def page_input_to_decisions(payload: dict[str, Any]) -> dict[str, Any]:
    scale_map = {"original": "native", "contain": "contain", "stretch": "stretch", "code_drawn": "code_drawn"}
    decisions: dict[str, Any] = {
        "coordinate_space": dict(payload["coordinate_space"]),
        "bbox_canvas_policy": dict(payload["bbox_policy"]),
        "interaction_policy": dict(payload["interactions"]),
    }
    fonts = payload.get("fonts", [])
    if fonts:
        decisions["font_policy"] = {
            "source": fonts[0]["source"],
            "match_sizes": any(font.get("size") is None for font in fonts),
            "fallback": "lvgl_default",
            "glyph_scope": "used_text",
        }
    for asset in payload["assets"]:
        decisions[f"asset:{asset['symbol']}"] = {
            "page": asset["page"],
            "state": asset["state"],
            "layer": asset["layer"],
            "bbox": list(asset["bbox"]),
            "size_policy": scale_map[asset["scale"]],
            "reuse_scope": asset["reuse_scope"],
        }
    return decisions


def page_input_to_spec(
    payload: dict[str, Any],
    *,
    asset_header: str,
    font_header: str | None,
    font_symbols: dict[str, str],
) -> dict[str, Any]:
    """Convert a confirmed page contract into UI Spec v2 without re-analysis."""
    width, height = payload["display"]
    screen = payload.get("screen", {})
    nodes: list[dict[str, Any]] = [{
        "id": "root",
        "type": "screen",
        "full_screen_tap": bool(screen.get("full_screen_tap", False)),
        "styles": {
            "bg_color": screen.get("bg_color", "#FFFFFF"),
            "bg_opa": 255,
            "border_width": 0,
            "pad_top": 0,
            "pad_bottom": 0,
            "pad_left": 0,
            "pad_right": 0,
        },
    }]
    for asset in payload["assets"]:
        node = {
            "id": _asset_node_id(asset["symbol"]),
            "type": "image",
            "parent_id": "root",
            "src": asset["symbol"],
            "src_expr": f"&{asset['symbol']}",
            "source_bbox": list(asset["bbox"]),
            "layout_exception_reason": f"user-confirmed full-canvas bbox for {asset['symbol']}",
        }
        if asset["scale"] == "stretch":
            node["image_fit"] = "stretch"
        nodes.append(node)
    for element in payload.get("elements", []):
        styles = dict(element.get("styles", {}))
        font_role = element.get("font_role")
        if font_role:
            styles["font"] = f"&{font_symbols[font_role]}"
            styles["font_role"] = font_role
            styles["font_id"] = font_symbols[font_role]
        node = {
            "id": element["id"],
            "type": element["type"],
            "parent_id": element.get("parent_id", "root"),
            "source_bbox": list(element["bbox"]),
            "layout_exception_reason": element.get("layout_exception_reason", "user-confirmed page_input bbox"),
            "styles": styles,
        }
        for key in ("text", "text_macro", "value", "range_min", "range_max", "layout"):
            if key in element:
                node[key] = element[key]
        nodes.append(node)
    spec: dict[str, Any] = {
        "schema_version": "2.0",
        "page_name": payload["page_id"],
        "display": {"width": width, "height": height},
        "lvgl_version": "v9",
        "nodes": nodes,
        "assets": [],
        "asset_bundle": {"header": asset_header},
    }
    if font_header:
        spec["fonts"] = [
            {"symbol": symbol, "role": role}
            for role, symbol in font_symbols.items()
        ]
        spec["font_bundle"] = {"header": font_header}
    return spec
