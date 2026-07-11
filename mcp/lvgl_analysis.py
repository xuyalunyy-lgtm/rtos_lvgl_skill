"""Visual analysis engine for LVGL design images.

Detects regions, text, colors, layout candidates, and cutout matches.
Output conforms to schemas/lvgl_analysis_report_v1.schema.json.

Usage:
    python mcp/lvgl_analysis.py --design path/to/design.png --width 480 --height 800 --json
    python mcp/lvgl_analysis.py --design path/to/design.png --cuts path/to/cuts/ --json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageOps
    import numpy as np
except ImportError:
    Image = None  # type: ignore
    np = None  # type: ignore

ROOT = Path(__file__).resolve().parent.parent

# ── Color analysis ────────────────────────────────────────────────


def _dominant_colors(img: Image.Image, max_colors: int = 8, sample_step: int = 4) -> list[dict[str, Any]]:
    """Extract dominant colors by sampling and clustering."""
    if np is None:
        return _dominant_colors_pillow(img, max_colors, sample_step)
    return _dominant_colors_numpy(img, max_colors, sample_step)


def _dominant_colors_pillow(img: Image.Image, max_colors: int, sample_step: int) -> list[dict[str, Any]]:
    """Fallback color extraction using Pillow only."""
    small = img.resize((img.width // sample_step, img.height // sample_step))
    rgb = small.convert("RGB")
    pixels = list(rgb.getdata())
    # Simple histogram
    color_count: dict[tuple, int] = {}
    for p in pixels:
        # Quantize to reduce noise
        q = (p[0] // 32 * 32, p[1] // 32 * 32, p[2] // 32 * 32)
        color_count[q] = color_count.get(q, 0) + 1
    total = len(pixels)
    sorted_colors = sorted(color_count.items(), key=lambda x: x[1], reverse=True)[:max_colors]
    return [
        {"hex": f"#{r:02x}{g:02x}{b:02x}", "ratio": round(count / total, 3)}
        for (r, g, b), count in sorted_colors
    ]


def _dominant_colors_numpy(img: Image.Image, max_colors: int, sample_step: int) -> list[dict[str, Any]]:
    """Color extraction using numpy k-means-like clustering."""
    small = img.resize((img.width // sample_step, img.height // sample_step))
    rgb = np.array(small.convert("RGB")).reshape(-1, 3)
    # Quantize
    quantized = (rgb // 32) * 32
    unique, counts = np.unique(quantized, axis=0, return_counts=True)
    total = len(rgb)
    top_idx = np.argsort(-counts)[:max_colors]
    results = []
    for idx in top_idx:
        r, g, b = unique[idx]
        ratio = float(counts[idx]) / total
        # Determine role heuristic
        brightness = (int(r) + int(g) + int(b)) / 3
        role = "background" if ratio > 0.3 else ("text" if brightness < 80 else "primary")
        results.append({"hex": f"#{int(r):02x}{int(g):02x}{int(b):02x}", "ratio": round(ratio, 3), "role": role})
    return results


# ── Region detection ──────────────────────────────────────────────


def _detect_rectangles(img: Image.Image, min_area: int = 500, max_regions: int = 64) -> list[dict[str, Any]]:
    """Detect rectangular regions by edge detection and contour finding."""
    gray = img.convert("L")
    # Edge detection
    edges = gray.filter(ImageFilter.FIND_EDGES)
    # Threshold
    edges = edges.point(lambda x: 255 if x > 30 else 0)
    # Find bounding boxes of edge clusters
    if np is None:
        return _detect_rectangles_pillow(edges, min_area, max_regions)
    return _detect_rectangles_numpy(edges, min_area, max_regions)


def _detect_rectangles_pillow(edges: Image.Image, min_area: int, max_regions: int) -> list[dict[str, Any]]:
    """Fallback rectangle detection using Pillow."""
    regions = []
    bbox = edges.getbbox()
    if bbox:
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        if w * h >= min_area:
            regions.append({
                "id": f"region_0",
                "type": "container",
                "bbox": list(bbox),
                "confidence": 0.5,
                "evidence": ["edge_detection"],
            })
    return regions[:max_regions]


def _detect_rectangles_numpy(edges: Image.Image, min_area: int, max_regions: int) -> list[dict[str, Any]]:
    """Rectangle detection using numpy connected components."""
    arr = np.array(edges)
    # Simple connected component via row scanning
    rows, cols = np.where(arr > 0)
    if len(rows) == 0:
        return []
    # Find bounding box of all edge pixels
    y_min, y_max = int(rows.min()), int(rows.max())
    x_min, x_max = int(cols.min()), int(cols.max())
    # Split into grid cells
    cell_h = max(40, (y_max - y_min) // 8)
    cell_w = max(40, (x_max - x_min) // 8)
    regions = []
    idx = 0
    for cy in range(y_min, y_max, cell_h):
        for cx in range(x_min, x_max, cell_w):
            mask = (rows >= cy) & (rows < cy + cell_h) & (cols >= cx) & (cols < cx + cell_w)
            count = mask.sum()
            if count < 10:
                continue
            # Get tight bbox of edge pixels in this cell
            cell_rows = rows[mask]
            cell_cols = cols[mask]
            bx0, by0 = int(cell_cols.min()), int(cell_rows.min())
            bx1, by1 = int(cell_cols.max()), int(cell_rows.max())
            area = (bx1 - bx0) * (by1 - by0)
            if area < min_area:
                continue
            regions.append({
                "id": f"region_{idx}",
                "type": "container",
                "bbox": [bx0, by0, bx1 - bx0, by1 - by0],
                "confidence": min(0.9, 0.5 + count / 100),
                "evidence": ["edge_cluster"],
            })
            idx += 1
            if idx >= max_regions:
                break
        if idx >= max_regions:
            break
    return regions


# ── Text detection (basic) ────────────────────────────────────────


def _detect_text_regions(img: Image.Image, min_height: int = 10, max_height: int = 80) -> list[dict[str, Any]]:
    """Detect text-like regions by horizontal line analysis."""
    gray = img.convert("L")
    arr = np.array(gray) if np is not None else None
    if arr is None:
        return []
    # Find rows with many transitions (text-like)
    diff = np.abs(np.diff(arr.astype(int), axis=1))
    row_activity = (diff > 20).sum(axis=1)
    # Find contiguous text blocks
    text_rows = np.where(row_activity > arr.shape[1] * 0.1)[0]
    if len(text_rows) == 0:
        return []
    # Group contiguous rows
    blocks = []
    start = text_rows[0]
    for i in range(1, len(text_rows)):
        if text_rows[i] - text_rows[i - 1] > 5:
            blocks.append((start, text_rows[i - 1]))
            start = text_rows[i]
    blocks.append((start, text_rows[-1]))
    # Filter by height
    text_regions = []
    for i, (y0, y1) in enumerate(blocks):
        h = y1 - y0
        if h < min_height or h > max_height:
            continue
        # Find horizontal extent
        row_slice = arr[y0:y1 + 1]
        cols_with_content = np.where(row_slice.mean(axis=0) < 200)[0]
        if len(cols_with_content) == 0:
            continue
        x0, x1 = int(cols_with_content[0]), int(cols_with_content[-1])
        text_regions.append({
            "id": f"text_{i}",
            "type": "label",
            "bbox": [x0, y0, x1 - x0, y1 - y0],
            "confidence": 0.6,
            "evidence": ["horizontal_activity"],
        })
    return text_regions


# ── Cutout matching ───────────────────────────────────────────────


def _match_cutouts(img: Image.Image, cut_details: list[dict[str, Any]], threshold: float = 0.8) -> list[dict[str, Any]]:
    """Match cutout images against design using template matching."""
    if np is None or not cut_details:
        return []
    design_arr = np.array(img.convert("RGB"))
    matches = []
    for cut_info in cut_details:
        cut_path = Path(cut_info["path"])
        if not cut_path.is_file():
            continue
        try:
            cut_img = Image.open(cut_path)
            cut_arr = np.array(cut_img.convert("RGB"))
        except Exception:
            continue
        ch, cw = cut_arr.shape[:2]
        dh, dw = design_arr.shape[:2]
        if ch > dh or cw > dw:
            continue
        # Simple template matching (normalized cross-correlation)
        best_score = 0.0
        best_pos = (0, 0)
        step = max(1, min(ch, cw) // 4)
        for y in range(0, dh - ch + 1, step):
            for x in range(0, dw - cw + 1, step):
                patch = design_arr[y:y + ch, x:x + cw]
                if patch.shape != cut_arr.shape:
                    continue
                # Normalized correlation
                diff = np.abs(patch.astype(float) - cut_arr.astype(float))
                score = 1.0 - diff.mean() / 255.0
                if score > best_score:
                    best_score = score
                    best_pos = (x, y)
        if best_score >= threshold:
            # Refine position
            x, y = best_pos
            for dy in range(-step, step + 1):
                for dx in range(-step, step + 1):
                    ny, nx = y + dy, x + dx
                    if ny < 0 or nx < 0 or ny + ch > dh or nx + cw > dw:
                        continue
                    patch = design_arr[ny:ny + ch, nx:nx + cw]
                    diff = np.abs(patch.astype(float) - cut_arr.astype(float))
                    score = 1.0 - diff.mean() / 255.0
                    if score > best_score:
                        best_score = score
                        best_pos = (nx, ny)
            x, y = best_pos
            matches.append({
                "cutout_path": str(cut_path),
                "bbox": [x, y, cw, ch],
                "confidence": round(best_score, 3),
                "status": "used_cutout",
                "improvement_score": round(best_score - 0.5, 3),
            })
    return matches


# ── Layout inference ──────────────────────────────────────────────


def _infer_layouts(regions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Infer Flex/Grid layout candidates from region positions."""
    if len(regions) < 2:
        return []
    layouts = []
    # Check for horizontal alignment (flex-row)
    for i in range(len(regions)):
        for j in range(i + 1, len(regions)):
            r1 = regions[i]
            r2 = regions[j]
            b1, b2 = r1["bbox"], r2["bbox"]
            # Check vertical alignment (same y)
            if abs(b1[1] - b2[1]) < 20:
                layouts.append({
                    "region_ids": [r1["id"], r2["id"]],
                    "mode": "flex-row",
                    "confidence": 0.7,
                    "gap_estimate": abs(b2[0] - b1[0] - b1[2]),
                })
            # Check horizontal alignment (same x)
            if abs(b1[0] - b2[0]) < 20:
                layouts.append({
                    "region_ids": [r1["id"], r2["id"]],
                    "mode": "flex-column",
                    "confidence": 0.7,
                    "gap_estimate": abs(b2[1] - b1[1] - b1[3]),
                })
    return layouts


