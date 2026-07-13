"""Deterministic resolution of AI-authored image asset intents.

The AI contract describes *what* is needed.  This module is the only layer
allowed to decide which physical file is used and how it is encoded.
"""
from __future__ import annotations

import hashlib
import json
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from PIL import Image

from mcp.lvgl_ir.asset_pack import (
    encode_pack,
    list_pack_symbols,
    pack_asset,
    write_lvgl_v9_c_assets,
)

SCHEMA_VERSION = "1.0"
ALIAS_VERSION = "asset-name-aliases-v1"
ASSET_TYPES = {
    "full_screen_background",
    "transparent_character",
    "status_icon",
    "control_icon",
    "decorative_image",
    "state_image",
}
PHYSICAL_FIELDS = {"source_path", "width", "height", "format", "stride", "flash_bytes", "sha256"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp"}
_C_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_ALIASES = {
    "bg": "background", "background": "background",
    "pet": "character", "character": "character",
    "wifi": "wlan", "wlan": "wlan",
    "bt": "bluetooth", "bluetooth": "bluetooth",
    "battery": "power", "power": "power",
}


def _json_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_initial_manifest(manifest: Any) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(manifest, dict):
        return {"valid": False, "errors": ["manifest must be an object"]}
    if manifest.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    if not isinstance(manifest.get("project"), str) or not manifest.get("project", "").strip():
        errors.append("project is required")
    if not isinstance(manifest.get("design_reference"), str) or not manifest.get("design_reference", "").strip():
        errors.append("design_reference is required")
    display = manifest.get("display")
    if not isinstance(display, dict):
        errors.append("display is required")
    else:
        for key in ("width", "height"):
            if not isinstance(display.get(key), int) or display[key] <= 0:
                errors.append(f"display.{key} must be a positive integer")
        if display.get("rotation", 0) not in {0, 90, 180, 270}:
            errors.append("display.rotation must be 0, 90, 180, or 270")
        if display.get("color_format") != "RGB565":
            errors.append("display.color_format must be RGB565")
    assets = manifest.get("assets")
    if not isinstance(assets, list) or not assets:
        errors.append("assets must be a non-empty array")
        assets = []
    symbols: set[str] = set()
    portable_symbols: set[str] = set()
    for index, asset in enumerate(assets):
        prefix = f"assets[{index}]"
        if not isinstance(asset, dict):
            errors.append(f"{prefix} must be an object")
            continue
        forbidden = sorted(PHYSICAL_FIELDS.intersection(asset))
        if forbidden:
            errors.append(f"{prefix} contains forbidden physical fields: {', '.join(forbidden)}")
        symbol = asset.get("symbol")
        if not isinstance(symbol, str) or not _C_IDENTIFIER.fullmatch(symbol) or len(symbol.encode("ascii", errors="ignore")) > 31:
            errors.append(f"{prefix}.symbol must be a valid C identifier")
        elif symbol in symbols:
            errors.append(f"duplicate asset symbol: {symbol}")
        elif symbol.casefold() in portable_symbols:
            errors.append(f"asset symbols collide on case-insensitive filesystems: {symbol}")
        else:
            symbols.add(symbol)
            portable_symbols.add(symbol.casefold())
        if asset.get("type") not in ASSET_TYPES:
            errors.append(f"{prefix}.type is invalid")
        if not isinstance(asset.get("file_hint"), str) or not asset.get("file_hint", "").strip():
            errors.append(f"{prefix}.file_hint is required")
        bbox = asset.get("estimated_bbox")
        if bbox is not None and (not isinstance(bbox, list) or len(bbox) != 4 or not all(isinstance(v, int) for v in bbox)):
            errors.append(f"{prefix}.estimated_bbox must contain four integers")
        confidence = asset.get("confidence")
        if confidence is not None and (not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1):
            errors.append(f"{prefix}.confidence must be between 0 and 1")
    limits = manifest.get("limits")
    if limits is not None:
        if not isinstance(limits, dict) or not isinstance(limits.get("max_flash_bytes"), int) or limits["max_flash_bytes"] <= 0:
            errors.append("limits.max_flash_bytes must be a positive integer")
    return {"valid": not errors, "errors": errors}


def build_initial_manifest(
    *, project: str, design_reference: str, display: dict[str, Any], assets: list[dict[str, Any]], asset_root: str | None = None,
    max_flash_bytes: int | None = None,
) -> dict[str, Any]:
    manifest: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "project": project,
        "design_reference": design_reference,
        "display": {
            "width": int(display.get("width", 480)),
            "height": int(display.get("height", 800)),
            "rotation": int(display.get("rotation", 0)),
            "color_format": "RGB565",
        },
        "assets": assets,
    }
    if asset_root:
        manifest["asset_root"] = asset_root
    if max_flash_bytes is not None:
        manifest["limits"] = {"max_flash_bytes": int(max_flash_bytes)}
    return manifest


