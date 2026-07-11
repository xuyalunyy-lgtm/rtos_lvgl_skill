"""UI Spec v2 Validator — structural and semantic validation.

Validates the JSON IR before scene encoding or code generation.
Catches empty specs, duplicate IDs, broken parent chains,
out-of-bounds bboxes, and unresolved image assets.

Usage:
    from mcp.lvgl_ir.spec_validator import validate_spec
    result = validate_spec(spec, asset_pack_path="assets.pack", display={"width": 480, "height": 800})
"""
from __future__ import annotations

from pathlib import Path
from typing import Any


# ── Public API ────────────────────────────────────────────────────


def validate_spec(
    spec: dict[str, Any],
    *,
    asset_pack_path: str | None = None,
    display: dict[str, Any] | None = None,
    expected_lvgl_version: str = "v9",
) -> dict[str, Any]:
    """Validate a UI Spec v2 document.

    Args:
        spec: The UI Spec dict to validate.
        asset_pack_path: Optional path to .pack file for image src resolution.
        display: Optional display config override (width/height). Falls back to spec's own display.
        expected_lvgl_version: Required LVGL version (default "v9").

    Returns:
        {
            "valid": bool,
            "errors": [str, ...],
            "warnings": [str, ...],
            "status": "invalid_input" | "generated"
        }
    """
    errors: list[str] = []
    warnings: list[str] = []

    # ── Type check ───────────────────────────────────────────────
    if not isinstance(spec, dict):
        return _result(False, ["UI Spec must be a JSON object"], [])

    # ── schema_version ───────────────────────────────────────────
    if spec.get("schema_version") != "2.0":
        errors.append("schema_version must be \"2.0\"")

    # ── page_name ────────────────────────────────────────────────
    page_name = spec.get("page_name")
    if not isinstance(page_name, str) or not page_name:
        errors.append("page_name is required and must be a non-empty string")

    # ── display ──────────────────────────────────────────────────
    spec_display = spec.get("display")
    if not isinstance(spec_display, dict):
        errors.append("display is required and must be an object with width/height")
        width, height = 480, 800  # fallback for further checks
    else:
        width = spec_display.get("width", 480)
        height = spec_display.get("height", 800)
        if not isinstance(width, int) or width < 1:
            errors.append(f"display.width must be a positive integer, got {width!r}")
        if not isinstance(height, int) or height < 1:
            errors.append(f"display.height must be a positive integer, got {height!r}")

    # Allow caller override
    if display and isinstance(display, dict):
        dw = display.get("width")
        dh = display.get("height")
        if isinstance(dw, int) and dw >= 1:
            width = dw
        if isinstance(dh, int) and dh >= 1:
            height = dh

    # ── lvgl_version ─────────────────────────────────────────────
    lvgl_ver = spec.get("lvgl_version")
    if lvgl_ver and lvgl_ver != expected_lvgl_version:
        errors.append(
            f"lvgl_version mismatch: spec says {lvgl_ver!r}, "
            f"runner expects {expected_lvgl_version!r}"
        )

    # ── nodes ────────────────────────────────────────────────────
    nodes = spec.get("nodes")
    if not isinstance(nodes, list) or len(nodes) == 0:
        errors.append("nodes must be a non-empty array")
        return _result(not errors, errors, warnings)

    for i, node in enumerate(nodes):
        if not isinstance(node, dict):
            errors.append(f"nodes[{i}] must be an object")
            continue

    # Filter to dict-only nodes for further checks
    valid_nodes = [n for n in nodes if isinstance(n, dict)]

    # ── Unique IDs ───────────────────────────────────────────────
    seen_ids: dict[str, int] = {}
    for i, node in enumerate(valid_nodes):
        nid = node.get("id")
        if not isinstance(nid, str) or not nid:
            errors.append(f"nodes[{i}].id must be a non-empty string")
        elif nid in seen_ids:
            errors.append(
                f"Duplicate node id {nid!r} at nodes[{seen_ids[nid]}] and nodes[{i}]"
            )
        else:
            seen_ids[nid] = i

    # ── Unique root ──────────────────────────────────────────────
    screen_nodes = [n for n in valid_nodes if n.get("type") == "screen"]
    if len(screen_nodes) == 0:
        errors.append("No root node (type=\"screen\") found")
    elif len(screen_nodes) > 1:
        ids = [n.get("id", "?") for n in screen_nodes]
        errors.append(f"Multiple root nodes found: {ids}. Exactly one screen node required.")

    root_id = screen_nodes[0].get("id") if screen_nodes else None

    # ── Parent chain ─────────────────────────────────────────────
    # Build parent map
    parent_map: dict[str, str | None] = {}
    for node in valid_nodes:
        nid = node.get("id", "")
        pid = node.get("parent_id")
        # Screen nodes must not have a parent
        if node.get("type") == "screen" and pid:
            errors.append(f"Root node {nid!r} must not have a parent_id")
        # Non-screen nodes must have a parent
        if node.get("type") != "screen" and not pid:
            errors.append(f"Node {nid!r} (type={node.get('type')!r}) has no parent_id")
        parent_map[nid] = pid

    # Walk parent chains — must reach root
    if root_id:
        for node in valid_nodes:
            nid = node.get("id", "")
            if nid == root_id:
                continue
            visited: set[str] = set()
            current = nid
            reached_root = False
            while current:
                if current == root_id:
                    reached_root = True
                    break
                if current in visited:
                    break  # cycle
                visited.add(current)
                current = parent_map.get(current)  # type: ignore[assignment]
            if not reached_root:
                errors.append(
                    f"Node {nid!r} parent chain does not reach root {root_id!r}"
                )

    # ── At least one visible child ───────────────────────────────
    non_root = [n for n in valid_nodes if n.get("type") != "screen"]
    if len(non_root) == 0:
        errors.append("Spec has only a root screen node — at least one child node required")

    # ── source_bbox validation ───────────────────────────────────
    for i, node in enumerate(valid_nodes):
        bbox = node.get("source_bbox")
        if bbox is None:
            continue
        if not isinstance(bbox, list) or len(bbox) != 4:
            errors.append(f"nodes[{i}].source_bbox must be [x, y, w, h]")
            continue
        x, y, w, h = bbox
        if not all(isinstance(v, (int, float)) for v in bbox):
            errors.append(f"nodes[{i}].source_bbox values must be numbers")
            continue
        if w <= 0 or h <= 0:
            errors.append(
                f"nodes[{i}].source_bbox width/height must be positive, got [{x},{y},{w},{h}]"
            )
        if x < 0 or y < 0:
            warnings.append(
                f"nodes[{i}].source_bbox has negative origin [{x},{y}]"
            )
        if x + w > width * 1.5 or y + h > height * 1.5:
            warnings.append(
                f"nodes[{i}].source_bbox [{x},{y},{w},{h}] extends well beyond "
                f"screen ({width}x{height})"
            )

    # ── Image src resolution ─────────────────────────────────────
    if asset_pack_path:
        try:
            from mcp.lvgl_ir.asset_pack import list_pack_symbols
            pack_symbols = set(list_pack_symbols(asset_pack_path))
        except Exception:
            pack_symbols = set()
            warnings.append(f"Could not read asset pack: {asset_pack_path}")
    else:
        pack_symbols = set()

    for i, node in enumerate(valid_nodes):
        if node.get("type") == "image":
            src = node.get("src")
            if not src:
                warnings.append(
                    f"nodes[{i}] is type=image but has no src"
                )
            elif pack_symbols and src.startswith("UI_IMG_") and src not in pack_symbols:
                errors.append(
                    f"nodes[{i}].src={src!r} not found in asset pack "
                    f"(available: {sorted(pack_symbols)[:10]})"
                )

    return _result(not errors, errors, warnings)


# ── Helpers ───────────────────────────────────────────────────────


def _result(
    valid: bool, errors: list[str], warnings: list[str]
) -> dict[str, Any]:
    return {
        "valid": valid,
        "errors": errors,
        "warnings": warnings,
        "status": "generated" if valid else "invalid_input",
    }
