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
            "reuse_scope": "page",
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
        "assets": assets,
        "fonts": [],
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
    if not isinstance(assets, list) or not assets:
        errors.append("assets must contain at least one confirmed asset")
    else:
        seen: set[str] = set()
        for index, asset in enumerate(assets):
            label = f"assets[{index}]"
            if not isinstance(asset, dict):
                errors.append(f"{label} must be an object")
                continue
            symbol = asset.get("symbol")
            if not isinstance(symbol, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", symbol):
                errors.append(f"{label}.symbol must be a C identifier")
            elif symbol in seen:
                errors.append(f"{label}.symbol is duplicated")
            else:
                seen.add(symbol)
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
    if not isinstance(fonts, list):
        errors.append("fonts must be an array")
    else:
        for index, font in enumerate(fonts):
            label = f"fonts[{index}]"
            if not isinstance(font, dict):
                errors.append(f"{label} must be an object")
                continue
            if not isinstance(font.get("role"), str) or not font["role"].strip():
                errors.append(f"{label}.role must be non-empty")
            if not isinstance(font.get("source"), str) or not font["source"].strip():
                errors.append(f"{label}.source must be non-empty")
            size = font.get("size")
            if size is not None and (not isinstance(size, int) or isinstance(size, bool) or size <= 0):
                errors.append(f"{label}.size must be a positive integer or null")

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
