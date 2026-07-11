from __future__ import annotations

from collections import deque
from pathlib import Path
from typing import Any
import json
import shutil
import textwrap

SCENE_TOKEN = "\u4e92\u52a8\u573a\u666f"
MOOD_TOKENS = {
    "normal": "\u6b63\u5e38",
    "happy": "\u5f00\u5fc3",
    "sad": "\u5931\u843d",
    "angry": "\u6124\u6012",
    "calmness": "calmness",
    "down": "down",
    "good": "good",
    "stressed": "stressed",
}
MOOD_ORDER = ("normal", "happy", "sad", "angry")
DEFAULT_FAVORITE_MOOD_ORDER = ("calmness", "good", "down", "stressed")
BACKGROUND_GATE_DEFAULT_AVG_DELTA = 24.0


def _as_string_map(value: Any) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("mood maps must be objects")
    return {str(key): str(item) for key, item in value.items()}


def _mood_order_from_args(args: dict[str, Any]) -> tuple[str, ...]:
    raw = args.get("mood_order")
    if raw is None:
        raw = args.get("mood_keys")
    if raw is None:
        raw_paths = _as_string_map(args.get("mood_paths"))
        if any(key in raw_paths or args.get(f"{key}_path") for key in DEFAULT_FAVORITE_MOOD_ORDER):
            return DEFAULT_FAVORITE_MOOD_ORDER
        return MOOD_ORDER
    if isinstance(raw, str):
        items = [part for part in raw.replace(",", " ").split() if part]
    elif isinstance(raw, list):
        items = [str(item) for item in raw]
    else:
        raise ValueError("mood_order must be an array or comma/space separated string")
    order = tuple(item.strip().lower() for item in items if item.strip())
    if not order:
        raise ValueError("mood_order must not be empty")
    if len(set(order)) != len(order):
        raise ValueError("mood_order contains duplicate entries")
    return order


def _mood_default_src(key: str) -> str:
    return f"S:/ui/mood_{key}.png"


def _mood_default_macro(key: str) -> str:
    return f"UI_IMG_SRC_MOOD_{key.upper()}"


def _enum_constant(page_name: str, key: str) -> str:
    return f"UI_{page_name.upper()}_MOOD_{key.upper()}"


def _find_by_token(directory: Path, token: str) -> Path:
    for path in directory.glob("*.png"):
        if token in path.name:
            return path
    raise ValueError(f"required design asset not found in {directory}: token={token!r}")


