"""Design preflight — input validation for the LVGL image-to-code pipeline.

Checks images, detects scaling, deduplicates cutouts, validates screen params.
Must run before visual analysis.

Usage:
    python mcp/lvgl_preflight.py --design path/to/design.png --width 480 --height 800
    python mcp/lvgl_preflight.py --design path/to/design.png --cuts path/to/cuts/ --json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

try:
    from PIL import Image
except ImportError:
    Image = None  # type: ignore

ROOT = Path(__file__).resolve().parent.parent
MAX_IMAGE_PIXELS = 4096 * 4096  # 16MP limit
MAX_FILE_SIZE_MB = 50
SUPPORTED_FORMATS = {".png", ".jpg", ".jpeg", ".bmp", ".ppm"}


def _file_hash(path: Path) -> str:
    """SHA256 hash of file contents."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _image_info(path: Path) -> dict[str, Any]:
    """Get image metadata without loading full pixel data."""
    if Image is None:
        return {"error": "Pillow not installed"}
    try:
        with Image.open(path) as img:
            return {
                "width": img.width,
                "height": img.height,
                "mode": img.mode,
                "format": img.format,
                "has_alpha": img.mode in ("RGBA", "LA", "PA"),
                "file_size_bytes": path.stat().st_size,
            }
    except Exception as e:
        return {"error": str(e)}


def _detect_scale_factor(design_w: int, design_h: int, screen_w: int, screen_h: int) -> float | None:
    """Detect if design is 2x/3x of target screen."""
    if screen_w == 0 or screen_h == 0:
        return None
    ratio_w = design_w / screen_w
    ratio_h = design_h / screen_h
    # Allow 5% tolerance
    for scale in [1.0, 1.5, 2.0, 3.0]:
        if abs(ratio_w - scale) < 0.05 and abs(ratio_h - scale) < 0.05:
            return scale
    return None


def _detect_transparency_bounds(img: Any) -> dict[str, Any]:
    """Detect transparent/empty borders in an RGBA image."""
    if img.mode != "RGBA":
        return {"has_alpha": False}
    alpha = img.getchannel("A")
    bbox = alpha.getbbox()
    if bbox is None:
        return {"has_alpha": True, "fully_transparent": True, "content_bbox": None}
    return {
        "has_alpha": True,
        "fully_transparent": False,
        "content_bbox": list(bbox),  # [left, upper, right, lower]
        "content_width": bbox[2] - bbox[0],
        "content_height": bbox[3] - bbox[1],
    }


def _deduplicate_cuts(cut_paths: list[Path]) -> dict[str, Any]:
    """Find duplicate cut images by hash."""
    seen: dict[str, list[str]] = {}
    for p in cut_paths:
        if not p.is_file():
            continue
        h = _file_hash(p)
        seen.setdefault(h, []).append(str(p))
    duplicates = {h: paths for h, paths in seen.items() if len(paths) > 1}
    unique = {h: paths[0] for h, paths in seen.items()}
    return {
        "total": len(cut_paths),
        "unique": len(unique),
        "duplicates": duplicates,
        "duplicate_count": sum(len(v) - 1 for v in duplicates.values()),
    }


