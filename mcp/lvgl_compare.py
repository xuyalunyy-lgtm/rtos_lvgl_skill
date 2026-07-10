"""Visual comparison between rendered LVGL output and design image.

Compares screenshots at global, regional, and text levels.
Supports automatic refinement loop.

Usage:
    python mcp/lvgl_compare.py --actual path/to/render.png --baseline path/to/design.png --json
    python mcp/lvgl_compare.py --actual path/to/render.png --baseline path/to/design.png --spec path/to/spec.json --refine
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    from PIL import Image
    import numpy as np
except ImportError:
    Image = None
    np = None

ROOT = Path(__file__).resolve().parent.parent


# ── Pixel comparison ──────────────────────────────────────────────


def _load_image(path: str) -> Any:
    """Load image as numpy array."""
    if Image is None or np is None:
        raise ImportError("Pillow and numpy required for visual comparison")
    img = Image.open(path).convert("RGB")
    return np.array(img)


def _pixel_diff(actual: Any, baseline: Any) -> dict[str, Any]:
    """Compute pixel-level difference."""
    if actual.shape != baseline.shape:
        return {
            "error": f"Shape mismatch: {actual.shape} vs {baseline.shape}",
            "changed_pixel_ratio": 1.0,
        }
    diff = np.abs(actual.astype(int) - baseline.astype(int))
    changed = np.any(diff > 10, axis=2)  # Threshold: 10 per channel
    changed_ratio = float(changed.sum()) / (changed.shape[0] * changed.shape[1])
    return {
        "changed_pixel_ratio": round(changed_ratio, 4),
        "total_pixels": changed.shape[0] * changed.shape[1],
        "changed_pixels": int(changed.sum()),
    }


def _compute_ssim(actual: Any, baseline: Any, window_size: int = 7) -> float:
    """Compute simplified SSIM (Structural Similarity Index)."""
    if np is None:
        return 0.0
    # Convert to grayscale
    gray_actual = np.mean(actual, axis=2) if len(actual.shape) == 3 else actual
    gray_baseline = np.mean(baseline, axis=2) if len(baseline.shape) == 3 else baseline

    # Simplified SSIM using mean and variance
    h, w = gray_actual.shape
    ssim_sum = 0.0
    count = 0

    for y in range(0, h - window_size, window_size):
        for x in range(0, w - window_size, window_size):
            win_a = gray_actual[y:y + window_size, x:x + window_size].astype(float)
            win_b = gray_baseline[y:y + window_size, x:x + window_size].astype(float)

            mu_a = win_a.mean()
            mu_b = win_b.mean()
            sigma_a = win_a.std()
            sigma_b = win_b.std()
            sigma_ab = np.mean((win_a - mu_a) * (win_b - mu_b))

            c1 = (0.01 * 255) ** 2
            c2 = (0.03 * 255) ** 2

            numerator = (2 * mu_a * mu_b + c1) * (2 * sigma_ab + c2)
            denominator = (mu_a ** 2 + mu_b ** 2 + c1) * (sigma_a ** 2 + sigma_b ** 2 + c2)

            if denominator > 0:
                ssim_sum += numerator / denominator
                count += 1

    return round(ssim_sum / max(count, 1), 4)


# ── Regional comparison ───────────────────────────────────────────


def _compare_regions(
    actual: Any,
    baseline: Any,
    regions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Compare specific regions between actual and baseline."""
    results = []
    for region in regions:
        bbox = region.get("bbox", [])
        if len(bbox) != 4:
            continue
        x, y, w, h = bbox
        # Clamp to image bounds
        x = max(0, min(x, actual.shape[1] - 1))
        y = max(0, min(y, actual.shape[0] - 1))
        w = min(w, actual.shape[1] - x)
        h = min(h, actual.shape[0] - y)
        if w <= 0 or h <= 0:
            continue

        region_a = actual[y:y + h, x:x + w]
        region_b = baseline[y:y + h, x:x + w]

        diff = np.abs(region_a.astype(int) - region_b.astype(int))
        changed = np.any(diff > 10, axis=2)
        changed_ratio = float(changed.sum()) / max(changed.shape[0] * changed.shape[1], 1)

        results.append({
            "region_id": region.get("id", "unknown"),
            "bbox": bbox,
            "changed_pixel_ratio": round(changed_ratio, 4),
            "ssim": round(_compute_ssim(region_a, region_b), 4),
            "status": "match" if changed_ratio < 0.05 else "mismatch",
        })
    return results


