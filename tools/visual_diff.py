#!/usr/bin/env python3
"""Visual diff: compare design PNG with LVGL render PNG.

Usage:
    python tools/visual_diff.py design.png render.png
    python tools/visual_diff.py design.png render.png --output diff_result/
    python tools/visual_diff.py design.png render.png --threshold 12 --json

Outputs:
    visual_diff.json    — diff report
    diff_overlay.png    — visual overlay of differences
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import deque
from pathlib import Path

try:
    from PIL import Image
    import numpy as np
except ImportError:
    Image = None
    np = None


def compute_diff(design: np.ndarray, render: np.ndarray, channel_threshold: int = 8) -> dict:
    """Compute pixel-level diff between two images."""
    if design.shape != render.shape:
        return {
            "verdict": "fail",
            "match": False,
            "error": f"size mismatch: design={design.shape} render={render.shape}",
            "changed_ratio": 1.0,
            "bbox_mismatch_count": -1,
            "missing_regions": -1,
        }

    h, w, c = design.shape
    total_pixels = h * w

    abs_diff = np.abs(design.astype(int) - render.astype(int))
    max_delta = int(abs_diff.max())
    mean_delta = float(abs_diff.mean())

    # Per-channel stats
    channel_deltas = {}
    channel_names = ["R", "G", "B"][:c]
    for i, name in enumerate(channel_names):
        ch_diff = abs_diff[:, :, i]
        channel_deltas[name] = {
            "max": int(ch_diff.max()),
            "mean": round(float(ch_diff.mean()), 2),
            "p99": int(np.percentile(ch_diff, 99)),
        }

    # Changed pixels (any channel above threshold)
    changed_mask = np.any(abs_diff > channel_threshold, axis=2)
    changed_pixels = int(changed_mask.sum())
    changed_ratio = changed_pixels / total_pixels

    # Connected components of changed regions
    regions = find_changed_regions(changed_mask)
    bbox_mismatch_count = len(regions)

    # Verdict logic
    if changed_ratio == 0:
        verdict = "pass"
    elif changed_ratio <= 0.005 and max_delta <= 16:
        verdict = "pass"
    elif changed_ratio <= 0.01 and bbox_mismatch_count <= 2:
        verdict = "pass"
    elif changed_ratio <= 0.02:
        verdict = "warn"
    else:
        verdict = "fail"

    return {
        "verdict": verdict,
        "match": verdict == "pass",
        "changed_ratio": round(changed_ratio, 6),
        "changed_pixels": changed_pixels,
        "total_pixels": total_pixels,
        "max_channel_delta": max_delta,
        "mean_channel_delta": round(mean_delta, 2),
        "channel_deltas": channel_deltas,
        "channel_threshold": channel_threshold,
        "bbox_mismatch_count": bbox_mismatch_count,
        "missing_regions": bbox_mismatch_count,  # same as mismatch for symmetric diff
        "regions": regions,
    }


def find_changed_regions(changed_mask: np.ndarray, min_area: int = 100) -> list[dict]:
    """Find connected regions of changed pixels."""
    h, w = changed_mask.shape
    visited = np.zeros_like(changed_mask, dtype=bool)
    regions = []

    for y in range(h):
        for x in range(w):
            if changed_mask[y, x] and not visited[y, x]:
                # BFS to find connected component
                pixels = []
                queue = deque([(y, x)])
                visited[y, x] = True
                while queue:
                    cy, cx = queue.popleft()
                    pixels.append((cy, cx))
                    for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                        ny, nx = cy + dy, cx + dx
                        if 0 <= ny < h and 0 <= nx < w and changed_mask[ny, nx] and not visited[ny, nx]:
                            visited[ny, nx] = True
                            queue.append((ny, nx))

                if len(pixels) >= min_area:
                    ys = [p[0] for p in pixels]
                    xs = [p[1] for p in pixels]
                    regions.append({
                        "bbox": [int(min(xs)), int(min(ys)), int(max(xs)) - int(min(xs)) + 1, int(max(ys)) - int(min(ys)) + 1],
                        "area": len(pixels),
                        "center": [int(np.mean(xs)), int(np.mean(ys))],
                    })

    # Sort by area descending
    regions.sort(key=lambda r: r["area"], reverse=True)
    return regions[:20]  # Cap at 20 regions


def generate_overlay(design: np.ndarray, changed_mask: np.ndarray) -> np.ndarray:
    """Generate diff overlay image: design with red highlights on changed areas."""
    overlay = design.copy()
    overlay[changed_mask] = [255, 0, 0]  # Red highlight
    # Blend: 50% original + 50% red highlight
    result = design.copy().astype(float)
    result[changed_mask] = result[changed_mask] * 0.5 + np.array([255, 0, 0]) * 0.5
    return result.astype(np.uint8)


def main() -> int:
    if Image is None or np is None:
        print("[ERROR] Pillow and numpy are required: pip install Pillow numpy", file=sys.stderr)
        return 1

    parser = argparse.ArgumentParser(description="Visual diff: compare design vs render")
    parser.add_argument("design", help="Design PNG path")
    parser.add_argument("render", help="Render PNG path")
    parser.add_argument("--output", "-o", help="Output directory (default: render dir)")
    parser.add_argument("--threshold", type=int, default=8, help="Channel delta threshold (default: 8)")
    parser.add_argument("--json", action="store_true", help="JSON output to stdout")
    args = parser.parse_args()

    design_path = Path(args.design)
    render_path = Path(args.render)

    if not design_path.is_file():
        print(f"[ERROR] design not found: {design_path}", file=sys.stderr)
        return 1
    if not render_path.is_file():
        print(f"[ERROR] render not found: {render_path}", file=sys.stderr)
        return 1

    design_img = Image.open(design_path).convert("RGB")
    render_img = Image.open(render_path).convert("RGB")

    design_arr = np.array(design_img)
    render_arr = np.array(render_img)

    result = compute_diff(design_arr, render_arr, args.threshold)

    if "error" in result and "size mismatch" in result.get("error", ""):
        if args.json:
            json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
            print()
        else:
            print(f"[FAIL] {result['error']}")
        return 1

    # Generate overlay
    changed_mask = np.any(np.abs(design_arr.astype(int) - render_arr.astype(int)) > args.threshold, axis=2)
    overlay_arr = generate_overlay(design_arr, changed_mask)

    # Determine output directory
    out_dir = Path(args.output) if args.output else render_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    overlay_path = out_dir / "diff_overlay.png"
    report_path = out_dir / "visual_diff.json"

    Image.fromarray(overlay_arr).save(overlay_path)
    result["overlay_path"] = str(overlay_path)
    result["design_path"] = str(design_path)
    result["render_path"] = str(render_path)

    report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if args.json:
        json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
        print()
    else:
        v = result.get("verdict", "unknown")
        status = {"pass": "PASS", "warn": "WARN", "fail": "FAIL"}.get(v, "???")
        print(f"[{status}] verdict={v} changed_ratio={result['changed_ratio']:.6f} "
              f"max_delta={result['max_channel_delta']} "
              f"bbox_mismatch={result['bbox_mismatch_count']} "
              f"missing_regions={result['missing_regions']}")
        print(f"  threshold: changed_ratio<={0.01} max_delta<={16} bbox_mismatch<={2}")
        print(f"  overlay: {overlay_path}")
        print(f"  report:  {report_path}")
        if result["regions"]:
            print(f"  top regions:")
            for r in result["regions"][:5]:
                print(f"    bbox={r['bbox']} area={r['area']}")

    return 0 if result["match"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