def preflight(
    design_path: str,
    screen_width: int,
    screen_height: int,
    lvgl_version: str = "v9",
    cut_dir: str | None = None,
    max_pixels: int = MAX_IMAGE_PIXELS,
) -> dict[str, Any]:
    """Run preflight checks on design inputs.

    Args:
        design_path: Path to design screenshot.
        screen_width: Target screen width in pixels.
        screen_height: Target screen height in pixels.
        lvgl_version: Target LVGL version (v8 or v9).
        cut_dir: Optional directory containing cutout assets.
        max_pixels: Maximum allowed pixel count.

    Returns:
        Preflight result dict with status, errors, warnings, and metadata.
    """
    errors: list[str] = []
    warnings: list[str] = []
    metadata: dict[str, Any] = {}

    # ── Check Pillow ──
    if Image is None:
        errors.append("Pillow not installed. Run: pip install Pillow")
        return {"ok": False, "status": "failed", "errors": errors, "warnings": warnings, "metadata": metadata}

    # ── Validate design image ──
    design = Path(design_path)
    if not design.is_file():
        errors.append(f"Design image not found: {design_path}")
        return {"ok": False, "status": "failed", "errors": errors, "warnings": warnings, "metadata": metadata}

    if design.suffix.lower() not in SUPPORTED_FORMATS:
        errors.append(f"Unsupported image format: {design.suffix} (supported: {SUPPORTED_FORMATS})")

    info = _image_info(design)
    if "error" in info:
        errors.append(f"Cannot read design image: {info['error']}")
        return {"ok": False, "status": "failed", "errors": errors, "warnings": warnings, "metadata": metadata}

    metadata["design"] = {
        "path": str(design),
        "sha256": _file_hash(design),
        **info,
    }

    # ── Check pixel count ──
    total_pixels = info["width"] * info["height"]
    if total_pixels > max_pixels:
        errors.append(f"Image too large: {total_pixels} pixels (max: {max_pixels})")

    # ── Check file size ──
    if info["file_size_bytes"] > MAX_FILE_SIZE_MB * 1024 * 1024:
        errors.append(f"File too large: {info['file_size_bytes'] / 1024 / 1024:.1f}MB (max: {MAX_FILE_SIZE_MB}MB)")

    # ── Validate screen params ──
    if screen_width <= 0 or screen_height <= 0:
        errors.append(f"Invalid screen dimensions: {screen_width}x{screen_height}")
    if screen_width > 4096 or screen_height > 4096:
        warnings.append(f"Unusually large screen: {screen_width}x{screen_height}")

    metadata["screen"] = {
        "width": screen_width,
        "height": screen_height,
        "lvgl_version": lvgl_version,
    }

    # ── Detect scale factor ──
    if screen_width > 0 and screen_height > 0:
        scale = _detect_scale_factor(info["width"], info["height"], screen_width, screen_height)
        if scale is not None:
            metadata["design"]["scale_factor"] = scale
            if scale != 1.0:
                warnings.append(f"Design appears to be {scale}x of target screen ({info['width']}x{info['height']} vs {screen_width}x{screen_height})")
        else:
            aspect_design = info["width"] / info["height"]
            aspect_screen = screen_width / screen_height
            if abs(aspect_design - aspect_screen) > 0.1:
                warnings.append(f"Aspect ratio mismatch: design {aspect_design:.2f} vs screen {aspect_screen:.2f}")

    # ── Check alpha channel ──
    if info["has_alpha"]:
        metadata["design"]["alpha"] = _detect_transparency_bounds(Image.open(design))
    else:
        warnings.append("Design image has no alpha channel")

    # ── Process cutout assets ──
    if cut_dir:
        cuts_path = Path(cut_dir)
        if not cuts_path.is_dir():
            errors.append(f"Cut directory not found: {cut_dir}")
        else:
            cut_files = [p for p in cuts_path.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED_FORMATS]
            if not cut_files:
                warnings.append(f"No cut images found in {cut_dir}")
            else:
                dedup = _deduplicate_cuts(cut_files)
                metadata["cuts"] = {
                    "directory": str(cuts_path),
                    "files": [str(p) for p in cut_files],
                    "deduplication": dedup,
                }
                if dedup["duplicate_count"] > 0:
                    warnings.append(f"Found {dedup['duplicate_count']} duplicate cut images")

                # Check each cut image
                cut_details = []
                for cf in cut_files:
                    ci = _image_info(cf)
                    detail = {"path": str(cf), "sha256": _file_hash(cf), **ci}
                    if "error" not in ci:
                        ci_pixels = ci["width"] * ci["height"]
                        if ci_pixels > max_pixels:
                            errors.append(f"Cut image too large: {cf.name} ({ci_pixels} pixels)")
                        if ci["has_alpha"]:
                            with Image.open(cf) as img:
                                detail["alpha"] = _detect_transparency_bounds(img)
                    cut_details.append(detail)
                metadata["cuts"]["details"] = cut_details

    # ── Validate LVGL version ──
    if lvgl_version not in ("v8", "v9"):
        errors.append(f"Unsupported LVGL version: {lvgl_version} (must be v8 or v9)")

    # ── Determine status ──
    if errors:
        status = "failed"
        ok = False
    elif warnings:
        status = "passed_with_warnings"
        ok = True
    else:
        status = "passed"
        ok = True

    # ── Generate input manifest ──
    manifest = {
        "schema_version": "1.0",
        "design": metadata.get("design", {}),
        "screen": metadata.get("screen", {}),
        "cuts": metadata.get("cuts", {}),
    }
    manifest_path = design.parent / "input_manifest.json"
    try:
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        metadata["manifest_path"] = str(manifest_path)
    except Exception:
        pass  # Non-critical

    return {
        "ok": ok,
        "status": status,
        "errors": errors,
        "warnings": warnings,
        "metadata": metadata,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--design", required=True, help="Path to design screenshot")
    parser.add_argument("--width", type=int, required=True, help="Target screen width")
    parser.add_argument("--height", type=int, required=True, help="Target screen height")
    parser.add_argument("--lvgl-version", default="v9", choices=["v8", "v9"])
    parser.add_argument("--cuts", help="Directory containing cutout assets")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    result = preflight(
        design_path=args.design,
        screen_width=args.width,
        screen_height=args.height,
        lvgl_version=args.lvgl_version,
        cut_dir=args.cuts,
    )

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"Status: {result['status']}")
        for err in result["errors"]:
            print(f"  ERROR: {err}")
        for warn in result["warnings"]:
            print(f"  WARN: {warn}")
        if result["metadata"].get("design", {}).get("scale_factor"):
            print(f"  Scale: {result['metadata']['design']['scale_factor']}x")

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