# ── Main analysis ─────────────────────────────────────────────────


def analyze(
    design_path: str,
    screen_width: int,
    screen_height: int,
    lvgl_version: str = "v9",
    cut_dir: str | None = None,
    output_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Run visual analysis on a design image.

    Args:
        design_path: Path to design screenshot.
        screen_width: Target screen width.
        screen_height: Target screen height.
        lvgl_version: Target LVGL version.
        cut_dir: Optional directory with cutout assets.
        output_dir: Artifact directory. Defaults beside the design only for
            legacy direct callers; high-level MCP calls always pass artifacts/.

    Returns:
        Analysis report conforming to lvgl_analysis_report_v1.schema.json.
    """
    errors: list[str] = []
    warnings: list[str] = []

    if Image is None:
        errors.append("Pillow not installed")
        return {"ok": False, "errors": errors}

    design = Path(design_path)
    if not design.is_file():
        errors.append(f"Design image not found: {design_path}")
        return {"ok": False, "errors": errors}

    img = Image.open(design)
    page_name = design.stem
    artifact_dir = Path(output_dir) if output_dir is not None else design.parent
    artifact_dir.mkdir(parents=True, exist_ok=True)

    # ── Color analysis ──
    colors = _dominant_colors(img)

    # ── Region detection ──
    regions = _detect_rectangles(img)

    # ── Text detection ──
    text_regions = _detect_text_regions(img)
    # Merge text regions into regions list
    for tr in text_regions:
        tr["id"] = f"region_{len(regions)}"
        regions.append(tr)

    # ── Layout inference ──
    layouts = _infer_layouts(regions)

    # ── Cutout matching ──
    cut_matches: list[dict[str, Any]] = []
    if cut_dir:
        cuts_path = Path(cut_dir)
        if cuts_path.is_dir():
            cut_files = [p for p in cuts_path.iterdir() if p.is_file() and p.suffix.lower() in {".png", ".jpg", ".jpeg", ".bmp"}]
            cut_details = [{"path": str(p)} for p in cut_files]
            cut_matches = _match_cutouts(img, cut_details)

    # ── Generate overlay ──
    overlay_path = artifact_dir / "debug_overlay.png"
    try:
        _generate_overlay(img, regions, cut_matches, overlay_path)
    except Exception:
        warnings.append("Failed to generate debug overlay")

    # ── Compute overall confidence ──
    confidences = [r["confidence"] for r in regions]
    avg_confidence = round(sum(confidences) / len(confidences), 3) if confidences else 0.0

    # ── Convert numpy types to Python types for JSON serialization ──
    def _to_python(obj):
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, dict):
            return {k: _to_python(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_to_python(v) for v in obj]
        return obj

    regions = _to_python(regions)
    cut_matches = _to_python(cut_matches)
    layouts = _to_python(layouts)
    colors = _to_python(colors)

    # ── Build report ──
    report = {
        "schema_version": "1.0",
        "page_name": page_name,
        "screen": {
            "width": screen_width,
            "height": screen_height,
            "lvgl_version": lvgl_version,
            "color_depth": 16,
        },
        "detected_regions": regions,
        "detected_text": [],  # TODO: extract actual text via OCR
        "color_palette": colors,
        "layout_candidates": layouts,
        "cutout_matches": cut_matches,
        "confidence": avg_confidence,
        "uncertain_regions": [
            {"bbox": r["bbox"], "reason": "low confidence", "candidates": ["container", "label"]}
            for r in regions if r["confidence"] < 0.6
        ],
        "questions": [],
        "overlay_path": str(overlay_path),
        "metadata": {
            "image_width": img.width,
            "image_height": img.height,
        },
    }

    # Save report
    report_path = artifact_dir / "analysis_report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    return {"ok": True, "report": report, "report_path": str(report_path)}


def _generate_overlay(img: Image.Image, regions: list[dict], matches: list[dict], output_path: Path):
    """Generate debug overlay image with detected regions highlighted."""
    overlay = img.copy().convert("RGBA")
    draw = ImageDraw.Draw(overlay)
    # Draw regions
    for r in regions:
        x, y, w, h = r["bbox"]
        conf = r["confidence"]
        color = (0, 255, 0, 128) if conf >= 0.7 else (255, 255, 0, 128) if conf >= 0.5 else (255, 0, 0, 128)
        draw.rectangle([x, y, x + w, y + h], outline=color[:3], width=2)
        draw.text((x + 2, y + 2), f"{r['id']} ({conf:.2f})", fill=color[:3])
    # Draw cutout matches
    for m in matches:
        x, y, w, h = m["bbox"]
        draw.rectangle([x, y, x + w, y + h], outline=(0, 0, 255), width=2)
    overlay.save(str(output_path))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--design", required=True, help="Path to design screenshot")
    parser.add_argument("--width", type=int, required=True, help="Target screen width")
    parser.add_argument("--height", type=int, required=True, help="Target screen height")
    parser.add_argument("--lvgl-version", default="v9", choices=["v8", "v9"])
    parser.add_argument("--cuts", help="Directory containing cutout assets")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    result = analyze(
        design_path=args.design,
        screen_width=args.width,
        screen_height=args.height,
        lvgl_version=args.lvgl_version,
        cut_dir=args.cuts,
    )

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        if result.get("ok"):
            report = result["report"]
            print(f"Page: {report['page_name']}")
            print(f"Regions: {len(report['detected_regions'])}")
            print(f"Colors: {len(report['color_palette'])}")
            print(f"Layouts: {len(report['layout_candidates'])}")
            print(f"Confidence: {report['confidence']}")
        else:
            for err in result.get("errors", []):
                print(f"ERROR: {err}")

    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
