from __future__ import annotations

from collections import deque
from pathlib import Path
from typing import Any
import textwrap


def _fallback(width: int, height: int, pet_size: tuple[int, int]) -> dict[str, Any]:
    pet_w, pet_h = pet_size
    pet_x = (width - pet_w) // 2
    pet_y = int(height * 0.14)
    panel_w = int(width * 0.84)
    panel_h = int(height * 0.24)
    arc_size = int(min(width, height) * 0.48)
    return {
        "ok": False,
        "method": "fallback_static_ratios",
        "warnings": ["Pillow analysis unavailable; used ratio fallback."],
        "pet": {"x": pet_x, "y": pet_y, "w": pet_w, "h": pet_h, "score": None},
        "battery": {"x": width - 69, "y": 22, "w": 42, "h": 22},
        "loading_arc": {"x": (width - arc_size) // 2, "y": pet_y, "w": arc_size, "h": arc_size, "line_width": max(6, arc_size // 28), "value": 72},
        "glass_panel": {"x": (width - panel_w) // 2, "y": int(height * 0.68), "w": panel_w, "h": panel_h, "radius": 24},
        "panel_text": {"pad_x": 24, "title_y": 28, "body_y": 72, "title_font": 22, "body_font": 16},
        "components": [],
    }


def _intersects(a: dict[str, int], b: dict[str, int]) -> bool:
    return not (a["x"] + a["w"] <= b["x"] or b["x"] + b["w"] <= a["x"] or a["y"] + a["h"] <= b["y"] or b["y"] + b["h"] <= a["y"])


def _expand(rect: dict[str, int], margin: int, width: int, height: int) -> dict[str, int]:
    x0 = max(0, rect["x"] - margin)
    y0 = max(0, rect["y"] - margin)
    x1 = min(width, rect["x"] + rect["w"] + margin)
    y1 = min(height, rect["y"] + rect["h"] + margin)
    return {"x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0}


def _union(rects: list[dict[str, int]]) -> dict[str, int]:
    x0 = min(r["x"] for r in rects)
    y0 = min(r["y"] for r in rects)
    x1 = max(r["x"] + r["w"] for r in rects)
    y1 = max(r["y"] + r["h"] for r in rects)
    return {"x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0}


def _match_cutout(design: Any, background: Any, cutout: Any) -> dict[str, Any]:
    width, height = design.size
    cut_w, cut_h = cutout.size
    pixels = cutout.load()
    samples: list[tuple[int, int, int, int, int, int]] = []
    step = max(4, min(cut_w, cut_h) // 32)
    for y in range(0, cut_h, step):
        for x in range(0, cut_w, step):
            r, g, b, a = pixels[x, y]
            if a > 40:
                samples.append((x, y, r, g, b, a))
    if not samples:
        return {"x": (width - cut_w) // 2, "y": (height - cut_h) // 2, "w": cut_w, "h": cut_h, "score": None, "samples": 0}
    samples = samples[::max(1, len(samples) // 700)]
    dp = design.load()
    bp = background.load()

    def score_at(ox: int, oy: int) -> int:
        score = 0
        for x, y, r, g, b, a in samples:
            px = ox + x
            py = oy + y
            br, bg, bb, _ = bp[px, py]
            alpha = a / 255.0
            er = int(r * alpha + br * (1.0 - alpha))
            eg = int(g * alpha + bg * (1.0 - alpha))
            eb = int(b * alpha + bb * (1.0 - alpha))
            dr, dg, db, _ = dp[px, py]
            score += abs(dr - er) + abs(dg - eg) + abs(db - eb)
        return score

    max_x = max(0, width - cut_w)
    max_y = max(0, height - cut_h)
    best = (10**18, 0, 0)
    for oy in range(0, max_y + 1, 4):
        for ox in range(0, max_x + 1, 4):
            value = score_at(ox, oy)
            if value < best[0]:
                best = (value, ox, oy)
    _, bx, by = best
    for oy in range(max(0, by - 8), min(max_y, by + 8) + 1):
        for ox in range(max(0, bx - 8), min(max_x, bx + 8) + 1):
            value = score_at(ox, oy)
            if value < best[0]:
                best = (value, ox, oy)
    return {"x": best[1], "y": best[2], "w": cut_w, "h": cut_h, "score": best[0], "samples": len(samples)}


def _find_loading_reference(design_dir: Path, explicit_path: Path | None = None) -> Path | None:
    if explicit_path is not None:
        return explicit_path if explicit_path.is_file() else None
    for name in ("loadiing2.png", "loading2.png", "loading.png", "loading_circle.png", "loading_arc.png"):
        candidate = design_dir / name
        if candidate.is_file():
            return candidate
    return None


def _match_template(design: Any, template: Any) -> dict[str, Any]:
    width, height = design.size
    tmpl_w, tmpl_h = template.size
    if tmpl_w > width or tmpl_h > height:
        return {"x": 0, "y": 0, "w": tmpl_w, "h": tmpl_h, "score": None, "samples": 0}

    tp = template.load()
    samples: list[tuple[int, int, int, int, int]] = []
    fallback_samples: list[tuple[int, int, int, int, int]] = []
    step = max(1, min(tmpl_w, tmpl_h) // 36)
    for y in range(0, tmpl_h, step):
        for x in range(0, tmpl_w, step):
            r, g, b, a = tp[x, y]
            if a > 20:
                fallback_samples.append((x, y, r, g, b))
            if a > 30 and (r + g + b > 520 or a > 220):
                samples.append((x, y, r, g, b))
    if len(samples) < 64:
        samples = fallback_samples
    if not samples:
        return {"x": (width - tmpl_w) // 2, "y": (height - tmpl_h) // 2, "w": tmpl_w, "h": tmpl_h, "score": None, "samples": 0}
    samples = samples[::max(1, len(samples) // 1800)]
    dp = design.load()

    def score_at(ox: int, oy: int) -> int:
        score = 0
        for x, y, r, g, b in samples:
            dr, dg, db, _ = dp[ox + x, oy + y]
            score += abs(dr - r) + abs(dg - g) + abs(db - b)
        return score

    max_x = width - tmpl_w
    max_y = height - tmpl_h
    best = (10**18, 0, 0)
    for oy in range(0, max_y + 1, 4):
        for ox in range(0, max_x + 1, 4):
            value = score_at(ox, oy)
            if value < best[0]:
                best = (value, ox, oy)
    _, bx, by = best
    for oy in range(max(0, by - 8), min(max_y, by + 8) + 1):
        for ox in range(max(0, bx - 8), min(max_x, bx + 8) + 1):
            value = score_at(ox, oy)
            if value < best[0]:
                best = (value, ox, oy)
    return {"x": best[1], "y": best[2], "w": tmpl_w, "h": tmpl_h, "score": best[0], "samples": len(samples)}


def _components(design: Any, composed: Any) -> list[dict[str, Any]]:
    from PIL import Image, ImageChops, ImageFilter

    width, height = design.size
    diff = ImageChops.difference(design, composed).convert("RGB")
    mask = Image.new("1", (width, height), 0)
    mp = mask.load()
    dp = diff.load()
    for y in range(height):
        for x in range(width):
            r, g, b = dp[x, y]
            if max(r, g, b) >= 20 and r + g + b >= 42:
                mp[x, y] = 1
    mask = mask.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.MinFilter(3))
    mp = mask.load()
    seen = bytearray(width * height)
    out: list[dict[str, Any]] = []
    for y in range(height):
        for x in range(width):
            idx = y * width + x
            if seen[idx] or not mp[x, y]:
                continue
            q: deque[tuple[int, int]] = deque([(x, y)])
            seen[idx] = 1
            min_x = max_x = x
            min_y = max_y = y
            area = bright = sum_r = sum_g = sum_b = 0
            while q:
                cx, cy = q.popleft()
                area += 1
                min_x = min(min_x, cx)
                max_x = max(max_x, cx)
                min_y = min(min_y, cy)
                max_y = max(max_y, cy)
                rr, gg, bb, _ = design.getpixel((cx, cy))
                sum_r += rr
                sum_g += gg
                sum_b += bb
                if rr > 210 and gg > 210 and bb > 210:
                    bright += 1
                for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                    if nx < 0 or nx >= width or ny < 0 or ny >= height:
                        continue
                    nidx = ny * width + nx
                    if not seen[nidx] and mp[nx, ny]:
                        seen[nidx] = 1
                        q.append((nx, ny))
            if area >= 20:
                out.append({
                    "x": min_x,
                    "y": min_y,
                    "w": max_x - min_x + 1,
                    "h": max_y - min_y + 1,
                    "area": area,
                    "avg_rgb": [sum_r // area, sum_g // area, sum_b // area],
                    "bright_pixels": bright,
                })
    out.sort(key=lambda item: item["area"], reverse=True)
    return out


def analyze_design(design_path: Path, background_path: Path, pet_path: Path, width: int, height: int, loading_path: Path | None = None) -> dict[str, Any]:
    try:
        from PIL import Image
    except Exception as exc:
        fallback = _fallback(width, height, (271, 391))
        fallback["warnings"] = [f"Pillow import failed: {exc}"]
        return fallback

    warnings: list[str] = []
    design = Image.open(design_path).convert("RGBA")
    background = Image.open(background_path).convert("RGBA")
    pet = Image.open(pet_path).convert("RGBA")
    loading_template = None
    loading_path = _find_loading_reference(design_path.parent, loading_path)
    if loading_path is not None:
        try:
            loading_template = Image.open(loading_path).convert("RGBA")
        except Exception as exc:
            warnings.append(f"loading reference open failed: {exc}")
            loading_path = None
    width, height = design.size
    if background.size != design.size:
        background = background.resize(design.size)
    pet_rect = _match_cutout(design, background, pet)
    composed = background.copy()
    composed.alpha_composite(pet, (pet_rect["x"], pet_rect["y"]))
    comps = _components(design, composed)

    card_candidates = [c for c in comps if c["y"] > height * 0.55 and c["w"] > width * 0.45 and c["h"] > height * 0.08]
    if card_candidates:
        panel_src = max(card_candidates, key=lambda c: c["area"])
        panel = {"x": panel_src["x"], "y": panel_src["y"], "w": panel_src["w"], "h": panel_src["h"]}
    else:
        panel_w = int(width * 0.84)
        panel = {"x": (width - panel_w) // 2, "y": int(height * 0.68), "w": panel_w, "h": int(height * 0.24)}
    panel["radius"] = max(18, min(36, int(panel["h"] * 0.18)))

    battery_candidates = [c for c in comps if c["x"] > width * 0.72 and c["y"] < height * 0.10 and 16 <= c["w"] <= 80 and 8 <= c["h"] <= 42]
    battery_src = max(battery_candidates, key=lambda c: c["area"]) if battery_candidates else {"x": width - 69, "y": 22, "w": 42, "h": 22}
    battery = {"x": battery_src["x"], "y": battery_src["y"], "w": battery_src["w"], "h": battery_src["h"]}

    pet_box = {"x": pet_rect["x"], "y": pet_rect["y"], "w": pet_rect["w"], "h": pet_rect["h"]}
    context = _expand(pet_box, 36, width, height)
    excluded = [_expand(panel, 8, width, height), _expand(battery, 8, width, height)]
    arc_rects: list[dict[str, int]] = []
    for comp in comps:
        rect = {"x": comp["x"], "y": comp["y"], "w": comp["w"], "h": comp["h"]}
        if comp["area"] < 180 or comp["y"] > pet_box["y"] + int(pet_box["h"] * 0.58):
            continue
        if rect["x"] + rect["w"] < width * 0.32 or rect["x"] > width * 0.82:
            continue
        if any(_intersects(rect, skip) for skip in excluded):
            continue
        if _intersects(rect, context):
            arc_rects.append(rect)
    if arc_rects:
        merged = _union(arc_rects)
        arc_size = int(max(96, min(width - 32, max(merged["w"], merged["h"]) * 1.08)))
        arc_x = max(0, min(width - arc_size, (width - arc_size) // 2))
        arc_y = max(0, min(height - arc_size, merged["y"] - max(4, arc_size // 40)))
    else:
        arc_size = int(min(width, height) * 0.48)
        arc_x = (width - arc_size) // 2
        arc_y = pet_box["y"]
        merged = {"x": arc_x, "y": arc_y, "w": arc_size, "h": arc_size}
    residual_arc = {"x": arc_x, "y": arc_y, "w": arc_size, "h": arc_size, "line_width": max(6, arc_size // 28), "value": 72, "source_bbox": merged, "source": "residual_components"}
    arc = residual_arc
    loading_match = None
    if loading_template is not None and loading_path is not None:
        loading_match = _match_template(design, loading_template)
        loading_match["template_path"] = str(loading_path)
        if int(loading_match.get("samples") or 0) > 0:
            tmpl_w, tmpl_h = loading_template.size
            arc = {
                "x": int(loading_match["x"]),
                "y": int(loading_match["y"]),
                "w": int(tmpl_w),
                "h": int(tmpl_h),
                "line_width": max(4, min(10, int(round(min(tmpl_w, tmpl_h) / 12)))),
                "value": 72,
                "source_bbox": {"x": int(loading_match["x"]), "y": int(loading_match["y"]), "w": int(tmpl_w), "h": int(tmpl_h)},
                "source": "template_match",
                "template_path": str(loading_path),
                "score": loading_match.get("score"),
                "samples": loading_match.get("samples"),
                "residual_fallback": residual_arc,
            }
        else:
            warnings.append("loading reference template had no usable pixels; residual arc bbox kept")
    pad_x = max(20, int(panel["w"] * 0.055))
    return {
        "ok": True,
        "method": "pillow_residual_components_v2_template_calibrated" if arc.get("source") == "template_match" else "pillow_residual_components_v2",
        "warnings": warnings,
        "pet": pet_rect,
        "battery": battery,
        "loading_arc": arc,
        "loading_template": {"path": str(loading_path), "match": loading_match} if loading_path is not None else None,
        "glass_panel": panel,
        "panel_text": {"pad_x": pad_x, "title_y": max(22, int(panel["h"] * 0.15)), "body_y": max(62, int(panel["h"] * 0.42)), "title_font": 22, "body_font": 16},
        "components": comps[:40],
    }



def _bbox_list(rect: dict[str, Any]) -> list[int]:
    return [int(rect.get("x", 0)), int(rect.get("y", 0)), int(rect.get("w", 0)), int(rect.get("h", 0))]


def _compact_validation(validation: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": bool(validation.get("ok")),
        "error_count": len(validation.get("errors", [])),
        "warning_count": len(validation.get("warnings", [])),
        "checked_files": validation.get("checked_files", []),
    }


def _write_analysis_artifacts(output_dir: Path, design_path: Path, analysis: dict[str, Any]) -> dict[str, str]:
    saved: dict[str, str] = {}
    try:
        from PIL import Image, ImageDraw
    except Exception:
        return saved

    try:
        design = Image.open(design_path).convert("RGBA")
        overlay = design.copy()
        draw = ImageDraw.Draw(overlay)
        boxes = (
            ("pet", analysis.get("pet"), "#377DFF"),
            ("loading", analysis.get("loading_arc"), "#00E5FF"),
            ("battery", analysis.get("battery"), "#FFD23F"),
            ("panel", analysis.get("glass_panel"), "#42F57B"),
        )
        for label, rect, color in boxes:
            if not isinstance(rect, dict):
                continue
            x = int(rect.get("x", 0))
            y = int(rect.get("y", 0))
            w = int(rect.get("w", 0))
            h = int(rect.get("h", 0))
            if w <= 0 or h <= 0:
                continue
            draw.rectangle((x, y, x + w - 1, y + h - 1), outline=color, width=3)
            draw.text((x + 4, max(0, y - 14)), label, fill=color)
        overlay_path = output_dir / "debug_overlay.png"
        overlay.save(overlay_path)
        saved["debug_overlay"] = str(overlay_path)

        arc = analysis.get("loading_arc") or {}
        template_path = arc.get("template_path")
        if arc.get("source") == "template_match" and template_path:
            template = Image.open(template_path).convert("RGBA")
            x = int(arc["x"])
            y = int(arc["y"])
            w = int(arc["w"])
            h = int(arc["h"])
            crop = design.crop((x, y, x + w, y + h))
            gap = 16
            out = Image.new("RGBA", (w * 2 + gap, max(h, template.height)), (31, 31, 31, 255))
            out.alpha_composite(template.resize((w, h)), (0, 0))
            out.alpha_composite(crop, (w + gap, 0))
            cmp_draw = ImageDraw.Draw(out)
            cmp_draw.rectangle((0, 0, w - 1, h - 1), outline="#00E5FF", width=2)
            cmp_draw.rectangle((w + gap, 0, w + gap + w - 1, h - 1), outline="#00E5FF", width=2)
            match_path = output_dir / "debug_loading_template_match.png"
            out.save(match_path)
            saved["debug_loading_template_match"] = str(match_path)
    except Exception:
        return saved
    return saved


def generate_initial_loading_page(args: dict[str, Any]) -> dict[str, Any]:
    import lvgl_ui as base

    design_dir = base.resolve_path(args.get("design_dir", base.ROOT / "ui"))
    output_dir = base.resolve_path(args.get("output_dir", base.ROOT / "artifacts" / "lvgl_ui" / "initial_loading"))
    output_dir.mkdir(parents=True, exist_ok=True)
    version = str(args.get("lvgl_version", base.DISPLAY_CONFIG["lvgl"]["version"]))
    base.require_choice("lvgl_version", version, base.LVGL_VERSIONS)
    return_mode = str(args.get("return_mode", "full")).lower()
    if return_mode not in {"compact", "full"}:
        raise ValueError("return_mode must be 'compact' or 'full'")

    background_path = base.resolve_path(args.get("background_path", design_dir / base.INITIAL_LOADING_BACKGROUND_FILE))
    pet_path = base.resolve_path(args.get("pet_path", design_dir / base.INITIAL_LOADING_PET_FILE))
    design_path = base.resolve_path(args.get("design_path", design_dir / base.INITIAL_LOADING_DESIGN_FILE))
    raw_loading_path = args.get("loading_path", args.get("loading_reference_path"))
    loading_path = base.resolve_path(raw_loading_path) if raw_loading_path else None
    for item in (background_path, pet_path, design_path):
        if not item.is_file():
            raise ValueError(f"design asset does not exist: {item}")
    if raw_loading_path and (loading_path is None or not loading_path.is_file()):
        raise ValueError(f"loading reference asset does not exist: {loading_path}")

    width = int(args.get("width", base.DISPLAY_CONFIG["display"]["width"]))
    height = int(args.get("height", base.DISPLAY_CONFIG["display"]["height"]))
    analysis = analyze_design(design_path, background_path, pet_path, width, height, loading_path=loading_path) if bool(args.get("auto_analyze", True)) else _fallback(width, height, (271, 391))
    page_name = base.safe_symbol(str(args.get("page_name", "initial_loading")))
    width = int(args.get("width", width))
    height = int(args.get("height", height))
    pet = dict(analysis["pet"])
    battery = dict(analysis["battery"])
    arc = dict(analysis["loading_arc"])
    panel = dict(analysis["glass_panel"])
    text_layout = dict(analysis["panel_text"])

    pet_x = int(args.get("pet_x", pet["x"]))
    pet_y = int(args.get("pet_y", pet["y"]))
    pet_w = int(args.get("pet_w", pet["w"]))
    pet_h = int(args.get("pet_h", pet["h"]))
    bg_src = str(args.get("background_src", "S:/ui/background1.jpg"))
    pet_src = str(args.get("pet_src", "S:/ui/pet.png"))
    bg_src_macro = str(args.get("background_src_macro", "UI_IMG_SRC_INITIAL_LOADING_BG"))
    pet_src_macro = str(args.get("pet_src_macro", "UI_IMG_SRC_INITIAL_LOADING_PET"))
    title_text = str(args.get("title_text", "Loading"))
    body_text = str(args.get("body_text", "Please wait"))
    title_macro = str(args.get("title_text_macro", "UI_TEXT_INITIAL_LOADING_TITLE"))
    body_macro = str(args.get("body_text_macro", "UI_TEXT_INITIAL_LOADING_BODY"))
    image_create = "lv_image_create" if version == "v9" else "lv_img_create"
    image_set_src = "lv_image_set_src" if version == "v9" else "lv_img_set_src"
    delete_api = "lv_obj_delete" if version == "v9" else "lv_obj_del"
    custom_events_enabled = bool(args.get("custom_events_enabled", True))
    state_machine_enabled = bool(args.get("state_machine_enabled", True))
    states = base.state_names_from_config(args, {})
    default_event_name = f"UI_{page_name.upper()}_EVENT_SERVER_UPDATE"
    raw_event_name = args.get("server_update_event_name", "auto")
    event_name = base.c_identifier(default_event_name if str(raw_event_name).lower() == "auto" else raw_event_name, default=default_event_name)

    create_fn = f"ui_{page_name}_create"
    destroy_fn = f"ui_{page_name}_destroy"
    set_panel_fn = f"ui_{page_name}_set_panel_text"
    set_arc_fn = f"ui_{page_name}_set_loading_value"
    set_battery_fn = f"ui_{page_name}_set_battery_level"
    c_path = output_dir / f"ui_{page_name}.c"
    h_path = output_dir / f"ui_{page_name}.h"
    spec_path = output_dir / f"{page_name}_spec.json"
    analysis_report_path = output_dir / "analysis_report.json"
    preview_path = output_dir / "preview.html"
    readme_path = output_dir / "README.md"
    manifest_path = output_dir / "manifest.json"

    spec = {
        "schema": "freertos-embedded-architect.lvgl.initial-loading.v2",
        "page_name": page_name,
        "display": {"width": width, "height": height, "color_depth": base.DISPLAY_CONFIG["display"]["color_depth"]},
        "lvgl_version": version,
        "design": str(design_path),
        "analysis": analysis,
        "custom_events": {"enabled": custom_events_enabled, "server_update_event_name": event_name},
        "state_machine": {"enabled": state_machine_enabled, "states": states},
        "assets": [
            {"id": "background", "path": str(background_path), "runtime_src": bg_src, "size": [width, height]},
            {"id": "pet", "path": str(pet_path), "runtime_src": pet_src, "pos": [pet_x, pet_y], "size": [pet_w, pet_h]},
        ],
        "components": [
            {"id": "background", "type": "image", "pos": [0, 0], "size": [width, height], "source": "cut_asset"},
            {"id": "loading_arc", "type": "arc", "pos": [arc["x"], arc["y"]], "size": [arc["w"], arc["h"]], "line_width": arc["line_width"], "source": arc.get("source", "auto_residual")},
            {"id": "pet", "type": "image", "pos": [pet_x, pet_y], "size": [pet_w, pet_h], "source": "matched_cut_asset"},
            {"id": "battery", "type": "battery_indicator", "pos": [battery["x"], battery["y"]], "size": [battery["w"], battery["h"]], "source": "auto_residual"},
            {"id": "glass_text_panel", "type": "container", "pos": [panel["x"], panel["y"]], "size": [panel["w"], panel["h"]], "radius": panel["radius"], "source": "auto_residual"},
            {"id": "panel_title", "type": "label", "text_macro": title_macro, "source": "macro_placeholder"},
            {"id": "panel_body", "type": "label", "text_macro": body_macro, "source": "macro_placeholder"},
        ],
    }
    base._write_json(spec_path, spec)
    base._write_json(analysis_report_path, analysis)
    analysis_artifacts = _write_analysis_artifacts(output_dir, design_path, analysis)

    runtime_support = base.render_runtime_c_support(page_name, root_var="s_page", lvgl_version=version, event_name=event_name, custom_events_enabled=custom_events_enabled, state_machine_enabled=state_machine_enabled, states=states)
    runtime_decls = base.render_runtime_h_decls(page_name, event_name=event_name, custom_events_enabled=custom_events_enabled, state_machine_enabled=state_machine_enabled, states=states)
    create_runtime = ""
    if custom_events_enabled:
        create_runtime = f"    ui_{page_name}_custom_events_init();\n    lv_obj_add_event_cb(s_page, ui_{page_name}_server_update_cb, LV_EVENT_ALL, NULL);"
    state_runtime = f"    ui_{page_name}_set_state(UI_{page_name.upper()}_STATE_{states[0].upper()});" if state_machine_enabled else ""

    body_x = int(battery["x"] + 2)
    body_y = int(battery["y"] + max(2, battery["h"] // 5))
    body_w = int(max(22, battery["w"] - 11))
    body_h = int(max(11, battery["h"] - max(6, battery["h"] // 3)))
    cap_w = int(max(3, battery["w"] // 10))
    cap_h = int(max(6, body_h // 2))
    cap_x = int(body_x + body_w + 2)
    cap_y = int(body_y + (body_h - cap_h) // 2)
    fill_pad = 3
    fill_w = int(max(4, body_w - fill_pad * 2))
    fill_h = int(max(4, body_h - fill_pad * 2))
    panel_pad = int(text_layout["pad_x"])
    panel_content_w = int(max(20, panel["w"] - panel_pad * 2))
    arc_layout_comment = "loading arc bbox calibrated from loading reference template." if arc.get("source") == "template_match" else "loading arc position inferred from residual circular components."

    c_source = f'''
#include "ui_{page_name}.h"

#include <stdbool.h>
#include <stdlib.h>

#ifndef {bg_src_macro}
#define {bg_src_macro} {base.image_source_expr(bg_src)}
#endif

#ifndef {pet_src_macro}
#define {pet_src_macro} {base.image_source_expr(pet_src)}
#endif

#ifndef {title_macro}
#define {title_macro} {base.c_text_expr(title_text)}
#endif

#ifndef {body_macro}
#define {body_macro} {base.c_text_expr(body_text)}
#endif

#ifndef UI_INITIAL_LOADING_ARC_VALUE
#define UI_INITIAL_LOADING_ARC_VALUE {int(arc.get("value", 72))}
#endif

#ifndef UI_INITIAL_LOADING_BATTERY_LEVEL
#define UI_INITIAL_LOADING_BATTERY_LEVEL 78
#endif

#define UI_INITIAL_LOADING_WIDTH {width}
#define UI_INITIAL_LOADING_HEIGHT {height}
#define UI_INITIAL_LOADING_BATTERY_FILL_MAX_W {fill_w}
#define UI_INITIAL_LOADING_ARC_LINE_W {int(arc["line_width"])}

static lv_obj_t *s_page;
static lv_obj_t *s_loading_arc;
static lv_obj_t *s_battery_fill;
static lv_obj_t *s_glass_panel;
static lv_obj_t *s_panel_title;
static lv_obj_t *s_panel_body;
static lv_style_t s_panel_style;
static lv_style_t s_title_style;
static lv_style_t s_body_style;
static lv_style_t s_battery_body_style;
static lv_style_t s_battery_fill_style;
static lv_style_t s_battery_cap_style;

{runtime_support}

static void init_styles(void)
{{
    static bool inited = false;
    if (inited) {{
        return;
    }}
    inited = true;

    lv_style_init(&s_panel_style);
    lv_style_set_radius(&s_panel_style, {int(panel["radius"])});
    lv_style_set_bg_color(&s_panel_style, lv_color_hex(0xFFFFFF));
    lv_style_set_bg_opa(&s_panel_style, LV_OPA_30);
    lv_style_set_border_color(&s_panel_style, lv_color_hex(0xFFFFFF));
    lv_style_set_border_opa(&s_panel_style, LV_OPA_30);
    lv_style_set_border_width(&s_panel_style, 1);
    lv_style_set_pad_left(&s_panel_style, {panel_pad});
    lv_style_set_pad_right(&s_panel_style, {panel_pad});
    lv_style_set_pad_top(&s_panel_style, {int(text_layout["title_y"])});
    lv_style_set_pad_bottom(&s_panel_style, 18);

    lv_style_init(&s_title_style);
    lv_style_set_text_color(&s_title_style, lv_color_hex(0xFFFFFF));
#ifdef UI_FONT_INITIAL_LOADING_TITLE
    lv_style_set_text_font(&s_title_style, UI_FONT_INITIAL_LOADING_TITLE);
#endif

    lv_style_init(&s_body_style);
    lv_style_set_text_color(&s_body_style, lv_color_hex(0xFFFFFF));
    lv_style_set_text_opa(&s_body_style, LV_OPA_90);
    lv_style_set_text_line_space(&s_body_style, 6);
#ifdef UI_FONT_INITIAL_LOADING_BODY
    lv_style_set_text_font(&s_body_style, UI_FONT_INITIAL_LOADING_BODY);
#endif

    lv_style_init(&s_battery_body_style);
    lv_style_set_radius(&s_battery_body_style, 4);
    lv_style_set_bg_opa(&s_battery_body_style, LV_OPA_TRANSP);
    lv_style_set_border_color(&s_battery_body_style, lv_color_hex(0xFFFFFF));
    lv_style_set_border_width(&s_battery_body_style, 2);
    lv_style_set_pad_all(&s_battery_body_style, 0);

    lv_style_init(&s_battery_fill_style);
    lv_style_set_radius(&s_battery_fill_style, 2);
    lv_style_set_bg_color(&s_battery_fill_style, lv_color_hex(0xFFFFFF));
    lv_style_set_bg_opa(&s_battery_fill_style, LV_OPA_COVER);

    lv_style_init(&s_battery_cap_style);
    lv_style_set_radius(&s_battery_cap_style, 2);
    lv_style_set_bg_color(&s_battery_cap_style, lv_color_hex(0xFFFFFF));
    lv_style_set_bg_opa(&s_battery_cap_style, LV_OPA_COVER);
}}

lv_obj_t *{create_fn}(lv_obj_t *parent)
{{
    init_styles();

    s_page = lv_obj_create(parent);
    lv_obj_set_size(s_page, UI_INITIAL_LOADING_WIDTH, UI_INITIAL_LOADING_HEIGHT);
    lv_obj_clear_flag(s_page, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_set_style_border_width(s_page, 0, 0);
    lv_obj_set_style_pad_all(s_page, 0, 0);
    lv_obj_set_style_bg_color(s_page, lv_color_hex(0x79A05F), 0);

{create_runtime}

    lv_obj_t *bg = {image_create}(s_page);
    {image_set_src}(bg, {bg_src_macro});
    /* LVGL_LAYOUT_EXCEPTION: full-screen background cut asset inferred from design. */
    lv_obj_set_pos(bg, 0, 0);
    lv_obj_set_size(bg, UI_INITIAL_LOADING_WIDTH, UI_INITIAL_LOADING_HEIGHT);

    s_loading_arc = lv_arc_create(s_page);
    lv_arc_set_range(s_loading_arc, 0, 100);
    lv_arc_set_value(s_loading_arc, UI_INITIAL_LOADING_ARC_VALUE);
    lv_arc_set_rotation(s_loading_arc, 240);
    lv_obj_remove_style(s_loading_arc, NULL, LV_PART_KNOB);
    lv_obj_clear_flag(s_loading_arc, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_set_style_arc_width(s_loading_arc, UI_INITIAL_LOADING_ARC_LINE_W, LV_PART_MAIN);
    lv_obj_set_style_arc_width(s_loading_arc, UI_INITIAL_LOADING_ARC_LINE_W, LV_PART_INDICATOR);
    lv_obj_set_style_arc_color(s_loading_arc, lv_color_hex(0xFFFFFF), LV_PART_MAIN);
    lv_obj_set_style_arc_color(s_loading_arc, lv_color_hex(0xFFFFFF), LV_PART_INDICATOR);
    lv_obj_set_style_arc_opa(s_loading_arc, LV_OPA_20, LV_PART_MAIN);
    lv_obj_set_style_arc_opa(s_loading_arc, LV_OPA_90, LV_PART_INDICATOR);
    /* LVGL_LAYOUT_EXCEPTION: {arc_layout_comment} */
    lv_obj_set_pos(s_loading_arc, {int(arc["x"])}, {int(arc["y"])});
    lv_obj_set_size(s_loading_arc, {int(arc["w"])}, {int(arc["h"])});

    lv_obj_t *pet = {image_create}(s_page);
    {image_set_src}(pet, {pet_src_macro});
    /* LVGL_LAYOUT_EXCEPTION: pet cutout position matched by alpha-template analysis. */
    lv_obj_set_pos(pet, {pet_x}, {pet_y});
    lv_obj_set_size(pet, {pet_w}, {pet_h});

    lv_obj_t *battery_body = lv_obj_create(s_page);
    lv_obj_remove_style_all(battery_body);
    lv_obj_add_style(battery_body, &s_battery_body_style, 0);
    /* LVGL_LAYOUT_EXCEPTION: battery position inferred from top-right residual component. */
    lv_obj_set_pos(battery_body, {body_x}, {body_y});
    lv_obj_set_size(battery_body, {body_w}, {body_h});

    s_battery_fill = lv_obj_create(battery_body);
    lv_obj_remove_style_all(s_battery_fill);
    lv_obj_add_style(s_battery_fill, &s_battery_fill_style, 0);
    /* LVGL_LAYOUT_EXCEPTION: battery fill is anchored inside the detected battery body. */
    lv_obj_set_pos(s_battery_fill, {fill_pad}, {fill_pad});
    lv_obj_set_size(s_battery_fill, UI_INITIAL_LOADING_BATTERY_FILL_MAX_W, {fill_h});

    lv_obj_t *battery_cap = lv_obj_create(s_page);
    lv_obj_remove_style_all(battery_cap);
    lv_obj_add_style(battery_cap, &s_battery_cap_style, 0);
    /* LVGL_LAYOUT_EXCEPTION: battery cap belongs to the detected top-right battery icon. */
    lv_obj_set_pos(battery_cap, {cap_x}, {cap_y});
    lv_obj_set_size(battery_cap, {cap_w}, {cap_h});

    s_glass_panel = lv_obj_create(s_page);
    lv_obj_remove_style_all(s_glass_panel);
    lv_obj_add_style(s_glass_panel, &s_panel_style, 0);
    lv_obj_clear_flag(s_glass_panel, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_set_flex_flow(s_glass_panel, LV_FLEX_FLOW_COLUMN);
    lv_obj_set_style_pad_row(s_glass_panel, 14, 0);
    /* LVGL_LAYOUT_EXCEPTION: glass text panel bbox inferred from bottom residual region. */
    lv_obj_set_pos(s_glass_panel, {int(panel["x"])}, {int(panel["y"])});
    lv_obj_set_size(s_glass_panel, {int(panel["w"])}, {int(panel["h"])});

    s_panel_title = lv_label_create(s_glass_panel);
    lv_obj_add_style(s_panel_title, &s_title_style, 0);
    lv_obj_set_width(s_panel_title, {panel_content_w});
    lv_label_set_text(s_panel_title, {title_macro});

    s_panel_body = lv_label_create(s_glass_panel);
    lv_obj_add_style(s_panel_body, &s_body_style, 0);
    lv_obj_set_width(s_panel_body, {panel_content_w});
    lv_label_set_long_mode(s_panel_body, LV_LABEL_LONG_WRAP);
    lv_label_set_text(s_panel_body, {body_macro});

    {set_battery_fn}(UI_INITIAL_LOADING_BATTERY_LEVEL);

{state_runtime}

    return s_page;
}}

void {destroy_fn}(void)
{{
    if (s_page != NULL) {{
        {delete_api}(s_page);
        s_page = NULL;
        s_loading_arc = NULL;
        s_battery_fill = NULL;
        s_glass_panel = NULL;
        s_panel_title = NULL;
        s_panel_body = NULL;
    }}
}}

void {set_panel_fn}(const char *title, const char *body)
{{
    if (s_panel_title != NULL && title != NULL) {{
        lv_label_set_text(s_panel_title, title);
    }}
    if (s_panel_body != NULL && body != NULL) {{
        lv_label_set_text(s_panel_body, body);
    }}
}}

void {set_arc_fn}(uint8_t value)
{{
    if (value > 100U) {{
        value = 100U;
    }}
    if (s_loading_arc != NULL) {{
        lv_arc_set_value(s_loading_arc, value);
    }}
}}

void {set_battery_fn}(uint8_t percent)
{{
    if (percent > 100U) {{
        percent = 100U;
    }}
    if (s_battery_fill != NULL) {{
        int32_t fill_width = (UI_INITIAL_LOADING_BATTERY_FILL_MAX_W * percent) / 100;
        lv_obj_set_width(s_battery_fill, fill_width);
    }}
}}
'''
    c_path.write_text(base.normalize_generated_source(c_source), encoding="utf-8", newline="\n")

    h_source = f'''
#ifndef UI_{page_name.upper()}_H
#define UI_{page_name.upper()}_H

#include "lvgl.h"
#include <stdint.h>

{runtime_decls}

lv_obj_t *{create_fn}(lv_obj_t *parent);
void {destroy_fn}(void);
void {set_panel_fn}(const char *title, const char *body);
void {set_arc_fn}(uint8_t value);
void {set_battery_fn}(uint8_t percent);

#endif /* UI_{page_name.upper()}_H */
'''
    h_path.write_text(base.normalize_generated_source(h_source), encoding="utf-8", newline="\n")

    bg_rel = base.relative_asset_path(background_path, output_dir)
    pet_rel = base.relative_asset_path(pet_path, output_dir)
    design_rel = base.relative_asset_path(design_path, output_dir)
    preview = f'''
<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Initial Loading Preview</title>
<style>
body{{margin:0;min-height:100vh;display:grid;place-items:center;background:#1d2419}}.screen{{position:relative;width:{width}px;height:{height}px;overflow:hidden;background:#79a05f}}.screen img{{position:absolute;display:block;user-select:none;pointer-events:none}}.bg{{inset:0;width:100%;height:100%;object-fit:cover}}.arc{{position:absolute;left:{int(arc['x'])}px;top:{int(arc['y'])}px;width:{int(arc['w'])}px;height:{int(arc['h'])}px;border-radius:50%;border:{int(arc['line_width'])}px solid rgba(255,255,255,.22);border-top-color:rgba(255,255,255,.9);border-right-color:rgba(255,255,255,.72);box-sizing:border-box}}.pet{{left:{pet_x}px;top:{pet_y}px;width:{pet_w}px;height:{pet_h}px}}.battery{{position:absolute;left:{body_x}px;top:{body_y}px;width:{body_w}px;height:{body_h}px;border:2px solid #fff;border-radius:4px;box-sizing:border-box}}.battery:before{{content:"";position:absolute;left:{fill_pad}px;top:{fill_pad}px;width:{int(fill_w * .78)}px;height:{fill_h}px;border-radius:2px;background:#fff}}.battery:after{{content:"";position:absolute;left:{body_w + 2}px;top:{(body_h - cap_h)//2}px;width:{cap_w}px;height:{cap_h}px;border-radius:2px;background:#fff}}.panel{{position:absolute;left:{int(panel['x'])}px;top:{int(panel['y'])}px;width:{int(panel['w'])}px;height:{int(panel['h'])}px;border-radius:{int(panel['radius'])}px;background:rgba(255,255,255,.28);border:1px solid rgba(255,255,255,.28);box-sizing:border-box;padding:{int(text_layout['title_y'])}px {panel_pad}px 18px;color:#fff;font-family:system-ui,"Microsoft YaHei",sans-serif}}.panel strong{{display:block;font-size:{int(text_layout['title_font'])}px;line-height:1.2;margin-bottom:14px}}.panel span{{display:block;font-size:{int(text_layout['body_font'])}px;line-height:1.55;opacity:.9}}
</style></head><body><div class="screen" data-design="{base.html_attr(design_rel)}"><img class="bg" src="{base.html_attr(bg_rel)}" alt=""><div class="arc"></div><img class="pet" src="{base.html_attr(pet_rel)}" alt=""><div class="battery"></div><div class="panel"><strong>{base.html_attr(title_text)}</strong><span>{base.html_attr(body_text)}</span></div></div></body></html>
'''
    preview_path.write_text(textwrap.dedent(preview), encoding="utf-8", newline="\n")

    readme = f'''
# Initial Loading LVGL Page

Generated from `ui/initial_loading.png` by automatic residual analysis plus optional loading-reference calibration.

`preview.html` is an approximate browser preview. Use `analysis_report.json`, `debug_overlay.png`, and `debug_loading_template_match.png` for detection QA.

Cut assets:

- Background: `{background_path}`
- Pet: `{pet_path}`

Auto-detected LVGL components:

- Battery indicator: x={battery['x']}, y={battery['y']}, w={battery['w']}, h={battery['h']}
- Loading arc: x={arc['x']}, y={arc['y']}, w={arc['w']}, h={arc['h']}, source={arc.get('source', 'unknown')}
- Glass text panel: x={panel['x']}, y={panel['y']}, w={panel['w']}, h={panel['h']}
- Pet cutout match: x={pet_x}, y={pet_y}, w={pet_w}, h={pet_h}

Analysis artifacts:

- `analysis_report.json`: machine-readable detection tree.
- `debug_overlay.png`: detected boxes drawn over the design screenshot.
- `debug_loading_template_match.png`: loading template beside the matched design crop when a template is available.

Runtime requirements:

- JPEG decoder for `{bg_src}`.
- PNG decoder for `{pet_src}`.
- Override `{bg_src_macro}`, `{pet_src_macro}`, `{title_macro}`, and `{body_macro}` when integrating final resources/text.
- Optional font macros: `UI_FONT_INITIAL_LOADING_TITLE`, `UI_FONT_INITIAL_LOADING_BODY`.
- Network/MQTT threads should call `ui_{page_name}_post_server_update(payload)` instead of touching LVGL objects directly.
'''
    readme_path.write_text(textwrap.dedent(readme), encoding="utf-8", newline="\n")

    validation = base.validate_lvgl_layout_code({"path": str(output_dir)})
    artifact_paths = [c_path, h_path, spec_path, analysis_report_path, preview_path, readme_path]
    for artifact in ("debug_overlay", "debug_loading_template_match"):
        saved_path = analysis_artifacts.get(artifact)
        if saved_path:
            artifact_paths.append(Path(saved_path))
    artifacts = [str(item) for item in artifact_paths if item.exists()]
    all_artifacts = artifacts + [str(manifest_path)]
    summary = {
        "return_mode": return_mode,
        "page_name": page_name,
        "analysis_method": analysis.get("method"),
        "analysis_ok": bool(analysis.get("ok", False)),
        "loading_arc_source": arc.get("source", "unknown"),
        "key_bboxes": {
            "pet": [pet_x, pet_y, pet_w, pet_h],
            "battery": _bbox_list(battery),
            "loading_arc": _bbox_list(arc),
            "glass_panel": _bbox_list(panel),
        },
        "source_files": {
            "design": str(design_path),
            "background": str(background_path),
            "pet": str(pet_path),
            "loading_reference": str(loading_path) if loading_path else None,
        },
        "reports": {
            "analysis_report": str(analysis_report_path),
            "debug_overlay": analysis_artifacts.get("debug_overlay"),
            "debug_loading_template_match": analysis_artifacts.get("debug_loading_template_match"),
            "preview": str(preview_path),
            "manifest": str(manifest_path),
        },
        "warnings": list(analysis.get("warnings", []))[:5],
        "validation": _compact_validation(validation),
    }
    manifest = {
        "ok": validation["ok"],
        "page_name": page_name,
        "artifacts": artifacts,
        "validation": validation,
        "analysis_ok": analysis.get("ok", False),
        "summary": summary,
    }
    base._write_json(manifest_path, manifest)
    if return_mode == "full":
        return {**manifest, "artifacts": all_artifacts}
    return {
        "ok": validation["ok"],
        "page_name": page_name,
        "analysis_ok": analysis.get("ok", False),
        "summary": summary,
        "artifacts": all_artifacts,
        "validation": summary["validation"],
    }
