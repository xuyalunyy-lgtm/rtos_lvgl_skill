"""Font glyph collection and resource budget for LVGL pipeline.

Collects glyphs from UI Spec, generates glyph sets, detects missing glyphs,
and calculates flash/font size budgets.

Usage:
    python mcp/lvgl_fonts.py --spec path/to/ui_spec.json --json
    python mcp/lvgl_fonts.py --text "Hello World 你好" --json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent

# ── Glyph collection ──────────────────────────────────────────────


def collect_glyphs_from_text(text: str) -> set[str]:
    """Extract unique glyphs from text string."""
    return set(text)


def collect_glyphs_from_spec(spec: dict[str, Any]) -> dict[str, Any]:
    """Collect all glyphs needed by a UI Spec.

    Returns:
        {
            "total_glyphs": int,
            "unique_glyphs": str (sorted unique chars),
            "glyph_sets": { "latin": str, "digits": str, "cjk": str, "symbols": str },
            "by_node": { "node_id": {"text": str, "glyphs": str} }
        }
    """
    all_glyphs: set[str] = set()
    by_node: dict[str, dict[str, str]] = {}

    # Collect from nodes
    for node in spec.get("nodes", []):
        node_id = node.get("id", "unknown")
        text = node.get("text", "")
        if text:
            glyphs = set(text)
            all_glyphs.update(glyphs)
            by_node[node_id] = {"text": text, "glyphs": "".join(sorted(glyphs))}

    # Collect from data bindings (static text parts)
    for binding in spec.get("data_bindings", []):
        source = binding.get("source", "")
        if source and not source.startswith("$"):
            # Static text in binding source
            all_glyphs.update(set(source))

    # Categorize glyphs
    latin = sorted(c for c in all_glyphs if c.isascii() and c.isalpha())
    digits = sorted(c for c in all_glyphs if c.isdigit())
    symbols = sorted(c for c in all_glyphs if c.isascii() and not c.isalnum() and not c.isspace())
    cjk = sorted(c for c in all_glyphs if not c.isascii() and not c.isspace())
    whitespace = sorted(c for c in all_glyphs if c.isspace())

    return {
        "total_glyphs": len(all_glyphs),
        "unique_glyphs": "".join(sorted(all_glyphs)),
        "glyph_sets": {
            "latin": "".join(latin),
            "digits": "".join(digits),
            "symbols": "".join(symbols),
            "cjk": "".join(cjk),
            "whitespace": "".join(whitespace),
        },
        "by_node": by_node,
    }


# ── Font size estimation ──────────────────────────────────────────


def estimate_font_flash(
    glyph_count: int,
    size: int,
    bpp: int = 4,
    has_cjk: bool = False,
) -> dict[str, Any]:
    """Estimate flash consumption for a font.

    Rough estimation:
    - Each glyph: ~size * size * bpp / 8 bytes for bitmap
    - Plus ~16 bytes metadata per glyph
    - CJK fonts: significantly more glyphs (3000-8000 common)
    """
    bitmap_per_glyph = (size * size * bpp) // 8
    metadata_per_glyph = 16
    per_glyph = bitmap_per_glyph + metadata_per_glyph
    total = glyph_count * per_glyph

    # Add font header overhead
    header_overhead = 256
    total += header_overhead

    return {
        "glyph_count": glyph_count,
        "size": size,
        "bpp": bpp,
        "bitmap_per_glyph_bytes": bitmap_per_glyph,
        "metadata_per_glyph_bytes": metadata_per_glyph,
        "estimated_flash_bytes": total,
        "estimated_flash_kb": round(total / 1024, 1),
        "has_cjk": has_cjk,
    }


# ── Resource budget ───────────────────────────────────────────────


def calculate_resource_budget(
    spec: dict[str, Any],
    asset_manifest: dict[str, Any] | None = None,
    max_flash_bytes: int = 2 * 1024 * 1024,  # 2MB default
    max_ram_bytes: int = 512 * 1024,  # 512KB default
) -> dict[str, Any]:
    """Calculate total resource budget for a page.

    Args:
        spec: UI Spec v2.
        asset_manifest: Optional compiled asset manifest.
        max_flash_bytes: Maximum flash budget.
        max_ram_bytes: Maximum RAM budget.

    Returns:
        Budget report with totals and within_budget flag.
    """
    # Asset flash
    asset_flash = 0
    if asset_manifest:
        asset_flash = asset_manifest.get("total_flash_bytes", 0)
    else:
        # Estimate from spec assets
        for asset in spec.get("assets", []):
            asset_flash += asset.get("flash_bytes", 0)

    # Font flash
    font_flash = 0
    font_details = []
    for font in spec.get("fonts", []):
        glyph_count = font.get("glyph_count", 96)  # Default ASCII
        size = font.get("size", 16)
        bpp = font.get("bpp", 4)
        has_cjk = any(not c.isascii() for c in font.get("glyphs", ""))
        if has_cjk:
            glyph_count = max(glyph_count, 3000)  # Minimum CJK set
        est = estimate_font_flash(glyph_count, size, bpp, has_cjk)
        font_flash += est["estimated_flash_bytes"]
        font_details.append(est)

    # Code flash (rough estimate: ~100 bytes per node)
    node_count = len(spec.get("nodes", []))
    code_flash_estimate = node_count * 100

    total_flash = asset_flash + font_flash + code_flash_estimate
    total_ram = 0  # Static assets use flash only

    within_flash = total_flash <= max_flash_bytes
    within_ram = total_ram <= max_ram_bytes

    return {
        "total_flash_bytes": total_flash,
        "total_flash_kb": round(total_flash / 1024, 1),
        "total_ram_bytes": total_ram,
        "budget": {
            "max_flash_bytes": max_flash_bytes,
            "max_flash_kb": round(max_flash_bytes / 1024, 1),
            "max_ram_bytes": max_ram_bytes,
            "within_budget": within_flash and within_ram,
            "flash_usage_percent": round(total_flash / max_flash_bytes * 100, 1) if max_flash_bytes > 0 else 0,
        },
        "breakdown": {
            "assets_bytes": asset_flash,
            "fonts_bytes": font_flash,
            "code_estimate_bytes": code_flash_estimate,
        },
        "font_details": font_details,
        "warnings": [],
    }


# ── Glyph validation ──────────────────────────────────────────────


def validate_glyphs(
    spec: dict[str, Any],
    available_fonts: dict[str, set[str]] | None = None,
) -> dict[str, Any]:
    """Validate that all required glyphs are available.

    Args:
        spec: UI Spec v2.
        available_fonts: Optional dict mapping font name to available glyph set.

    Returns:
        Validation result with missing glyphs.
    """
    collected = collect_glyphs_from_spec(spec)
    all_needed = set(collected["unique_glyphs"])

    if available_fonts is None:
        # Assume all ASCII + common CJK available
        available = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 .,!?-+*/=()[]{}:;")
    else:
        available = set()
        for glyphs in available_fonts.values():
            available.update(glyphs)

    missing = all_needed - available
    # Filter out whitespace
    missing_visible = {c for c in missing if not c.isspace()}

    return {
        "total_needed": len(all_needed),
        "total_available": len(available),
        "missing_count": len(missing_visible),
        "missing_glyphs": "".join(sorted(missing_visible)),
        "coverage_percent": round((1 - len(missing_visible) / max(len(all_needed), 1)) * 100, 1),
        "ok": len(missing_visible) == 0,
    }


# ── CLI ───────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", help="Path to UI Spec JSON")
    parser.add_argument("--text", help="Text to collect glyphs from")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    if args.spec:
        spec_path = Path(args.spec)
        if not spec_path.is_file():
            print(f"ERROR: Spec not found: {args.spec}")
            return 1
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        result = collect_glyphs_from_spec(spec)
        budget = calculate_resource_budget(spec)
        validation = validate_glyphs(spec)
        output = {"glyphs": result, "budget": budget, "validation": validation}
    elif args.text:
        glyphs = collect_glyphs_from_text(args.text)
        output = {"glyphs": sorted(glyphs), "count": len(glyphs)}
    else:
        print("ERROR: --spec or --text required")
        return 1

    if args.json:
        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        if "glyphs" in output and isinstance(output["glyphs"], dict):
            g = output["glyphs"]
            print(f"Total glyphs: {g['total_glyphs']}")
            print(f"Latin: {g['glyph_sets']['latin']}")
            print(f"Digits: {g['glyph_sets']['digits']}")
            print(f"Symbols: {g['glyph_sets']['symbols']}")
            print(f"CJK: {g['glyph_sets']['cjk']}")
            b = output["budget"]
            print(f"\nBudget: {b['total_flash_kb']}KB flash ({b['budget']['flash_usage_percent']}%)")
            print(f"Within budget: {b['budget']['within_budget']}")
            v = output["validation"]
            print(f"\nGlyph coverage: {v['coverage_percent']}%")
            if v["missing_glyphs"]:
                print(f"Missing: {v['missing_glyphs']}")
        else:
            print(f"Glyphs: {output['count']}")
            print(f"Characters: {''.join(output['glyphs'])}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