def write_initial_manifest(path: str | Path, manifest: dict[str, Any]) -> dict[str, Any]:
    validation = validate_initial_manifest(manifest)
    if not validation["valid"]:
        return {"ok": False, "status": "invalid_asset_contract", "errors": validation["errors"]}
    target = Path(path)
    _json_write(target, manifest)
    return {"ok": True, "status": "initial_asset_manifest_ready", "path": str(target), "manifest": manifest}


def _contained(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _tokens(value: str) -> list[str]:
    raw = re.findall(r"[a-z0-9]+", Path(value).stem.lower().replace("-", "_").replace(" ", "_"))
    return [_ALIASES.get(token, token) for token in raw if token not in {"ui", "img", "image", "icon"}]


def _normalized_stem(value: str) -> str:
    return "_".join(_tokens(value))


def _directory_matches(asset_type: str, relative: Path) -> bool:
    parts = tuple(part.lower() for part in relative.parts[:-1])
    if asset_type == "full_screen_background":
        return "backgrounds" in parts
    if asset_type == "transparent_character":
        return "characters" in parts
    if asset_type == "status_icon":
        return "icons" in parts and "system" in parts
    if asset_type == "control_icon":
        return "icons" in parts
    return True


def _score(file_hint: str, candidate: Path, relative: Path, asset_type: str) -> dict[str, float]:
    hint_tokens = set(_tokens(file_hint))
    candidate_tokens = set(_tokens(candidate.stem))
    coverage = len(hint_tokens.intersection(candidate_tokens)) / max(1, len(hint_tokens))
    similarity = SequenceMatcher(None, _normalized_stem(file_hint), _normalized_stem(candidate.stem)).ratio()
    directory = 1.0 if _directory_matches(asset_type, relative) else 0.0
    requested_suffix = Path(file_hint).suffix.lower()
    extension = 1.0 if not requested_suffix or requested_suffix == candidate.suffix.lower() else 0.0
    total = 0.45 * coverage + 0.30 * similarity + 0.15 * directory + 0.10 * extension
    return {"total": round(total, 6), "token_coverage": round(coverage, 6), "name_similarity": round(similarity, 6), "directory_match": directory, "extension_match": extension}


def _resolve_design_path(reference: str, package_root: Path, manifest_path: Path) -> Path | None:
    candidate = Path(reference)
    options = [candidate] if candidate.is_absolute() else [package_root / candidate, manifest_path.parent / candidate]
    for option in options:
        if option.is_file():
            return option.resolve()
    return None


def _match_intent(intent: dict[str, Any], candidates: list[Path], asset_root: Path) -> dict[str, Any]:
    hint = str(intent["file_hint"])
    asset_type = str(intent["type"])
    hint_path = Path(hint)
    if hint_path.is_absolute() or ".." in hint_path.parts:
        return {"ok": False, "reason": "file_hint_path_escape", "candidates": []}
    compatible = [(path, path.relative_to(asset_root)) for path in candidates if _directory_matches(asset_type, path.relative_to(asset_root))]
    direct = (asset_root / hint).resolve()
    if _contained(direct, asset_root) and direct.is_file() and _directory_matches(asset_type, direct.relative_to(asset_root)):
        return {"ok": True, "path": direct, "method": "exact_relative_path", "score": 1.0, "candidates": []}
    basename = [(p, rel) for p, rel in compatible if p.name.lower() == Path(hint).name.lower()]
    if len(basename) == 1:
        return {"ok": True, "path": basename[0][0], "method": "exact_filename", "score": 1.0, "candidates": []}
    if len(basename) > 1:
        return {"ok": False, "reason": "ambiguous_exact_filename", "candidates": [{"path": rel.as_posix(), "score": 1.0} for _, rel in basename]}
    normalized = [(p, rel) for p, rel in compatible if _normalized_stem(p.stem) == _normalized_stem(hint)]
    if len(normalized) == 1:
        return {"ok": True, "path": normalized[0][0], "method": "normalized_stem", "score": 1.0, "candidates": []}
    if len(normalized) > 1:
        return {"ok": False, "reason": "ambiguous_normalized_stem", "candidates": [{"path": rel.as_posix(), "score": 1.0} for _, rel in normalized]}
    scored = []
    for path, relative in compatible:
        detail = _score(hint, path, relative, asset_type)
        scored.append({"path": path, "relative": relative, **detail})
    scored.sort(key=lambda item: (-item["total"], item["relative"].as_posix().lower()))
    public = [{"path": item["relative"].as_posix(), "score": item["total"], "components": {key: item[key] for key in ("token_coverage", "name_similarity", "directory_match", "extension_match")}} for item in scored[:5]]
    if not scored:
        return {"ok": False, "reason": "no_type_compatible_candidate", "candidates": []}
    best, second = scored[0], scored[1]["total"] if len(scored) > 1 else 0.0
    if best["total"] < 0.78:
        return {"ok": False, "reason": "fuzzy_score_below_threshold", "candidates": public}
    if best["total"] - second < 0.12:
        return {"ok": False, "reason": "fuzzy_match_not_unique", "candidates": public}
    return {"ok": True, "path": best["path"], "method": "unique_fuzzy_match", "score": best["total"], "candidates": public}


def _inspect_and_pack(path: Path, intent: dict[str, Any], display: dict[str, Any]) -> dict[str, Any]:
    with Image.open(path) as image:
        original_size = list(image.size)
        mode = image.mode
        bands = list(image.getbands())
        has_alpha_band = "A" in bands or "transparency" in image.info
        alpha = image.convert("RGBA").getchannel("A")
        alpha_min, alpha_max = alpha.getextrema()
        meaningful_alpha = alpha_min < 255
        alpha_bbox = list(alpha.getbbox()) if alpha.getbbox() else None
    asset_type = intent["type"]
    if asset_type == "full_screen_background":
        rotation = int(display.get("rotation", 0))
        expected = [int(display["height"]), int(display["width"])] if rotation in {90, 270} else [int(display["width"]), int(display["height"])]
        if original_size != expected:
            return {"ok": False, "reason": "background_size_mismatch", "expected_size": expected, "actual_size": original_size}
        if meaningful_alpha:
            return {"ok": False, "reason": "background_has_effective_alpha", "alpha_extrema": [alpha_min, alpha_max]}
        color_format, auto_crop = "RGB565", False
    elif asset_type in {"transparent_character", "status_icon", "control_icon"}:
        if not has_alpha_band or not meaningful_alpha:
            return {"ok": False, "reason": "required_effective_alpha_missing", "mode": mode, "alpha_extrema": [alpha_min, alpha_max]}
        # Status-bar icons keep their source canvas. Their transparent padding
        # is part of the placement contract and prevents antialiased edge
        # pixels from touching the LVGL object's clipping boundary.
        color_format = "RGB565A8"
        auto_crop = asset_type != "status_icon"
    else:
        color_format, auto_crop = ("RGB565A8", True) if meaningful_alpha else ("RGB565", False)
    packed = pack_asset(path, str(intent["symbol"]), color_format, auto_crop=auto_crop)
    if not packed.get("ok"):
        return packed
    crop = packed["crop_offset"]
    return {
        "ok": True,
        "packed": packed,
        "original_size": original_size,
        "mode": mode,
        "channels": bands,
        "alpha_extrema": [alpha_min, alpha_max],
        "alpha_bbox": alpha_bbox,
        "converted_size": [packed["width"], packed["height"]],
        "crop_offset": [crop[0], crop[1]],
        "format": f"LV_COLOR_FORMAT_{color_format}",
        "stride": packed["width"] * 2,
        "flash_bytes": packed["flash_bytes"],
        "sha256": packed["sha256"],
    }


def resolve_asset_contract(
    manifest_path: str | Path, *, package_root: str | Path, asset_root: str | Path | None, output_dir: str | Path,
) -> dict[str, Any]:
    source_manifest = Path(manifest_path).resolve()
    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    try:
        manifest = json.loads(source_manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "status": "invalid_asset_contract", "errors": [f"cannot read Initial Manifest: {exc}"]}
    validation = validate_initial_manifest(manifest)
    if not validation["valid"]:
        return {"ok": False, "status": "invalid_asset_contract", "errors": validation["errors"]}
    package = Path(package_root).resolve()
    root_value = asset_root or manifest.get("asset_root") or package / "assets"
    assets_root = Path(root_value)
    if not assets_root.is_absolute():
        assets_root = (package / assets_root).resolve()
    else:
        assets_root = assets_root.resolve()
    if not assets_root.is_dir() or not _contained(assets_root, package):
        return {"ok": False, "status": "manual_required", "errors": ["asset_root must be an existing directory inside the UI package"]}
    design = _resolve_design_path(manifest["design_reference"], package, source_manifest)
    if design is None:
        return {"ok": False, "status": "manual_required", "errors": ["design_reference cannot be resolved; SHA256 exclusion cannot be enforced"]}
    design_hash = _sha256(design) if design else None
    candidates = sorted(
        [path.resolve() for path in assets_root.rglob("*") if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES and _contained(path, assets_root)],
        key=lambda path: path.relative_to(assets_root).as_posix().lower(),
    )
    report_items: list[dict[str, Any]] = []
    resolved_items: list[dict[str, Any]] = []
    packed_assets: list[dict[str, Any]] = []
    used_sources: dict[Path, tuple[str, bool]] = {}
    errors: list[str] = []
    for intent in manifest["assets"]:
        match = _match_intent(intent, candidates, assets_root)
        report: dict[str, Any] = {"symbol": intent["symbol"], "type": intent["type"], "file_hint": intent["file_hint"], "required": intent.get("required", True)}
        if not match["ok"]:
            report.update({"status": "manual_required", "reason": match["reason"], "candidates": match.get("candidates", [])})
            report_items.append(report)
            if intent.get("required", True): errors.append(f"{intent['symbol']}: {match['reason']}")
            continue
        path = Path(match["path"]).resolve()
        file_hash = _sha256(path)
        if (design and path == design) or (design_hash and file_hash == design_hash):
            report.update({"status": "manual_required", "reason": "design_reference_or_content_copy_forbidden"})
            report_items.append(report)
            errors.append(f"{intent['symbol']}: design reference cannot be a runtime asset")
            continue
        previous = used_sources.get(path)
        if previous and not (bool(intent.get("allow_shared_source", False)) and previous[1]):
            report.update({"status": "manual_required", "reason": "physical_source_already_bound", "bound_symbol": previous[0]})
            report_items.append(report)
            errors.append(f"{intent['symbol']}: source already bound to {previous[0]}")
            continue
        physical = _inspect_and_pack(path, intent, manifest["display"])
        if not physical.get("ok"):
            report.update({"status": "manual_required", "reason": physical.get("reason", physical.get("error", "asset_conversion_failed")), "physical": {key: value for key, value in physical.items() if key != "ok"}})
            report_items.append(report)
            errors.append(f"{intent['symbol']}: {report['reason']}")
            continue
        used_sources[path] = (intent["symbol"], bool(intent.get("allow_shared_source", False)))
        packed = physical.pop("packed")
        relative = path.relative_to(package).as_posix()
        resolved = {
            "symbol": intent["symbol"], "type": intent["type"], "source_path": relative,
            "match_method": match["method"], "match_score": match["score"], **physical,
        }
        for key in ("state", "layer", "estimated_bbox", "confidence"):
            if key in intent: resolved[key] = intent[key]
        resolved_items.append(resolved)
        packed_assets.append(packed)
        report.update({"status": "resolved", "source_path": relative, "match_method": match["method"], "match_score": match["score"], "candidates": match.get("candidates", [])})
        report_items.append(report)
    resolution_report = {
        "schema_version": "1.0", "resolver_version": "deterministic-asset-resolver-v1", "alias_version": ALIAS_VERSION,
        "asset_root": assets_root.relative_to(package).as_posix(), "design_reference": manifest["design_reference"],
        "design_sha256": design_hash, "items": report_items, "errors": errors,
    }
    total_flash_bytes = sum(item["flash_bytes"] for item in resolved_items)
    max_flash_bytes = manifest.get("limits", {}).get("max_flash_bytes")
    resolution_report["flash_budget"] = {"used_bytes": total_flash_bytes, "max_bytes": max_flash_bytes, "passed": max_flash_bytes is None or total_flash_bytes <= max_flash_bytes}
    if max_flash_bytes is not None and total_flash_bytes > max_flash_bytes:
        errors.append(f"asset flash budget exceeded: {total_flash_bytes} > {max_flash_bytes}")
        resolution_report["errors"] = errors
    _json_write(out / "asset_resolution_report.json", resolution_report)
    if errors:
        return {"ok": False, "status": "manual_required", "errors": errors, "resolution_report": str(out / "asset_resolution_report.json"), "resolved_assets": resolved_items}
    resolved_manifest = {
        "schema_version": "1.0", "project": manifest["project"], "display": manifest["display"],
        "source_initial_manifest_sha256": _sha256(source_manifest), "resolver_version": "deterministic-asset-resolver-v1",
        "assets": resolved_items, "total_flash_bytes": total_flash_bytes, "limits": manifest.get("limits", {}),
    }
    _json_write(out / "resolved_asset_manifest.json", resolved_manifest)
    pack_path = out / "asset.pack"
    pack_path.write_bytes(encode_pack(packed_assets))
    firmware = write_lvgl_v9_c_assets(packed_assets, out, stem="ui_auto_assets")
    expected = sorted(item["symbol"] for item in resolved_items)
    pack_symbols = sorted(list_pack_symbols(pack_path))
    definition_symbols = sorted(firmware["symbols"])
    source_names = sorted(Path(path).name for path in firmware["sources"])
    cmake_text = Path(firmware["cmake"]).read_text(encoding="utf-8")
    cmake_sources = sorted(name for name in source_names if name in cmake_text)
    closure = {
        "ok": expected == definition_symbols == pack_symbols and source_names == cmake_sources,
        "resolved_symbols": expected, "declared_symbols": expected, "defined_symbols": definition_symbols,
        "pack_symbols": pack_symbols, "source_files": source_names, "cmake_sources": cmake_sources,
        "missing_definitions": sorted(set(expected) - set(definition_symbols)),
        "missing_pack_symbols": sorted(set(expected) - set(pack_symbols)),
        "missing_cmake_sources": sorted(set(source_names) - set(cmake_sources)),
    }
    _json_write(out / "resource_closure_report.json", closure)
    if not closure["ok"]:
        return {"ok": False, "status": "manual_required", "errors": ["resource closure check failed"], "resource_closure": closure}
    return {
        "ok": True, "status": "asset_contract_ready", "resolved_manifest": str(out / "resolved_asset_manifest.json"),
        "resolution_report": str(out / "asset_resolution_report.json"), "resource_closure_report": str(out / "resource_closure_report.json"),
        "asset_pack_path": str(pack_path), "firmware_assets": firmware, "packed_assets": packed_assets,
        "resolved_assets": resolved_items, "resource_closure": closure,
    }