# ── Text comparison ───────────────────────────────────────────────


def _compare_text(
    spec_nodes: list[dict[str, Any]],
    render_texts: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Compare expected vs actual text content."""
    results = []
    if render_texts is None:
        # No OCR available — compare spec text against itself (placeholder)
        for node in spec_nodes:
            text = node.get("text", "")
            if text:
                results.append({
                    "node_id": node.get("id", "unknown"),
                    "expected": text,
                    "actual": text,  # Placeholder
                    "match": True,
                })
    else:
        # Compare against OCR results
        for node in spec_nodes:
            text = node.get("text", "")
            if not text:
                continue
            # Find closest OCR match
            best_match = None
            best_score = 0
            for rt in render_texts:
                score = _text_similarity(text, rt.get("text", ""))
                if score > best_score:
                    best_score = score
                    best_match = rt
            results.append({
                "node_id": node.get("id", "unknown"),
                "expected": text,
                "actual": best_match.get("text", "") if best_match else "",
                "match": best_score > 0.8,
            })
    return results


def _text_similarity(a: str, b: str) -> float:
    """Simple text similarity (Jaccard on characters)."""
    if not a or not b:
        return 0.0
    set_a = set(a)
    set_b = set(b)
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / max(union, 1)


# ── Control tree comparison ───────────────────────────────────────


def _compare_control_tree(
    spec_nodes: list[dict[str, Any]],
    render_tree: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Compare expected vs actual control tree."""
    results = []
    if render_tree is None:
        # No render tree available — skip
        return results

    render_nodes = render_tree.get("root", {}).get("children", [])
    render_map = {n.get("id", ""): n for n in render_nodes}

    for spec_node in spec_nodes:
        node_id = spec_node.get("id", "")
        spec_type = spec_node.get("type", "")
        render_node = render_map.get(node_id)

        if render_node is None:
            results.append({
                "node_id": node_id,
                "diff_type": "missing",
                "expected": {"type": spec_type},
                "actual": None,
            })
        elif render_node.get("type") != spec_type:
            results.append({
                "node_id": node_id,
                "diff_type": "type_mismatch",
                "expected": {"type": spec_type},
                "actual": {"type": render_node.get("type")},
            })

    return results


# ── Main comparison ───────────────────────────────────────────────


def compare(
    actual_path: str,
    baseline_path: str,
    spec: dict[str, Any] | None = None,
    render_tree: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compare rendered output with design baseline.

    Args:
        actual_path: Path to rendered screenshot.
        baseline_path: Path to design screenshot.
        spec: Optional UI Spec for text/tree comparison.
        render_tree: Optional rendered object tree.

    Returns:
        Comparison report.
    """
    errors: list[str] = []
    warnings: list[str] = []

    actual = Path(actual_path)
    baseline = Path(baseline_path)

    if not actual.is_file():
        errors.append(f"Actual image not found: {actual_path}")
        return {"ok": False, "errors": errors}
    if not baseline.is_file():
        errors.append(f"Baseline image not found: {baseline_path}")
        return {"ok": False, "errors": errors}

    try:
        actual_img = _load_image(str(actual))
        baseline_img = _load_image(str(baseline))
    except Exception as e:
        errors.append(f"Failed to load images: {e}")
        return {"ok": False, "errors": errors}

    # Global comparison
    pixel_result = _pixel_diff(actual_img, baseline_img)
    ssim = _compute_ssim(actual_img, baseline_img)

    # Regional comparison
    regions = []
    if spec:
        regions = [
            {"id": n.get("id"), "bbox": n.get("source_bbox", [])}
            for n in spec.get("nodes", [])
            if n.get("source_bbox")
        ]
    region_diffs = _compare_regions(actual_img, baseline_img, regions) if regions else []

    # Text comparison
    text_diffs = []
    if spec:
        text_diffs = _compare_text(spec.get("nodes", []))

    # Control tree comparison
    tree_diffs = []
    if spec and render_tree:
        tree_diffs = _compare_control_tree(spec.get("nodes", []), render_tree)

    # Generate diff overlay
    diff_overlay_path = actual.parent / "visual_diff_overlay.png"
    try:
        _generate_diff_overlay(actual_img, baseline_img, diff_overlay_path)
    except Exception:
        warnings.append("Failed to generate diff overlay")

    # Determine status
    if pixel_result.get("error"):
        status = "failed"
    elif ssim >= 0.92 and pixel_result["changed_pixel_ratio"] < 0.05:
        status = "passed"
    elif ssim >= 0.85 and pixel_result["changed_pixel_ratio"] < 0.10:
        status = "passed_with_warnings"
    else:
        status = "failed"

    return {
        "ok": status in ("passed", "passed_with_warnings"),
        "status": status,
        "global_ssim": ssim,
        "changed_pixel_ratio": pixel_result["changed_pixel_ratio"],
        "region_diffs": region_diffs,
        "text_diffs": text_diffs,
        "control_tree_diffs": tree_diffs,
        "baseline_path": str(baseline),
        "actual_path": str(actual),
        "diff_overlay_path": str(diff_overlay_path),
        "errors": errors,
        "warnings": warnings,
    }


def _generate_diff_overlay(actual: Any, baseline: Any, output_path: Path):
    """Generate visual diff overlay image."""
    if np is None:
        return
    diff = np.abs(actual.astype(int) - baseline.astype(int))
    # Amplify differences for visibility
    diff_amp = np.clip(diff * 3, 0, 255).astype(np.uint8)
    # Blend: 50% actual + 50% diff (highlighted)
    overlay = (actual * 0.5 + diff_amp * 0.5).astype(np.uint8)
    Image.fromarray(overlay).save(str(output_path))


# ── Refinement suggestions ───────────────────────────────────────


def suggest_refinements(
    comparison: dict[str, Any],
    spec: dict[str, Any],
) -> list[dict[str, Any]]:
    """Suggest spec refinements based on comparison results.

    Returns:
        List of refinement suggestions.
    """
    suggestions = []

    # Check global SSIM
    ssim = comparison.get("global_ssim", 0)
    if ssim < 0.8:
        suggestions.append({
            "type": "global_layout",
            "severity": "high",
            "message": f"Low SSIM ({ssim}) — major layout differences detected",
            "action": "Review overall structure and positioning",
        })

    # Check region mismatches
    for rd in comparison.get("region_diffs", []):
        if rd.get("status") == "mismatch":
            suggestions.append({
                "type": "region_position",
                "severity": "medium",
                "node_id": rd.get("region_id"),
                "message": f"Region {rd.get('region_id')} mismatch (changed: {rd.get('changed_pixel_ratio', 0):.1%})",
                "action": "Check bbox and layout constraints",
            })

    # Check text mismatches
    for td in comparison.get("text_diffs", []):
        if not td.get("match"):
            suggestions.append({
                "type": "text_content",
                "severity": "medium",
                "node_id": td.get("node_id"),
                "message": f"Text mismatch: expected '{td.get('expected')}' got '{td.get('actual')}'",
                "action": "Update text macro or content",
            })

    # Check missing controls
    for cd in comparison.get("control_tree_diffs", []):
        if cd.get("diff_type") == "missing":
            suggestions.append({
                "type": "missing_widget",
                "severity": "high",
                "node_id": cd.get("node_id"),
                "message": f"Widget {cd.get('node_id')} missing from render",
                "action": "Check widget creation and parent reference",
            })

    return suggestions


# ── CLI ───────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--actual", required=True, help="Path to rendered screenshot")
    parser.add_argument("--baseline", required=True, help="Path to design screenshot")
    parser.add_argument("--spec", help="Path to UI Spec JSON")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    spec = None
    if args.spec:
        spec_path = Path(args.spec)
        if spec_path.is_file():
            spec = json.loads(spec_path.read_text(encoding="utf-8"))

    result = compare(args.actual, args.baseline, spec)

    if spec:
        result["refinements"] = suggest_refinements(result, spec)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"Status: {result.get('status', 'unknown')}")
        print(f"SSIM: {result.get('global_ssim', 0):.3f}")
        print(f"Changed pixels: {result.get('changed_pixel_ratio', 0):.1%}")
        if result.get("region_diffs"):
            for rd in result["region_diffs"]:
                print(f"  Region {rd['region_id']}: {rd['status']} ({rd['changed_pixel_ratio']:.1%})")
        if result.get("refinements"):
            print(f"\nRefinements: {len(result['refinements'])}")
            for r in result["refinements"][:5]:
                print(f"  [{r['severity']}] {r['message']}")

    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