def _components(image: Any, predicate: Any, *, region: tuple[int, int, int, int], min_area: int = 20) -> list[dict[str, Any]]:
    from PIL import Image, ImageFilter

    width, height = image.size
    rx, ry, rw, rh = region
    x0, y0 = max(0, rx), max(0, ry)
    x1, y1 = min(width, rx + rw), min(height, ry + rh)
    mask = Image.new("1", (width, height), 0)
    mp = mask.load()
    pix = image.load()
    for y in range(y0, y1):
        for x in range(x0, x1):
            r, g, b, a = pix[x, y]
            if predicate(r, g, b, a):
                mp[x, y] = 1
    mask = mask.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.MinFilter(3))
    mp = mask.load()
    seen = bytearray(width * height)
    out: list[dict[str, Any]] = []
    for y in range(y0, y1):
        for x in range(x0, x1):
            idx = y * width + x
            if seen[idx] or not mp[x, y]:
                continue
            q: deque[tuple[int, int]] = deque([(x, y)])
            seen[idx] = 1
            min_x = max_x = x
            min_y = max_y = y
            area = sum_r = sum_g = sum_b = 0
            while q:
                cx, cy = q.popleft()
                area += 1
                min_x = min(min_x, cx)
                max_x = max(max_x, cx)
                min_y = min(min_y, cy)
                max_y = max(max_y, cy)
                rr, gg, bb, _ = pix[cx, cy]
                sum_r += rr
                sum_g += gg
                sum_b += bb
                for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                    if nx < x0 or nx >= x1 or ny < y0 or ny >= y1:
                        continue
                    nidx = ny * width + nx
                    if not seen[nidx] and mp[nx, ny]:
                        seen[nidx] = 1
                        q.append((nx, ny))
            if area >= min_area:
                out.append({
                    "x": min_x,
                    "y": min_y,
                    "w": max_x - min_x + 1,
                    "h": max_y - min_y + 1,
                    "area": area,
                    "avg_rgb": [sum_r // area, sum_g // area, sum_b // area],
                })
    out.sort(key=lambda item: item["area"], reverse=True)
    return out


def _union(rects: list[dict[str, Any]]) -> dict[str, int]:
    x0 = min(int(r["x"]) for r in rects)
    y0 = min(int(r["y"]) for r in rects)
    x1 = max(int(r["x"] + r["w"]) for r in rects)
    y1 = max(int(r["y"] + r["h"]) for r in rects)
    return {"x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0}


def _rect_contains(rect: dict[str, Any], x: int, y: int, *, margin: int = 0) -> bool:
    return (
        int(rect.get("x", 0)) - margin <= x < int(rect.get("x", 0)) + int(rect.get("w", 0)) + margin
        and int(rect.get("y", 0)) - margin <= y < int(rect.get("y", 0)) + int(rect.get("h", 0)) + margin
    )


def _background_delta(design: Any, background: Any, exclude_rects: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    dp = design.convert("RGB").load()
    bp = background.convert("RGB").load()
    width, height = design.size
    step = max(1, min(width, height) // 80)
    total = 0
    count = 0
    skipped = 0
    max_delta = 0
    exclude_rects = exclude_rects or []
    for y in range(0, height, step):
        for x in range(0, width, step):
            if any(_rect_contains(rect, x, y, margin=8) for rect in exclude_rects):
                skipped += 1
                continue
            dr, dg, db = dp[x, y]
            br, bg, bb = bp[x, y]
            delta = (abs(dr - br) + abs(dg - bg) + abs(db - bb)) / 3.0
            total += delta
            count += 1
            max_delta = max(max_delta, int(delta))
    avg = total / count if count else 0.0
    return {"sample_step": step, "sample_count": count, "skipped_foreground_samples": skipped, "avg_abs_delta": round(avg, 2), "max_abs_delta": max_delta}


def _background_consistency_gate(delta: dict[str, Any], threshold: float) -> dict[str, Any]:
    avg = float(delta.get("avg_abs_delta", 0.0))
    blocked = avg > threshold
    reason = ""
    if blocked:
        reason = (
            f"background asset does not match design background "
            f"(avg_abs_delta={avg}, threshold={threshold}); layered pixel reconstruction is blocked"
        )
    return {
        "name": "background_consistency_gate",
        "threshold_avg_abs_delta": threshold,
        "avg_abs_delta": avg,
        "max_abs_delta": int(delta.get("max_abs_delta", 0)),
        "sample_count": int(delta.get("sample_count", 0)),
        "skipped_foreground_samples": int(delta.get("skipped_foreground_samples", 0)),
        "verdict": "blocked" if blocked else "pass",
        "layered_pixel_reconstruction_blocked": blocked,
        "auto_preview_mode": "design_reference" if blocked else "layered_reconstruction",
        "reason": reason,
        "required_fix": "provide a clean background matching the design screenshot" if blocked else "",
    }


def _match_pet(design: Any, background: Any, cutout: Any) -> dict[str, Any]:
    width, height = design.size
    cut_w, cut_h = cutout.size
    cp = cutout.load()
    dp = design.load()
    bp = background.load()
    samples: list[tuple[int, int, int, int, int, int]] = []
    step = max(4, min(cut_w, cut_h) // 32)
    for y in range(0, cut_h, step):
        for x in range(0, cut_w, step):
            r, g, b, a = cp[x, y]
            if a > 40:
                samples.append((x, y, r, g, b, a))
    if not samples:
        return {"x": (width - cut_w) // 2, "y": int(height * 0.14), "w": cut_w, "h": cut_h, "score": None, "samples": 0}
    samples = samples[::max(1, len(samples) // 700)]

    def score_at(ox: int, oy: int) -> int:
        score = 0
        for x, y, r, g, b, a in samples:
            br, bg, bb, _ = bp[ox + x, oy + y]
            alpha = a / 255.0
            er = int(r * alpha + br * (1.0 - alpha))
            eg = int(g * alpha + bg * (1.0 - alpha))
            eb = int(b * alpha + bb * (1.0 - alpha))
            dr, dg, db, _ = dp[ox + x, oy + y]
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


def _fallback(width: int, height: int, mood_sizes: dict[str, tuple[int, int]], mood_order: tuple[str, ...] = MOOD_ORDER) -> dict[str, Any]:
    moods: list[dict[str, Any]] = []
    count = max(1, len(mood_order))
    button_size = 70
    gap = 24 if count > 1 else 0
    total_w = count * button_size + (count - 1) * gap
    start_x = max(0, (width - total_w) // 2)
    for idx, mood in enumerate(mood_order):
        button = {"x": start_x + idx * (button_size + gap), "y": 636, "w": button_size, "h": button_size, "radius": button_size // 2, "source": "fallback_static"}
        icon_w, icon_h = mood_sizes[mood]
        icon = {"x": button["x"] + (button["w"] - icon_w) // 2, "y": button["y"] + (button["h"] - icon_h) // 2, "w": icon_w, "h": icon_h, "source": "button_center_fallback"}
        moods.append({
            "id": mood,
            "button": button,
            "icon": icon,
            "asset_path": f"{mood}.png",
        })
    return {
        "ok": False,
        "method": "fallback_static_interactive_scene",
        "warnings": ["Pillow analysis unavailable; used fixed 480x800 layout."],
        "pet": {"x": 118, "y": 112, "w": 271, "h": 391, "score": None},
        "glass_panel": {"x": 40, "y": 534, "w": 400, "h": 180, "radius": 28, "source": "fallback_static"},
        "text": {
            "top_prompt": {"x": 86, "y": 136, "w": 310, "h": 150, "font": 34, "source": "fallback_static"},
            "title": {"x": 94, "y": 537, "w": 294, "h": 38, "font": 18, "source": "fallback_static"},
            "hint": {"x": 184, "y": 583, "w": 112, "h": 36, "font": 16, "source": "fallback_static"},
        },
        "status_bar": {
            "favorite": {"x": 259, "y": 30, "w": 27, "h": 4, "source": "fallback_static"},
            "wifi": {"x": 297, "y": 20, "w": 31, "h": 23, "source": "fallback_static"},
            "bluetooth": {"x": 363, "y": 18, "w": 21, "h": 29, "source": "fallback_static"},
            "battery": {"x": 413, "y": 23, "w": 36, "h": 18, "source": "fallback_static"},
        },
        "moods": moods,
        "components": {},
    }


def _image_size(path: Path) -> tuple[int, int]:
    try:
        from PIL import Image
    except Exception as exc:
        raise ValueError(f"cannot open image asset with Pillow: {path} ({exc})") from exc
    with Image.open(path) as image:
        return image.size


def _find_status_cutouts(design_dir: Path) -> dict[str, Path | None]:
    status_candidates = {
        "favorite": ("favorite", "star", "fav", "bookmark"),
        "wifi": ("wifi", "network", "signal"),
        "bluetooth": ("bluetooth", "blue"),
        "battery": ("battery", "power"),
    }
    found: dict[str, Path | None] = {key: None for key in status_candidates}
    try:
        files = sorted(design_dir.glob("*.*"))
    except Exception:
        return found
    for candidate, keys in status_candidates.items():
        for item in files:
            name = item.name.lower()
            suffix = item.suffix.lower()
            if suffix not in {".png", ".jpg", ".jpeg", ".bmp"}:
                continue
            if any(key in name for key in keys):
                found[candidate] = item
                break
    return found


def _evaluate_cutout_quality(path: Path, label: str) -> tuple[str, str | None]:
    try:
        width, height = _image_size(path)
    except Exception as exc:
        return "fail", f"{label} is not a valid image: {exc}"
    if width <= 1 or height <= 1:
        return "fail", f"{label} size is too small ({width}x{height})"
    if width < 20 or height < 20:
        return "warn", f"{label} is very small ({width}x{height})"
    return "pass", None


def _preflight_interactive_scene(
    design_path: Path,
    background_path: Path,
    pet_path: Path,
    mood_paths: dict[str, Path],
    mood_order: tuple[str, ...],
    design_dir: Path,
    background_gate_threshold: float,
) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    warnings: list[str] = []
    status_messages: dict[str, str] = {}
    bg_gate: dict[str, Any] = {}

    required = [design_path, background_path, pet_path, *mood_paths.values()]
    for path in required:
        if not path.is_file():
            issues.append({"level": "error", "check": "file_exists", "path": str(path), "message": "required asset missing"})

    try:
        design_size = _image_size(design_path)
        background_size = _image_size(background_path)
        pet_size = _image_size(pet_path)
        if design_size != background_size:
            issues.append({
                "level": "error",
                "check": "size_check",
                "message": f"design and background size mismatch: design={design_size}, background={background_size}",
            })
        if design_size != pet_size:
            warnings.append(f"pet cutout size {pet_size} differs from design size {design_size}")
        status_messages["size_check"] = f"{design_size[0]}x{design_size[1]}"
    except Exception as exc:
        issues.append({"level": "error", "check": "size_check", "message": f"size check failed: {exc}"})

    if not issues:
        try:
            from PIL import Image
            with Image.open(design_path) as design_img:
                with Image.open(background_path) as background_img:
                    bg_gate = _background_consistency_gate(_background_delta(design_img, background_img), float(background_gate_threshold))
        except Exception as exc:
            issues.append({"level": "error", "check": "background_gate", "message": f"background gate check failed: {exc}"})

    cutout_statuses: list[str] = []
    for mood in mood_order:
        status, message = _evaluate_cutout_quality(mood_paths[mood], f"mood cutout '{mood}'")
        cutout_statuses.append(status)
        if status == "fail":
            issues.append({"level": "error", "check": "mood_cutout", "path": str(mood_paths[mood]), "message": message or "invalid mood cutout"})
        elif message:
            warnings.append(message)

    if any(status == "fail" for status in cutout_statuses):
        cutout_completeness = "fail"
    elif any(status == "warn" for status in cutout_statuses):
        cutout_completeness = "warn"
    else:
        cutout_completeness = "pass"

    status_cutouts = _find_status_cutouts(design_dir)
    missing_status = [name for name, value in status_cutouts.items() if value is None]
    if missing_status:
        warnings.append(f"missing status/favorite cutouts: {', '.join(missing_status)}")

    status_messages["cutout_completeness"] = cutout_completeness
    status_messages["mood_order"] = ",".join(mood_order)
    status_messages["background_consistency"] = str(bg_gate.get("verdict", "pass"))
    status_messages["status_bar_cutout_presence"] = "warn" if missing_status else "pass"

    return {
        "errors": issues,
        "warnings": warnings,
        "quality": {
            "background_consistency": status_messages["background_consistency"],
            "cutout_completeness": cutout_completeness,
            "status_bar_cutout_presence": status_messages["status_bar_cutout_presence"],
            "passed": not issues,
        },
        "gate": bg_gate,
        "status_messages": status_messages,
        "status_cutouts": {name: (str(path) if path is not None else None) for name, path in status_cutouts.items()},
    }


def analyze_interactive_scene(
    design_path: Path,
    background_path: Path,
    pet_path: Path,
    mood_paths: dict[str, Path],
    width: int,
    height: int,
    mood_order: tuple[str, ...] = MOOD_ORDER,
    background_gate_threshold: float = BACKGROUND_GATE_DEFAULT_AVG_DELTA,
) -> dict[str, Any]:
    try:
        from PIL import Image
    except Exception as exc:
        fallback = _fallback(width, height, {key: (37, 37) for key in mood_order}, mood_order)
        fallback["warnings"] = [f"Pillow import failed: {exc}"]
        return fallback

    design = Image.open(design_path).convert("RGBA")
    background = Image.open(background_path).convert("RGBA")
    pet = Image.open(pet_path).convert("RGBA")
    if background.size != design.size:
        background = background.resize(design.size)
    width, height = design.size
    mood_images = {key: Image.open(path).convert("RGBA") for key, path in mood_paths.items()}
    warnings: list[str] = []

    pet_rect = _match_pet(design, background, pet)
    bright = _components(design, lambda r, g, b, a: a > 20 and r + g + b > 600, region=(30, int(height * 0.60), width - 60, int(height * 0.35)), min_area=40)
    mood_count = len(mood_order)
    button_candidates = [c for c in bright if 52 <= c["w"] <= 88 and 52 <= c["h"] <= 88 and c["area"] >= 2200 and c["y"] > height * 0.70]
    button_candidates = sorted(button_candidates, key=lambda c: c["x"])[:mood_count]
    if len(button_candidates) != mood_count:
        button_size = 70
        gap = 24 if mood_count > 1 else 0
        total_w = mood_count * button_size + (mood_count - 1) * gap
        start_x = max(0, (width - total_w) // 2)
        button_candidates = [{"x": start_x + idx * (button_size + gap), "y": 636, "w": button_size, "h": button_size, "area": 0, "avg_rgb": [255, 255, 255], "source": "fallback_static"} for idx in range(mood_count)]

    edge_candidates = [c for c in bright if c["w"] <= 3 and c["h"] >= 100]
    if len(edge_candidates) >= 2:
        left_edge = min(edge_candidates, key=lambda c: c["x"])
        right_edge = max(edge_candidates, key=lambda c: c["x"])
        panel_bottom = max(max(c["y"] + c["h"] for c in edge_candidates), max(c["y"] + c["h"] for c in button_candidates))
        panel = {"x": int(left_edge["x"]), "y": int(min(left_edge["y"], right_edge["y"])), "w": int(right_edge["x"] + right_edge["w"] - left_edge["x"]), "h": int(panel_bottom - min(left_edge["y"], right_edge["y"]) + 8), "radius": 28, "source": "bright_edge_detection"}
    else:
        bx0 = min(c["x"] for c in button_candidates)
        by0 = min(c["y"] for c in button_candidates)
        bx1 = max(c["x"] + c["w"] for c in button_candidates)
        by1 = max(c["y"] + c["h"] for c in button_candidates)
        panel = {"x": int(max(0, bx0 - 24)), "y": int(max(0, by0 - 102)), "w": int(min(width, bx1 + 24) - max(0, bx0 - 24)), "h": int(min(height, by1 + 8) - max(0, by0 - 102)), "radius": 28, "source": "button_bounds_fallback"}

    button_y = min(c["y"] for c in button_candidates)
    text_region_h = max(1, button_y - panel["y"] - 8)
    text_bright = _components(
        design,
        lambda r, g, b, a: a > 20 and r > 220 and g > 220 and b > 220,
        region=(panel["x"], panel["y"], panel["w"], text_region_h),
        min_area=20,
    )
    text_candidates = [c for c in text_bright if c["area"] >= 20 and c["w"] > 2 and c["h"] > 2]
    upper = [c for c in text_candidates if c["y"] < panel["y"] + 56]
    lower = [c for c in text_candidates if c["y"] >= panel["y"] + 56]
    title_fallback = {"x": panel["x"] + 48, "y": panel["y"] + 2, "w": panel["w"] - 96, "h": 54}
    hint_fallback = {"x": panel["x"] + 120, "y": panel["y"] + 52, "w": panel["w"] - 240, "h": 44}
    title = _union(upper) if upper else title_fallback
    hint = _union(lower) if lower else hint_fallback
    if title["y"] < panel["y"] or title["h"] > 70 or title["w"] > panel["w"]:
        title = title_fallback
        upper = []
    if hint["y"] < panel["y"] or hint["y"] > panel["y"] + 56 or hint["h"] > 60 or hint["w"] > panel["w"]:
        hint = hint_fallback
        lower = []
    title = {"x": int(title["x"]), "y": int(title["y"]), "w": int(max(80, title["w"])), "h": int(max(24, title["h"])), "font": 34, "source": "panel_white_text_union" if upper else "fallback_static"}
    hint = {"x": int(hint["x"]), "y": int(hint["y"]), "w": int(max(80, hint["w"])), "h": int(max(24, hint["h"])), "font": 30, "source": "panel_white_text_union" if lower else "fallback_static"}

    top_bright = _components(
        design,
        lambda r, g, b, a: a > 20 and r > 220 and g > 220 and b > 220,
        region=(40, 96, width - 80, max(80, int(height * 0.30))),
        min_area=35,
    )
    top_text_candidates = [c for c in top_bright if c["area"] >= 40 and c["h"] >= 4 and c["w"] >= 3]
    top_prompt = _union(top_text_candidates) if top_text_candidates else {"x": 86, "y": 136, "w": 310, "h": 150}
    top_prompt = {
        "x": int(top_prompt["x"]),
        "y": int(top_prompt["y"]),
        "w": int(max(160, top_prompt["w"])),
        "h": int(max(64, top_prompt["h"])),
        "font": 34,
        "source": "top_bright_text_union" if top_text_candidates else "fallback_static",
    }

    moods: list[dict[str, Any]] = []
    for idx, mood in enumerate(mood_order):
        src_button = button_candidates[idx]
        image = mood_images[mood]
        icon_w, icon_h = image.size
        button = {"x": int(src_button["x"]), "y": int(src_button["y"]), "w": int(src_button["w"]), "h": int(src_button["h"]), "radius": int(min(src_button["w"], src_button["h"]) // 2), "source": src_button.get("source", "bright_circle_detection")}
        icon = {"x": int(button["x"] + (button["w"] - icon_w) // 2), "y": int(button["y"] + (button["h"] - icon_h) // 2), "w": int(icon_w), "h": int(icon_h), "source": "button_center_from_detected_container"}
        moods.append({"id": mood, "button": button, "icon": icon, "asset_path": str(mood_paths[mood])})

    status_bar = {
        "favorite": {"x": 259, "y": 30, "w": 27, "h": 4, "source": "dynamic_component_fallback"},
        "wifi": {"x": 297, "y": 20, "w": 31, "h": 23, "source": "dynamic_component_fallback"},
        "bluetooth": {"x": 363, "y": 18, "w": 21, "h": 29, "source": "dynamic_component_fallback"},
        "battery": {"x": 413, "y": 23, "w": 36, "h": 18, "source": "dynamic_component_fallback"},
    }
    foreground_exclusions = [
        pet_rect,
        panel,
        top_prompt,
        title,
        hint,
        *status_bar.values(),
        *[mood["button"] for mood in moods],
    ]
    bg_delta = _background_delta(design, background, foreground_exclusions)
    bg_gate = _background_consistency_gate(bg_delta, float(background_gate_threshold))
    if bg_gate["layered_pixel_reconstruction_blocked"]:
        warnings.append(bg_gate["reason"])

    return {
        "ok": True,
        "method": "pillow_interactive_scene_v1",
        "warnings": warnings,
        "background_delta": bg_delta,
        "background_consistency_gate": bg_gate,
        "pet": pet_rect,
        "glass_panel": panel,
        "text": {"top_prompt": top_prompt, "title": title, "hint": hint},
        "status_bar": status_bar,
        "moods": moods,
        "components": {"bright_bottom": bright[:80], "text_candidates": text_candidates[:40], "top_text_candidates": top_text_candidates[:40]},
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
            ("panel", analysis.get("glass_panel"), "#42F57B"),
            ("pet", analysis.get("pet"), "#377DFF"),
            ("top", (analysis.get("text") or {}).get("top_prompt"), "#B967FF"),
            ("title", (analysis.get("text") or {}).get("title"), "#FFFFFF"),
            ("hint", (analysis.get("text") or {}).get("hint"), "#FFD23F"),
            ("favorite", (analysis.get("status_bar") or {}).get("favorite"), "#FF7AC8"),
            ("wifi", (analysis.get("status_bar") or {}).get("wifi"), "#7AE7FF"),
            ("bluetooth", (analysis.get("status_bar") or {}).get("bluetooth"), "#7AE7FF"),
            ("battery", (analysis.get("status_bar") or {}).get("battery"), "#7AE7FF"),
        )
        for label, rect, color in boxes:
            if not isinstance(rect, dict) or int(rect.get("w", 0)) <= 0 or int(rect.get("h", 0)) <= 0:
                continue
            x, y, w, h = int(rect["x"]), int(rect["y"]), int(rect["w"]), int(rect["h"])
            draw.rectangle((x, y, x + w - 1, y + h - 1), outline=color, width=3)
            draw.text((x + 3, max(0, y - 13)), label, fill=color)
        colors = ("#00E5FF", "#42F57B", "#FFD23F", "#FF4D4D", "#B967FF", "#FF7AC8")
        for idx, mood in enumerate(analysis.get("moods", [])):
            color = colors[idx % len(colors)]
            for rect in (mood.get("button"), mood.get("icon")):
                if not isinstance(rect, dict):
                    continue
                x, y, w, h = int(rect["x"]), int(rect["y"]), int(rect["w"]), int(rect["h"])
                draw.rectangle((x, y, x + w - 1, y + h - 1), outline=color, width=2)
        overlay_path = output_dir / "debug_overlay.png"
        overlay.save(overlay_path)
        saved["debug_overlay"] = str(overlay_path)
    except Exception:
        return saved
    return saved


def _crop_rect(rect: dict[str, Any], width: int, height: int, *, margin: int = 0) -> tuple[int, int, int, int]:
    x0 = max(0, int(rect.get("x", 0)) - margin)
    y0 = max(0, int(rect.get("y", 0)) - margin)
    x1 = min(width, int(rect.get("x", 0)) + int(rect.get("w", 0)) + margin)
    y1 = min(height, int(rect.get("y", 0)) + int(rect.get("h", 0)) + margin)
    return x0, y0, x1, y1


def _write_preview_crops(output_dir: Path, design_path: Path, analysis: dict[str, Any]) -> dict[str, Any]:
    try:
        from PIL import Image
    except Exception:
        return {}
    try:
        design = Image.open(design_path).convert("RGBA")
        width, height = design.size
        crops_dir = output_dir / "assets"
        crops_dir.mkdir(parents=True, exist_ok=True)
        saved: dict[str, Any] = {}

        text = analysis.get("text") or {}
        top_prompt = text.get("top_prompt")
        if isinstance(top_prompt, dict):
            x0, y0, x1, y1 = _crop_rect(top_prompt, width, height, margin=6)
            path = crops_dir / "derived_top_prompt.png"
            design.crop((x0, y0, x1, y1)).save(path)
            saved["top_prompt"] = {"path": str(path), "x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0}

        panel = analysis.get("glass_panel")
        if isinstance(panel, dict):
            x0, y0, x1, y1 = _crop_rect(panel, width, height)
            path = crops_dir / "derived_interaction_panel.png"
            design.crop((x0, y0, x1, y1)).save(path)
            saved["interaction_panel"] = {"path": str(path), "x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0}

        status_rects = [
            rect for rect in (analysis.get("status_bar") or {}).values()
            if isinstance(rect, dict) and int(rect.get("w", 0)) > 0 and int(rect.get("h", 0)) > 0
        ]
        if status_rects:
            status = _union(status_rects)
            x0, y0, x1, y1 = _crop_rect(status, width, height, margin=5)
            path = crops_dir / "derived_status_bar.png"
            design.crop((x0, y0, x1, y1)).save(path)
            saved["status_bar"] = {"path": str(path), "x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0}
        return saved
    except Exception:
        return {}


def _write_layered_preview(
    output_dir: Path,
    background_path: Path,
    pet_path: Path,
    analysis: dict[str, Any],
    moods: list[dict[str, Any]],
    mood_order: tuple[str, ...],
    asset_aliases: dict[str, str],
    width: int,
    height: int,
) -> str | None:
    try:
        from PIL import Image, ImageOps
    except Exception:
        return None
    try:
        with Image.open(background_path).convert("RGBA") as bg:
            canvas = Image.new("RGBA", (width, height), (121, 160, 95, 255))
            resized = bg.resize((width, height))
            resized = ImageOps.contain(resized, (width, height))
            x = max(0, (width - resized.size[0]) // 2)
            y = max(0, (height - resized.size[1]) // 2)
            canvas.alpha_composite(resized, (x, y))

        def _rect(value: dict[str, Any] | None) -> tuple[int, int, int, int]:
            if not value:
                return (0, 0, 0, 0)
            return (
                max(0, int(value.get("x", 0))),
                max(0, int(value.get("y", 0))),
                max(0, int(value.get("w", 0))),
                max(0, int(value.get("h", 0))),
            )

        preview_crops = _write_preview_crops(output_dir, background_path, analysis)
        for crop_name in ("top_prompt", "interaction_panel", "status_bar"):
            crop = preview_crops.get(crop_name)
            if not isinstance(crop, dict) or not crop.get("path"):
                continue
            rect = _rect({"x": int(crop.get("x", 0)), "y": int(crop.get("y", 0)), "w": int(crop.get("w", 0)), "h": int(crop.get("h", 0))})
            if rect[2] <= 0 or rect[3] <= 0:
                continue
            try:
                with Image.open(crop["path"]).convert("RGBA") as image:
                    layer = image.resize((rect[2], rect[3]))
                    canvas.alpha_composite(layer, (rect[0], rect[1]))
            except Exception:
                continue

        for mood in moods:
            if mood.get("id") not in mood_order:
                continue
            rect = _rect(mood.get("icon"))
            source = mood.get("id")
            if rect[2] <= 0 or rect[3] <= 0:
                continue
            try:
                cutout_path = asset_aliases.get(source)
                if not cutout_path:
                    continue
                with Image.open(cutout_path).convert("RGBA") as image:
                    canvas.alpha_composite(image.resize((rect[2], rect[3])), (rect[0], rect[1]))
            except Exception:
                continue

        pet = analysis.get("pet")
        pet_rect = _rect(pet)
        if pet_rect[2] > 0 and pet_rect[3] > 0:
            try:
                with Image.open(pet_path).convert("RGBA") as image:
                    canvas.alpha_composite(image.resize((pet_rect[2], pet_rect[3])), (pet_rect[0], pet_rect[1]))
            except Exception:
                pass

        path = output_dir / "layered_preview.png"
        canvas.convert("RGB").save(path)
        return str(path)
    except Exception:
        return None


def _copy_asset(src: Path, dst: Path) -> str:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.resolve() != dst.resolve():
        shutil.copyfile(src, dst)
    return str(dst)


def _build_quality_gates(
    preflight_quality: dict[str, Any],
    background_gate: dict[str, Any],
    analysis: dict[str, Any],
    validation: dict[str, Any],
    *,
    render_available: bool = False,
    render_verdict: str = "missing",
) -> dict[str, str]:
    cutout_completeness = str(preflight_quality.get("cutout_completeness", "unknown")).lower()
    if cutout_completeness not in {"pass", "warn", "fail"}:
        cutout_completeness = "warn"

    bg_verdict = str(background_gate.get("verdict", "unknown"))
    if bg_verdict == "pass":
        background_consistency = "pass"
    elif bg_verdict == "blocked":
        background_consistency = "blocked"
    else:
        background_consistency = "warn"

    bbox_confidence = "pass" if analysis.get("ok", False) and not analysis.get("warnings") else "warn"
    lvgl_validation = "pass" if bool(validation.get("ok")) else "fail"

    render_status = str(render_verdict).lower()
    if not render_available:
        render_state = "missing"
    elif render_status in {"", "pass", "passed"}:
        render_state = "pass"
    elif render_status in {"warn", "warning"}:
        render_state = "warn"
    elif render_status in {"fail", "failed"}:
        render_state = "failed"
    else:
        render_state = "pass"

    return {
        "background_consistency": background_consistency,
        "cutout_completeness": cutout_completeness,
        "bbox_confidence": bbox_confidence,
        "lvgl_validation": lvgl_validation,
        "render_available": render_state,
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


def generate_interactive_scene_page(args: dict[str, Any]) -> dict[str, Any]:
    try:
        from mcp import codegen as base
    except ImportError:  # Direct script execution compatibility.
        import codegen as base

    design_dir = base.resolve_path(args.get("design_dir", base.ROOT / "ui"))
    output_dir = base.resolve_path(args.get("output_dir", base.ROOT / "artifacts" / "lvgl_ui" / "interactive_scene"))
    output_dir.mkdir(parents=True, exist_ok=True)
    assets_dir = output_dir / "assets"
    version = str(args.get("lvgl_version", base.DISPLAY_CONFIG["lvgl"]["version"]))
    base.require_choice("lvgl_version", version, base.LVGL_VERSIONS)
    return_mode = str(args.get("return_mode", "full")).lower()
    if return_mode not in {"compact", "full"}:
        raise ValueError("return_mode must be 'compact' or 'full'")
    preview_design_reference_requested = bool(args.get("preview_design_reference", False))
    skip_preflight = bool(args.get("skip_preflight", False))
    background_gate_threshold = float(args.get("background_gate_threshold", BACKGROUND_GATE_DEFAULT_AVG_DELTA))
    allow_layered_reconstruction = bool(args.get("allow_layered_reconstruction", True))

    mood_order = _mood_order_from_args(args)
    mood_path_args = _as_string_map(args.get("mood_paths"))
    mood_src_args = _as_string_map(args.get("mood_src"))
    mood_src_macro_args = _as_string_map(args.get("mood_src_macros"))

    raw_design_path = args.get("design_path")
    design_path = base.resolve_path(raw_design_path) if raw_design_path else base.resolve_path(_find_by_token(design_dir, SCENE_TOKEN))
    background_path = base.resolve_path(args.get("background_path", design_dir / base.INITIAL_LOADING_BACKGROUND_FILE))
    pet_path = base.resolve_path(args.get("pet_path", design_dir / base.INITIAL_LOADING_PET_FILE))
    mood_paths = {}
    for key in mood_order:
        raw_mood_path = args.get(f"{key}_path") or mood_path_args.get(key)
        token = str(args.get(f"{key}_token") or MOOD_TOKENS.get(key, key))
        mood_paths[key] = base.resolve_path(raw_mood_path) if raw_mood_path else base.resolve_path(_find_by_token(design_dir, token))
    for item in (design_path, background_path, pet_path, *mood_paths.values()):
        if not item.is_file():
            raise ValueError(f"design asset does not exist: {item}")

    width = int(args.get("width", base.DISPLAY_CONFIG["display"]["width"]))
    height = int(args.get("height", base.DISPLAY_CONFIG["display"]["height"]))
    preflight = _preflight_interactive_scene(
        design_path=design_path,
        background_path=background_path,
        pet_path=pet_path,
        mood_paths=mood_paths,
        mood_order=mood_order,
        design_dir=design_dir,
        background_gate_threshold=background_gate_threshold,
    ) if not skip_preflight else {"errors": [], "warnings": [], "quality": {"background_consistency": "pass", "cutout_completeness": "pass", "passed": True}, "gate": {"verdict": "pass", "layered_pixel_reconstruction_blocked": False}}
    preflight_errors = preflight.get("errors") or []
    if preflight_errors and not bool(args.get("allow_preflight_warnings", False)):
        raise ValueError("; ".join(item.get("message", "preflight check failed") for item in preflight_errors))

    bg_gate = preflight.get("gate", {})
    if not isinstance(bg_gate, dict):
        bg_gate = {}
    bg_blocked = bool(bg_gate.get("layered_pixel_reconstruction_blocked", False))
    preview_design_reference = preview_design_reference_requested or bg_blocked
    should_run_layered = allow_layered_reconstruction and not bg_blocked
    auto_analyze = bool(args.get("auto_analyze", True))
    if auto_analyze and should_run_layered:
        analysis = analyze_interactive_scene(design_path, background_path, pet_path, mood_paths, width, height, mood_order, background_gate_threshold)
    else:
        fallback_sizes = {key: (37, 37) for key in mood_order}
        analysis = _fallback(width, height, fallback_sizes, mood_order)
        if auto_analyze and not should_run_layered:
            analysis["warnings"] = analysis.get("warnings", []) + ["layered pixel reconstruction skipped due to background consistency gate"]
    preview_decision = {
        "requested_design_reference": preview_design_reference_requested,
        "effective_mode": "design_reference" if preview_design_reference else "layered_reconstruction",
        "auto_switched_by_background_gate": bg_blocked and not preview_design_reference_requested,
        "layered_pixel_reconstruction_blocked": bg_blocked,
        "reason": bg_gate.get("reason", "") if bg_blocked else "",
        "preflight": preflight,
    }
    analysis["preview_decision"] = preview_decision
    if auto_analyze and bg_blocked:
        analysis["warnings"] = analysis.get("warnings", []) + ["background consistency blocked layered reconstruction"]

    width = int(args.get("width", 480))
    height = int(args.get("height", 800))
    page_name = base.safe_symbol(str(args.get("page_name", "interactive_scene")))

    asset_aliases = {
        "design": _copy_asset(design_path, assets_dir / f"{page_name}_design.png"),
    }
    for key in mood_order:
        asset_aliases[key] = _copy_asset(mood_paths[key], assets_dir / f"mood_{key}.png")

    bg_src = str(args.get("background_src", "S:/ui/background1.jpg"))
    pet_src = str(args.get("pet_src", "S:/ui/pet.png"))
    mood_src = {key: str(args.get(f"{key}_src") or mood_src_args.get(key) or _mood_default_src(key)) for key in mood_order}
    bg_src_macro = str(args.get("background_src_macro", "UI_IMG_SRC_INTERACTIVE_BG"))
    pet_src_macro = str(args.get("pet_src_macro", "UI_IMG_SRC_INTERACTIVE_PET"))
    mood_src_macro = {key: str(args.get(f"{key}_src_macro") or mood_src_macro_args.get(key) or _mood_default_macro(key)) for key in mood_order}
    asset_header = str(args.get("asset_header", "")).strip()
    top_text = str(args.get("top_text", "I am completely\nforgiven-past,\npresent, and"))
    title_text = str(args.get("title_text", "How's your mood"))
    hint_text = str(args.get("hint_text", "today?"))
    top_macro = str(args.get("top_text_macro", "UI_TEXT_INTERACTIVE_SCENE_TOP"))
    title_macro = str(args.get("title_text_macro", "UI_TEXT_INTERACTIVE_SCENE_TITLE"))
    hint_macro = str(args.get("hint_text_macro", "UI_TEXT_INTERACTIVE_SCENE_HINT"))
    font_header = str(args.get("font_header", "")).strip()
    raw_font_macro_exprs = args.get("font_macro_exprs", {})
    if raw_font_macro_exprs is None:
        raw_font_macro_exprs = {}
    if not isinstance(raw_font_macro_exprs, dict) or any(not isinstance(key, str) or not isinstance(value, str) for key, value in raw_font_macro_exprs.items()):
        raise ValueError("font_macro_exprs must be a mapping of font usage to C expressions")
    font_macro_exprs = {key: value.strip() for key, value in raw_font_macro_exprs.items() if value.strip()}

    image_create = "lv_image_create" if version == "v9" else "lv_img_create"
    image_set_src = "lv_image_set_src" if version == "v9" else "lv_img_set_src"
    delete_api = "lv_obj_delete" if version == "v9" else "lv_obj_del"
    custom_events_enabled = bool(args.get("custom_events_enabled", True))
    state_machine_enabled = bool(args.get("state_machine_enabled", True))
    states = base.state_names_from_config(args, {"states": ["idle", "interacting", "selected", "error"]})
    default_event_name = f"UI_{page_name.upper()}_EVENT_SERVER_UPDATE"
    raw_event_name = args.get("server_update_event_name", "auto")
    event_name = base.c_identifier(default_event_name if str(raw_event_name).lower() == "auto" else raw_event_name, default=default_event_name)

    c_path = output_dir / f"ui_{page_name}.c"
    h_path = output_dir / f"ui_{page_name}.h"
    spec_path = output_dir / f"{page_name}_spec.json"
    analysis_report_path = output_dir / "analysis_report.json"
    design_reference_preview_path = output_dir / "design_reference_preview.html"
    preview_path = output_dir / "preview.html"
    readme_path = output_dir / "README.md"
    manifest_path = output_dir / "manifest.json"
    quality_gates_path = output_dir / "quality_gates.json"

    pet = dict(analysis["pet"])
    panel = dict(analysis["glass_panel"])
    top_prompt = dict(analysis["text"].get("top_prompt", {"x": 86, "y": 136, "w": 310, "h": 150, "font": 34}))
    title = dict(analysis["text"]["title"])
    hint = dict(analysis["text"]["hint"])
    status_bar = dict(analysis.get("status_bar", {}))
    favorite = dict(status_bar.get("favorite", {"x": 259, "y": 30, "w": 27, "h": 4}))
    wifi = dict(status_bar.get("wifi", {"x": 297, "y": 20, "w": 31, "h": 23}))
    bluetooth = dict(status_bar.get("bluetooth", {"x": 363, "y": 18, "w": 21, "h": 29}))
    battery = dict(status_bar.get("battery", {"x": 413, "y": 23, "w": 36, "h": 18}))
    moods = list(analysis["moods"])
    create_fn = f"ui_{page_name}_create"
    destroy_fn = f"ui_{page_name}_destroy"
    set_prompt_fn = f"ui_{page_name}_set_prompt_text"
    set_mood_fn = f"ui_{page_name}_set_selected_mood"

    spec = {
        "schema": "freertos-embedded-architect.lvgl.interactive-scene.v1",
        "page_name": page_name,
        "display": {"width": width, "height": height, "color_depth": base.DISPLAY_CONFIG["display"]["color_depth"]},
        "lvgl_version": version,
        "design": str(design_path),
        "analysis": analysis,
        "asset_aliases": asset_aliases,
        "background_consistency_gate": bg_gate,
        "preview_decision": preview_decision,
        "custom_events": {"enabled": custom_events_enabled, "server_update_event_name": event_name},
        "state_machine": {"enabled": state_machine_enabled, "states": states},
        "assets": [
            {"id": "background", "path": str(background_path), "runtime_src": bg_src, "size": [width, height]},
            {"id": "pet", "path": str(pet_path), "runtime_src": pet_src, "pos": [pet["x"], pet["y"]], "size": [pet["w"], pet["h"]]},
            *[{"id": f"mood_{m['id']}", "path": m["asset_path"], "runtime_src": mood_src[m["id"]], "pos": [m["icon"]["x"], m["icon"]["y"]], "size": [m["icon"]["w"], m["icon"]["h"]]} for m in moods],
        ],
        "fonts": {"header": font_header or None, "macro_expressions": font_macro_exprs},
        "components": [
            {"id": "background", "type": "image", "pos": [0, 0], "size": [width, height], "source": "cut_asset"},
            {"id": "pet", "type": "image", "pos": [pet["x"], pet["y"]], "size": [pet["w"], pet["h"]], "source": "matched_cut_asset"},
            {"id": "top_prompt", "type": "label", "pos": [top_prompt["x"], top_prompt["y"]], "size": [top_prompt["w"], top_prompt["h"]], "text_macro": top_macro, "source": top_prompt.get("source")},
            {"id": "favorite", "type": "dynamic_status_component", "pos": [favorite["x"], favorite["y"]], "size": [favorite["w"], favorite["h"]], "source": favorite.get("source")},
            {"id": "wifi", "type": "dynamic_status_component", "pos": [wifi["x"], wifi["y"]], "size": [wifi["w"], wifi["h"]], "source": wifi.get("source")},
            {"id": "bluetooth", "type": "dynamic_status_component", "pos": [bluetooth["x"], bluetooth["y"]], "size": [bluetooth["w"], bluetooth["h"]], "source": bluetooth.get("source")},
            {"id": "battery", "type": "dynamic_status_component", "pos": [battery["x"], battery["y"]], "size": [battery["w"], battery["h"]], "source": battery.get("source")},
            {"id": "interaction_panel", "type": "container", "pos": [panel["x"], panel["y"]], "size": [panel["w"], panel["h"]], "radius": panel["radius"], "source": panel.get("source")},
            {"id": "title", "type": "label", "pos": [title["x"], title["y"]], "size": [title["w"], title["h"]], "text_macro": title_macro, "source": title.get("source")},
            {"id": "hint", "type": "label", "pos": [hint["x"], hint["y"]], "size": [hint["w"], hint["h"]], "text_macro": hint_macro, "source": hint.get("source")},
            *[{"id": f"mood_{m['id']}", "type": "mood_button", "button": m["button"], "icon": m["icon"], "image_macro": mood_src_macro[m["id"]]} for m in moods],
        ],
    }
    base._write_json(spec_path, spec)
    base._write_json(analysis_report_path, analysis)
    analysis_artifacts = _write_analysis_artifacts(output_dir, design_path, analysis)
    preview_crops = _write_preview_crops(output_dir, design_path, analysis)
    layered_preview_path = (
        _write_layered_preview(
            output_dir,
            background_path,
            pet_path,
            analysis,
            moods=moods,
            mood_order=mood_order,
            asset_aliases=asset_aliases,
            width=width,
            height=height,
        )
        if should_run_layered
        else None
    )

    runtime_support = base.render_runtime_c_support(page_name, root_var="s_page", lvgl_version=version, event_name=event_name, custom_events_enabled=custom_events_enabled, state_machine_enabled=state_machine_enabled, states=states)
    runtime_decls = base.render_runtime_h_decls(page_name, event_name=event_name, custom_events_enabled=custom_events_enabled, state_machine_enabled=state_machine_enabled, states=states)
    create_runtime = ""
    if custom_events_enabled:
        create_runtime = f"    ui_{page_name}_custom_events_init();\n    lv_obj_add_event_cb(s_page, ui_{page_name}_server_update_cb, LV_EVENT_ALL, NULL);"
    state_runtime = f"    ui_{page_name}_set_state(UI_{page_name.upper()}_STATE_{states[0].upper()});" if state_machine_enabled else ""
    mood_macro_defs = "\n\n".join(f"#ifndef {mood_src_macro[m]}\n#define {mood_src_macro[m]} {base.image_source_expr(mood_src[m])}\n#endif" for m in mood_order)
    mood_specs = ",\n".join(f"    {{{_enum_constant(page_name, m['id'])}, {int(m['button']['x'])}, {int(m['button']['y'])}, {int(m['button']['w'])}, {int(m['button']['h'])}, {int(m['icon']['x'] - m['button']['x'])}, {int(m['icon']['y'] - m['button']['y'])}, {int(m['icon']['w'])}, {int(m['icon']['h'])}, {mood_src_macro[m['id']]} }}" for m in moods)
    asset_include = f'#include "{base.c_string(asset_header)}"\n' if asset_header else ""
    font_include = f'#include "{base.c_string(font_header)}"\n' if font_header else ""
    font_macro_defaults = "\n\n".join(
        f"#ifndef {macro}\n#define {macro} {font_macro_exprs[usage]}\n#endif"
        for usage, macro in (("top", "UI_FONT_INTERACTIVE_SCENE_TOP"), ("title", "UI_FONT_INTERACTIVE_SCENE_TITLE"), ("hint", "UI_FONT_INTERACTIVE_SCENE_HINT"))
        if usage in font_macro_exprs
    )

    c_source = f'''
#include "ui_{page_name}.h"
{asset_include}
{font_include}

#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>

#ifndef {bg_src_macro}
#define {bg_src_macro} {base.image_source_expr(bg_src)}
#endif

#ifndef {pet_src_macro}
#define {pet_src_macro} {base.image_source_expr(pet_src)}
#endif

{mood_macro_defs}

{font_macro_defaults}

#ifndef {top_macro}
#define {top_macro} {base.c_text_expr(top_text)}
#endif

#ifndef {title_macro}
#define {title_macro} {base.c_text_expr(title_text)}
#endif

#ifndef {hint_macro}
#define {hint_macro} {base.c_text_expr(hint_text)}
#endif

#define UI_INTERACTIVE_SCENE_WIDTH {width}
#define UI_INTERACTIVE_SCENE_HEIGHT {height}
#define UI_INTERACTIVE_SCENE_MOOD_COUNT {len(mood_order)}U

typedef struct {{
    ui_{page_name}_mood_t mood;
    int32_t button_x;
    int32_t button_y;
    int32_t button_w;
    int32_t button_h;
    int32_t icon_x;
    int32_t icon_y;
    int32_t icon_w;
    int32_t icon_h;
    const void *src;
}} ui_{page_name}_mood_spec_t;

static lv_obj_t *s_page;
static lv_obj_t *s_panel;
static lv_obj_t *s_top_prompt;
static lv_obj_t *s_title;
static lv_obj_t *s_hint;
static lv_obj_t *s_mood_buttons[UI_INTERACTIVE_SCENE_MOOD_COUNT];
static ui_{page_name}_mood_t s_selected_mood = UI_{page_name.upper()}_MOOD_NONE;
static lv_style_t s_panel_style;
static lv_style_t s_top_style;
static lv_style_t s_title_style;
static lv_style_t s_hint_style;
static lv_style_t s_mood_button_style;
static lv_style_t s_mood_button_selected_style;

static const ui_{page_name}_mood_spec_t s_mood_specs[UI_INTERACTIVE_SCENE_MOOD_COUNT] = {{
{mood_specs}
}};

{runtime_support}

static void init_styles(void)
{{
    static bool inited = false;
    if (inited) {{
        return;
    }}
    inited = true;

    lv_style_init(&s_panel_style);
    lv_style_set_radius(&s_panel_style, {int(panel['radius'])});
    lv_style_set_bg_color(&s_panel_style, lv_color_hex(0xFFFFFF));
    lv_style_set_bg_opa(&s_panel_style, LV_OPA_24);
    lv_style_set_border_color(&s_panel_style, lv_color_hex(0xFFFFFF));
    lv_style_set_border_opa(&s_panel_style, LV_OPA_32);
    lv_style_set_border_width(&s_panel_style, 1);

    lv_style_init(&s_top_style);
    lv_style_set_text_color(&s_top_style, lv_color_hex(0xFFFFFF));
    lv_style_set_text_align(&s_top_style, LV_TEXT_ALIGN_CENTER);
#ifdef UI_FONT_INTERACTIVE_SCENE_TOP
    lv_style_set_text_font(&s_top_style, UI_FONT_INTERACTIVE_SCENE_TOP);
#endif

    lv_style_init(&s_title_style);
    lv_style_set_text_color(&s_title_style, lv_color_hex(0xFFFFFF));
    lv_style_set_text_align(&s_title_style, LV_TEXT_ALIGN_CENTER);
#ifdef UI_FONT_INTERACTIVE_SCENE_TITLE
    lv_style_set_text_font(&s_title_style, UI_FONT_INTERACTIVE_SCENE_TITLE);
#endif

    lv_style_init(&s_hint_style);
    lv_style_set_text_color(&s_hint_style, lv_color_hex(0xFFFFFF));
    lv_style_set_text_opa(&s_hint_style, LV_OPA_90);
    lv_style_set_text_align(&s_hint_style, LV_TEXT_ALIGN_CENTER);
#ifdef UI_FONT_INTERACTIVE_SCENE_HINT
    lv_style_set_text_font(&s_hint_style, UI_FONT_INTERACTIVE_SCENE_HINT);
#endif

    lv_style_init(&s_mood_button_style);
    lv_style_set_radius(&s_mood_button_style, LV_RADIUS_CIRCLE);
    lv_style_set_bg_color(&s_mood_button_style, lv_color_hex(0xFFFFFF));
    lv_style_set_bg_opa(&s_mood_button_style, LV_OPA_COVER);
    lv_style_set_border_width(&s_mood_button_style, 0);
    lv_style_set_pad_all(&s_mood_button_style, 0);

    lv_style_init(&s_mood_button_selected_style);
    lv_style_set_radius(&s_mood_button_selected_style, LV_RADIUS_CIRCLE);
    lv_style_set_border_color(&s_mood_button_selected_style, lv_color_hex(0xFFFFFF));
    lv_style_set_border_width(&s_mood_button_selected_style, 3);
    lv_style_set_border_opa(&s_mood_button_selected_style, LV_OPA_COVER);
}}

static void mood_button_event_cb(lv_event_t *e)
{{
    if (lv_event_get_code(e) != LV_EVENT_CLICKED) {{
        return;
    }}
    ui_{page_name}_mood_t mood = (ui_{page_name}_mood_t)(uintptr_t)lv_event_get_user_data(e);
    {set_mood_fn}(mood);
    /* TODO: Notify presenter/model that the user selected this mood. */
}}

lv_obj_t *{create_fn}(lv_obj_t *parent)
{{
    init_styles();

    s_page = lv_obj_create(parent);
    lv_obj_set_size(s_page, UI_INTERACTIVE_SCENE_WIDTH, UI_INTERACTIVE_SCENE_HEIGHT);
    lv_obj_clear_flag(s_page, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_set_style_border_width(s_page, 0, 0);
    lv_obj_set_style_pad_all(s_page, 0, 0);
    lv_obj_set_style_bg_color(s_page, lv_color_hex(0x79A05F), 0);

{create_runtime}

    lv_obj_t *bg = {image_create}(s_page);
    {image_set_src}(bg, {bg_src_macro});
    /* LVGL_LAYOUT_EXCEPTION: full-screen background cut asset inferred from design. */
    lv_obj_set_pos(bg, 0, 0);
    lv_obj_set_size(bg, UI_INTERACTIVE_SCENE_WIDTH, UI_INTERACTIVE_SCENE_HEIGHT);

    lv_obj_t *favorite = lv_obj_create(s_page);
    lv_obj_remove_style_all(favorite);
    lv_obj_set_style_bg_color(favorite, lv_color_hex(0xFFFFFF), 0);
    lv_obj_set_style_bg_opa(favorite, LV_OPA_COVER, 0);
    lv_obj_set_style_radius(favorite, 2, 0);
    /* LVGL_LAYOUT_EXCEPTION: favorite marker/status glyph approximated as a dynamic LVGL component because no cutout was provided. */
    lv_obj_set_pos(favorite, {int(favorite['x'])}, {int(favorite['y'])});
    lv_obj_set_size(favorite, {int(favorite['w'])}, {int(favorite['h'])});

    lv_obj_t *wifi = lv_label_create(s_page);
    lv_label_set_text(wifi, "wifi");
    lv_obj_set_style_text_color(wifi, lv_color_hex(0xFFFFFF), 0);
    /* LVGL_LAYOUT_EXCEPTION: top wifi glyph approximated as text because no cutout was provided. */
    lv_obj_set_pos(wifi, {int(wifi['x'])}, {int(wifi['y'])});
    lv_obj_set_size(wifi, {int(wifi['w'])}, {int(wifi['h'])});

    lv_obj_t *bluetooth = lv_label_create(s_page);
    lv_label_set_text(bluetooth, "B");
    lv_obj_set_style_text_color(bluetooth, lv_color_hex(0xFFFFFF), 0);
    /* LVGL_LAYOUT_EXCEPTION: top bluetooth glyph approximated as text because no cutout was provided. */
    lv_obj_set_pos(bluetooth, {int(bluetooth['x'])}, {int(bluetooth['y'])});
    lv_obj_set_size(bluetooth, {int(bluetooth['w'])}, {int(bluetooth['h'])});

    lv_obj_t *battery = lv_obj_create(s_page);
    lv_obj_remove_style_all(battery);
    lv_obj_set_style_bg_opa(battery, LV_OPA_TRANSP, 0);
    lv_obj_set_style_border_color(battery, lv_color_hex(0xFFFFFF), 0);
    lv_obj_set_style_border_width(battery, 2, 0);
    lv_obj_set_style_radius(battery, 2, 0);
    /* LVGL_LAYOUT_EXCEPTION: top battery glyph approximated as a dynamic LVGL component because no cutout was provided. */
    lv_obj_set_pos(battery, {int(battery['x'])}, {int(battery['y'])});
    lv_obj_set_size(battery, {int(battery['w'])}, {int(battery['h'])});

    lv_obj_t *battery_fill = lv_obj_create(battery);
    lv_obj_remove_style_all(battery_fill);
    lv_obj_set_style_bg_color(battery_fill, lv_color_hex(0xFFFFFF), 0);
    lv_obj_set_style_bg_opa(battery_fill, LV_OPA_COVER, 0);
    /* LVGL_LAYOUT_EXCEPTION: battery fill is positioned inside the fixed battery outline. */
    lv_obj_set_pos(battery_fill, 4, 4);
    lv_obj_set_size(battery_fill, {max(1, int(battery['w']) - 10)}, {max(1, int(battery['h']) - 8)});

    s_top_prompt = lv_label_create(s_page);
    lv_obj_add_style(s_top_prompt, &s_top_style, 0);
    lv_label_set_long_mode(s_top_prompt, LV_LABEL_LONG_WRAP);
    lv_label_set_text(s_top_prompt, {top_macro});
    /* LVGL_LAYOUT_EXCEPTION: top prompt bbox inferred from bright text cluster in the design screenshot. */
    lv_obj_set_pos(s_top_prompt, {int(top_prompt['x'])}, {int(top_prompt['y'])});
    lv_obj_set_size(s_top_prompt, {int(top_prompt['w'])}, {int(top_prompt['h'])});

    lv_obj_t *pet = {image_create}(s_page);
    {image_set_src}(pet, {pet_src_macro});
    /* LVGL_LAYOUT_EXCEPTION: pet cutout position matched by alpha-template analysis. */
    lv_obj_set_pos(pet, {int(pet['x'])}, {int(pet['y'])});
    lv_obj_set_size(pet, {int(pet['w'])}, {int(pet['h'])});

    s_panel = lv_obj_create(s_page);
    lv_obj_remove_style_all(s_panel);
    lv_obj_add_style(s_panel, &s_panel_style, 0);
    lv_obj_clear_flag(s_panel, LV_OBJ_FLAG_SCROLLABLE);
    /* LVGL_LAYOUT_EXCEPTION: bottom interaction panel bbox inferred from bright panel edges and mood button bounds. */
    lv_obj_set_pos(s_panel, {int(panel['x'])}, {int(panel['y'])});
    lv_obj_set_size(s_panel, {int(panel['w'])}, {int(panel['h'])});

    s_title = lv_label_create(s_page);
    lv_obj_add_style(s_title, &s_title_style, 0);
    lv_label_set_long_mode(s_title, LV_LABEL_LONG_WRAP);
    lv_label_set_text(s_title, {title_macro});
    /* LVGL_LAYOUT_EXCEPTION: title label bbox inferred from top bright text cluster. */
    lv_obj_set_pos(s_title, {int(title['x'])}, {int(title['y'])});
    lv_obj_set_size(s_title, {int(title['w'])}, {int(title['h'])});

    s_hint = lv_label_create(s_page);
    lv_obj_add_style(s_hint, &s_hint_style, 0);
    lv_label_set_long_mode(s_hint, LV_LABEL_LONG_WRAP);
    lv_label_set_text(s_hint, {hint_macro});
    /* LVGL_LAYOUT_EXCEPTION: hint label bbox inferred from lower bright text cluster. */
    lv_obj_set_pos(s_hint, {int(hint['x'])}, {int(hint['y'])});
    lv_obj_set_size(s_hint, {int(hint['w'])}, {int(hint['h'])});

    for (uint32_t i = 0; i < UI_INTERACTIVE_SCENE_MOOD_COUNT; ++i) {{
        const ui_{page_name}_mood_spec_t *spec = &s_mood_specs[i];
        lv_obj_t *button = lv_obj_create(s_page);
        lv_obj_remove_style_all(button);
        lv_obj_add_style(button, &s_mood_button_style, 0);
        lv_obj_add_flag(button, LV_OBJ_FLAG_CLICKABLE);
        lv_obj_add_event_cb(button, mood_button_event_cb, LV_EVENT_CLICKED, (void *)(uintptr_t)spec->mood);
        /* LVGL_LAYOUT_EXCEPTION: mood button position inferred from detected 70px circular button component. */
        lv_obj_set_pos(button, spec->button_x, spec->button_y);
        lv_obj_set_size(button, spec->button_w, spec->button_h);
        s_mood_buttons[i] = button;

        lv_obj_t *icon = {image_create}(button);
        {image_set_src}(icon, spec->src);
        /* LVGL_LAYOUT_EXCEPTION: mood icon offset centered inside the detected button bbox. */
        lv_obj_set_pos(icon, spec->icon_x, spec->icon_y);
        lv_obj_set_size(icon, spec->icon_w, spec->icon_h);
    }}

{state_runtime}

    return s_page;
}}

void {destroy_fn}(void)
{{
    if (s_page != NULL) {{
        {delete_api}(s_page);
        s_page = NULL;
        s_panel = NULL;
        s_top_prompt = NULL;
        s_title = NULL;
        s_hint = NULL;
        for (uint32_t i = 0; i < UI_INTERACTIVE_SCENE_MOOD_COUNT; ++i) {{
            s_mood_buttons[i] = NULL;
        }}
        s_selected_mood = UI_{page_name.upper()}_MOOD_NONE;
    }}
}}

void {set_prompt_fn}(const char *title, const char *hint)
{{
    if (s_title != NULL && title != NULL) {{
        lv_label_set_text(s_title, title);
    }}
    if (s_hint != NULL && hint != NULL) {{
        lv_label_set_text(s_hint, hint);
    }}
}}

void {set_mood_fn}(ui_{page_name}_mood_t mood)
{{
    s_selected_mood = mood;
    for (uint32_t i = 0; i < UI_INTERACTIVE_SCENE_MOOD_COUNT; ++i) {{
        if (s_mood_buttons[i] == NULL) {{
            continue;
        }}
        lv_obj_remove_style(s_mood_buttons[i], &s_mood_button_selected_style, 0);
        if (s_mood_specs[i].mood == mood) {{
            lv_obj_add_style(s_mood_buttons[i], &s_mood_button_selected_style, 0);
        }}
    }}
}}
'''
    c_normalized = base.normalize_generated_source(c_source)
    c_normalized = c_normalized.replace("\ns_mood_buttons[i] = NULL;", "\n            s_mood_buttons[i] = NULL;")
    c_normalized = c_normalized.replace("\ncontinue;", "\n            continue;")
    c_normalized = c_normalized.replace("\nlv_obj_add_style(s_mood_buttons", "\n            lv_obj_add_style(s_mood_buttons")
    c_path.write_text(c_normalized, encoding="utf-8", newline="\n")

    mood_enum_entries = "\n".join(f"    {_enum_constant(page_name, key)} = {idx}," for idx, key in enumerate(mood_order))
    h_source = f'''
#ifndef UI_{page_name.upper()}_H
#define UI_{page_name.upper()}_H

#include "lvgl.h"
#include <stdint.h>

{runtime_decls}

typedef enum {{
    UI_{page_name.upper()}_MOOD_NONE = -1,
{mood_enum_entries}
}} ui_{page_name}_mood_t;

lv_obj_t *{create_fn}(lv_obj_t *parent);
void {destroy_fn}(void);
void {set_prompt_fn}(const char *title, const char *hint);
void {set_mood_fn}(ui_{page_name}_mood_t mood);

#endif /* UI_{page_name.upper()}_H */
'''
    h_path.write_text(base.normalize_generated_source(h_source), encoding="utf-8", newline="\n")

    bg_rel = base.relative_asset_path(background_path, output_dir)
    pet_rel = base.relative_asset_path(pet_path, output_dir)
    mood_rel = {key: base.relative_asset_path(Path(asset_aliases[key]), output_dir) for key in mood_order}
    top_html = "<br>".join(base.html_attr(line) for line in top_text.splitlines())
    top_crop = preview_crops.get("top_prompt") if isinstance(preview_crops.get("top_prompt"), dict) else None
    panel_crop = preview_crops.get("interaction_panel") if isinstance(preview_crops.get("interaction_panel"), dict) else None
    status_crop = preview_crops.get("status_bar") if isinstance(preview_crops.get("status_bar"), dict) else None
    top_crop_html = ""
    if top_crop:
        top_crop_rel = base.relative_asset_path(Path(str(top_crop["path"])), output_dir)
        top_crop_html = f'<img class="top-crop" src="{base.html_attr(top_crop_rel)}" alt="">'
    else:
        top_crop_html = f'<div class="top">{top_html}</div>'
    panel_crop_html = ""
    if panel_crop:
        panel_crop_rel = base.relative_asset_path(Path(str(panel_crop["path"])), output_dir)
        panel_crop_html = f'<img class="panel-crop" src="{base.html_attr(panel_crop_rel)}" alt="">'
    else:
        panel_crop_html = f'<div class="panel"></div><div class="title">{base.html_attr(title_text)}</div><div class="hint">{base.html_attr(hint_text)}</div>'
    status_crop_html = ""
    if status_crop:
        status_crop_rel = base.relative_asset_path(Path(str(status_crop["path"])), output_dir)
        status_crop_html = f'<img class="status-crop" src="{base.html_attr(status_crop_rel)}" alt="">'
    else:
        status_crop_html = '<div class="fav"></div><div class="wifi">wifi</div><div class="bt">B</div><div class="battery"></div>'
    preview_buttons = "\n".join(
        f'<button class="hotspot" data-mood="{base.html_attr(m["id"])}" style="left:{int(m["button"]["x"])}px;top:{int(m["button"]["y"])}px;width:{int(m["button"]["w"])}px;height:{int(m["button"]["h"])}px" aria-label="{base.html_attr(m["id"])}"></button>' for m in moods
    )
    mood_macro_list = ", ".join(f"`{mood_src_macro[key]}`" for key in mood_order)
    asset_header_note = f"- Include `{asset_header}` before using the default asset macros.\n" if asset_header else ""
    design_rel = base.relative_asset_path(Path(asset_aliases["design"]), output_dir)
    preview = f'''
<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Interactive Scene Preview</title>
<style>
body{{margin:0;min-height:100vh;display:grid;place-items:center;background:#1d2419}}.screen{{position:relative;width:{width}px;height:{height}px;overflow:hidden;background:#79a05f}}.design{{position:absolute;inset:0;width:100%;height:100%;display:block;user-select:none;pointer-events:none}}.hotspot{{position:absolute;border:0;padding:0;margin:0;background:transparent;border-radius:50%;cursor:pointer}}.hotspot:focus-visible{{outline:2px solid rgba(255,255,255,.85);outline-offset:2px}}
</style></head><body><div class="screen"><img class="design" src="{base.html_attr(design_rel)}" alt="">{preview_buttons}</div></body></html>
'''
    design_reference_preview_path.write_text(textwrap.dedent(preview), encoding="utf-8", newline="\n")
    if design_reference_preview_path != preview_path:
        shutil.copy2(design_reference_preview_path, preview_path)

    readme = f'''
# Interactive Scene LVGL Page

Generated from the interactive scene design.

`preview.html` mode is selected by the background consistency gate. When the clean background does not match the design screenshot, preview switches to design-reference mode and keeps transparent mood hit zones. Use `analysis_report.json` and `debug_overlay.png` for detection QA.

Background consistency gate:

- Verdict: `{bg_gate.get('verdict', 'unknown')}`
- Layered pixel reconstruction blocked: `{str(bg_blocked).lower()}`
- Preview mode: `{preview_decision['effective_mode']}`
- Reason: {bg_gate.get('reason') or 'background asset is within threshold'}

Detected layout:

- Pet: x={pet['x']}, y={pet['y']}, w={pet['w']}, h={pet['h']}
- Top prompt: x={top_prompt['x']}, y={top_prompt['y']}, w={top_prompt['w']}, h={top_prompt['h']}
- Interaction panel: x={panel['x']}, y={panel['y']}, w={panel['w']}, h={panel['h']}
- Mood buttons: {', '.join(f"{m['id']}@({m['button']['x']},{m['button']['y']},{m['button']['w']},{m['button']['h']})" for m in moods)}

Runtime integration:

{asset_header_note}- Override `{bg_src_macro}`, `{pet_src_macro}`, {mood_macro_list}.
- Override `{top_macro}`, `{title_macro}`, and `{hint_macro}` for final product copy.
- Fonts: {"manifest font bundle is included and selected by default" if font_header else "override `UI_FONT_INTERACTIVE_SCENE_TOP`, `UI_FONT_INTERACTIVE_SCENE_TITLE`, and `UI_FONT_INTERACTIVE_SCENE_HINT` as needed"}.
- Worker/network threads should call `ui_{page_name}_post_server_update(payload)` instead of touching LVGL objects directly.
'''
    readme_path.write_text(textwrap.dedent(readme), encoding="utf-8", newline="\n")

    validation = base.validate_lvgl_layout_code({"path": str(output_dir)})
    quality_gates = _build_quality_gates(
        preflight.get("quality", {}),
        bg_gate,
        analysis,
        validation,
        render_available=False,
        render_verdict="missing",
    )
    quality_gates_path.write_text(json.dumps(quality_gates, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    artifact_paths = [c_path, h_path, spec_path, analysis_report_path, design_reference_preview_path, preview_path, readme_path, quality_gates_path]
    if layered_preview_path:
        artifact_paths.append(Path(layered_preview_path))
    if analysis_artifacts.get("debug_overlay"):
        artifact_paths.append(Path(analysis_artifacts["debug_overlay"]))
    for crop in preview_crops.values():
        if isinstance(crop, dict) and crop.get("path"):
            artifact_paths.append(Path(str(crop["path"])))
    artifact_paths.extend(Path(path) for path in asset_aliases.values())
    artifacts = [str(path) for path in artifact_paths if path.exists()]
    all_artifacts = artifacts + [str(manifest_path)]
    summary = {
        "return_mode": return_mode,
        "page_name": page_name,
        "analysis_method": analysis.get("method"),
        "analysis_ok": bool(analysis.get("ok", False)),
        "key_bboxes": {
            "pet": _bbox_list(pet),
            "top_prompt": _bbox_list(top_prompt),
            "favorite": _bbox_list(favorite),
            "wifi": _bbox_list(wifi),
            "bluetooth": _bbox_list(bluetooth),
            "battery": _bbox_list(battery),
            "glass_panel": _bbox_list(panel),
            "title": _bbox_list(title),
            "hint": _bbox_list(hint),
            "mood_buttons": {m["id"]: _bbox_list(m["button"]) for m in moods},
            "mood_icons": {m["id"]: _bbox_list(m["icon"]) for m in moods},
        },
        "source_files": {
            "design": str(design_path),
            "background": str(background_path),
            "pet": str(pet_path),
            "moods": {key: str(value) for key, value in mood_paths.items()},
        },
        "asset_aliases": asset_aliases,
        "background_consistency_gate": bg_gate,
        "preflight": preflight,
        "preview_decision": preview_decision,
        "quality_gates": quality_gates,
        "reports": {
            "analysis_report": str(analysis_report_path),
            "debug_overlay": analysis_artifacts.get("debug_overlay"),
            "preview_crops": preview_crops,
            "design_reference_preview": str(design_reference_preview_path),
            "preview": str(preview_path),
            "layered_preview": layered_preview_path,
            "manifest": str(manifest_path),
            "quality_gates": str(quality_gates_path),
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
