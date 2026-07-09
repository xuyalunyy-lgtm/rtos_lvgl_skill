from __future__ import annotations

from collections import deque
from pathlib import Path
from typing import Any
import shutil
import textwrap

SCENE_TOKEN = "\u4e92\u52a8\u573a\u666f"
MOOD_TOKENS = {
    "normal": "\u6b63\u5e38",
    "happy": "\u5f00\u5fc3",
    "sad": "\u5931\u843d",
    "angry": "\u6124\u6012",
}
MOOD_ORDER = ("normal", "happy", "sad", "angry")


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


def _fallback(width: int, height: int, mood_sizes: dict[str, tuple[int, int]]) -> dict[str, Any]:
    moods: list[dict[str, Any]] = []
    for idx, mood in enumerate(MOOD_ORDER):
        button = {"x": 64 + idx * 94, "y": 636, "w": 70, "h": 70, "radius": 35, "source": "fallback_static"}
        icon_w, icon_h = mood_sizes[mood]
        icon = {"x": button["x"] + (button["w"] - icon_w) // 2, "y": button["y"] + (button["h"] - icon_h) // 2, "w": icon_w, "h": icon_h, "source": "button_center_fallback"}
        moods.append({"id": mood, "button": button, "icon": icon})
    return {
        "ok": False,
        "method": "fallback_static_interactive_scene",
        "warnings": ["Pillow analysis unavailable; used fixed 480x800 layout."],
        "pet": {"x": 118, "y": 112, "w": 271, "h": 391, "score": None},
        "glass_panel": {"x": 40, "y": 534, "w": 400, "h": 180, "radius": 28, "source": "fallback_static"},
        "text": {
            "title": {"x": 94, "y": 537, "w": 294, "h": 38, "font": 18, "source": "fallback_static"},
            "hint": {"x": 184, "y": 583, "w": 112, "h": 36, "font": 16, "source": "fallback_static"},
        },
        "moods": moods,
        "components": {},
    }


def analyze_interactive_scene(design_path: Path, background_path: Path, pet_path: Path, mood_paths: dict[str, Path], width: int, height: int) -> dict[str, Any]:
    try:
        from PIL import Image
    except Exception as exc:
        fallback = _fallback(width, height, {key: (37, 37) for key in MOOD_ORDER})
        fallback["warnings"] = [f"Pillow import failed: {exc}"]
        return fallback

    design = Image.open(design_path).convert("RGBA")
    background = Image.open(background_path).convert("RGBA")
    pet = Image.open(pet_path).convert("RGBA")
    if background.size != design.size:
        background = background.resize(design.size)
    width, height = design.size
    mood_images = {key: Image.open(path).convert("RGBA") for key, path in mood_paths.items()}

    pet_rect = _match_pet(design, background, pet)
    bright = _components(design, lambda r, g, b, a: a > 20 and r + g + b > 600, region=(30, int(height * 0.60), width - 60, int(height * 0.35)), min_area=40)
    button_candidates = [c for c in bright if 52 <= c["w"] <= 88 and 52 <= c["h"] <= 88 and c["area"] >= 2200 and c["y"] > height * 0.70]
    button_candidates = sorted(button_candidates, key=lambda c: c["x"])[:4]
    if len(button_candidates) != 4:
        button_candidates = [{"x": 64 + idx * 94, "y": 636, "w": 70, "h": 70, "area": 0, "avg_rgb": [255, 255, 255], "source": "fallback_static"} for idx in range(4)]

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
    text_candidates = [
        c for c in bright
        if c not in button_candidates and c["area"] >= 90 and c["y"] < button_y - 8 and c["w"] > 3 and c["h"] > 3
    ]
    upper = [c for c in text_candidates if c["y"] < panel["y"] + 45]
    lower = [c for c in text_candidates if c["y"] >= panel["y"] + 45]
    title = _union(upper) if upper else {"x": panel["x"] + 54, "y": panel["y"] + 6, "w": panel["w"] - 108, "h": 34}
    hint = _union(lower) if lower else {"x": panel["x"] + 130, "y": panel["y"] + 48, "w": panel["w"] - 260, "h": 36}
    title = {"x": int(title["x"]), "y": int(title["y"]), "w": int(max(80, title["w"])), "h": int(max(24, title["h"])), "font": 18, "source": "bright_text_union" if upper else "fallback_static"}
    hint = {"x": int(hint["x"]), "y": int(hint["y"]), "w": int(max(80, hint["w"])), "h": int(max(24, hint["h"])), "font": 16, "source": "bright_text_union" if lower else "fallback_static"}

    moods: list[dict[str, Any]] = []
    for idx, mood in enumerate(MOOD_ORDER):
        src_button = button_candidates[idx]
        image = mood_images[mood]
        icon_w, icon_h = image.size
        button = {"x": int(src_button["x"]), "y": int(src_button["y"]), "w": int(src_button["w"]), "h": int(src_button["h"]), "radius": int(min(src_button["w"], src_button["h"]) // 2), "source": src_button.get("source", "bright_circle_detection")}
        icon = {"x": int(button["x"] + (button["w"] - icon_w) // 2), "y": int(button["y"] + (button["h"] - icon_h) // 2), "w": int(icon_w), "h": int(icon_h), "source": "button_center_from_detected_container"}
        moods.append({"id": mood, "button": button, "icon": icon, "asset_path": str(mood_paths[mood])})

    return {
        "ok": True,
        "method": "pillow_interactive_scene_v1",
        "warnings": [],
        "pet": pet_rect,
        "glass_panel": panel,
        "text": {"title": title, "hint": hint},
        "moods": moods,
        "components": {"bright_bottom": bright[:80], "text_candidates": text_candidates[:40]},
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
            ("title", (analysis.get("text") or {}).get("title"), "#FFFFFF"),
            ("hint", (analysis.get("text") or {}).get("hint"), "#FFD23F"),
        )
        for label, rect, color in boxes:
            if not isinstance(rect, dict) or int(rect.get("w", 0)) <= 0 or int(rect.get("h", 0)) <= 0:
                continue
            x, y, w, h = int(rect["x"]), int(rect["y"]), int(rect["w"]), int(rect["h"])
            draw.rectangle((x, y, x + w - 1, y + h - 1), outline=color, width=3)
            draw.text((x + 3, max(0, y - 13)), label, fill=color)
        colors = {"normal": "#00E5FF", "happy": "#42F57B", "sad": "#FFD23F", "angry": "#FF4D4D"}
        for mood in analysis.get("moods", []):
            color = colors.get(mood.get("id"), "#FFFFFF")
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


def _copy_asset(src: Path, dst: Path) -> str:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.resolve() != dst.resolve():
        shutil.copyfile(src, dst)
    return str(dst)


def generate_interactive_scene_page(args: dict[str, Any]) -> dict[str, Any]:
    import lvgl_ui as base

    design_dir = base.resolve_path(args.get("design_dir", base.ROOT / "ui"))
    output_dir = base.resolve_path(args.get("output_dir", base.ROOT / "artifacts" / "lvgl_ui" / "interactive_scene"))
    output_dir.mkdir(parents=True, exist_ok=True)
    assets_dir = output_dir / "assets"
    version = str(args.get("lvgl_version", base.DISPLAY_CONFIG["lvgl"]["version"]))
    base.require_choice("lvgl_version", version, base.LVGL_VERSIONS)

    design_path = base.resolve_path(args.get("design_path", _find_by_token(design_dir, SCENE_TOKEN)))
    background_path = base.resolve_path(args.get("background_path", design_dir / base.INITIAL_LOADING_BACKGROUND_FILE))
    pet_path = base.resolve_path(args.get("pet_path", design_dir / base.INITIAL_LOADING_PET_FILE))
    mood_paths = {key: base.resolve_path(args.get(f"{key}_path", _find_by_token(design_dir, MOOD_TOKENS[key]))) for key in MOOD_ORDER}
    for item in (design_path, background_path, pet_path, *mood_paths.values()):
        if not item.is_file():
            raise ValueError(f"design asset does not exist: {item}")

    width = int(args.get("width", base.DISPLAY_CONFIG["display"]["width"]))
    height = int(args.get("height", base.DISPLAY_CONFIG["display"]["height"]))
    analysis = analyze_interactive_scene(design_path, background_path, pet_path, mood_paths, width, height) if bool(args.get("auto_analyze", True)) else _fallback(width, height, {key: (37, 37) for key in MOOD_ORDER})
    width = int(args.get("width", 480))
    height = int(args.get("height", 800))
    page_name = base.safe_symbol(str(args.get("page_name", "interactive_scene")))

    asset_aliases = {
        "design": _copy_asset(design_path, assets_dir / "interactive_scene_no_favorite.png"),
        "normal": _copy_asset(mood_paths["normal"], assets_dir / "mood_normal.png"),
        "happy": _copy_asset(mood_paths["happy"], assets_dir / "mood_happy.png"),
        "sad": _copy_asset(mood_paths["sad"], assets_dir / "mood_sad.png"),
        "angry": _copy_asset(mood_paths["angry"], assets_dir / "mood_angry.png"),
    }

    bg_src = str(args.get("background_src", "S:/ui/background1.jpg"))
    pet_src = str(args.get("pet_src", "S:/ui/pet.png"))
    mood_src = {"normal": str(args.get("normal_src", "S:/ui/mood_normal.png")), "happy": str(args.get("happy_src", "S:/ui/mood_happy.png")), "sad": str(args.get("sad_src", "S:/ui/mood_sad.png")), "angry": str(args.get("angry_src", "S:/ui/mood_angry.png"))}
    bg_src_macro = str(args.get("background_src_macro", "UI_IMG_SRC_INTERACTIVE_BG"))
    pet_src_macro = str(args.get("pet_src_macro", "UI_IMG_SRC_INTERACTIVE_PET"))
    mood_src_macro = {"normal": str(args.get("normal_src_macro", "UI_IMG_SRC_MOOD_NORMAL")), "happy": str(args.get("happy_src_macro", "UI_IMG_SRC_MOOD_HAPPY")), "sad": str(args.get("sad_src_macro", "UI_IMG_SRC_MOOD_SAD")), "angry": str(args.get("angry_src_macro", "UI_IMG_SRC_MOOD_ANGRY"))}
    title_text = str(args.get("title_text", "How are you feeling?"))
    hint_text = str(args.get("hint_text", "Choose a mood"))
    title_macro = str(args.get("title_text_macro", "UI_TEXT_INTERACTIVE_SCENE_TITLE"))
    hint_macro = str(args.get("hint_text_macro", "UI_TEXT_INTERACTIVE_SCENE_HINT"))

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
    preview_path = output_dir / "preview.html"
    readme_path = output_dir / "README.md"
    manifest_path = output_dir / "manifest.json"

    pet = dict(analysis["pet"])
    panel = dict(analysis["glass_panel"])
    title = dict(analysis["text"]["title"])
    hint = dict(analysis["text"]["hint"])
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
        "custom_events": {"enabled": custom_events_enabled, "server_update_event_name": event_name},
        "state_machine": {"enabled": state_machine_enabled, "states": states},
        "assets": [
            {"id": "background", "path": str(background_path), "runtime_src": bg_src, "size": [width, height]},
            {"id": "pet", "path": str(pet_path), "runtime_src": pet_src, "pos": [pet["x"], pet["y"]], "size": [pet["w"], pet["h"]]},
            *[{"id": f"mood_{m['id']}", "path": m["asset_path"], "runtime_src": mood_src[m["id"]], "pos": [m["icon"]["x"], m["icon"]["y"]], "size": [m["icon"]["w"], m["icon"]["h"]]} for m in moods],
        ],
        "components": [
            {"id": "background", "type": "image", "pos": [0, 0], "size": [width, height], "source": "cut_asset"},
            {"id": "pet", "type": "image", "pos": [pet["x"], pet["y"]], "size": [pet["w"], pet["h"]], "source": "matched_cut_asset"},
            {"id": "interaction_panel", "type": "container", "pos": [panel["x"], panel["y"]], "size": [panel["w"], panel["h"]], "radius": panel["radius"], "source": panel.get("source")},
            {"id": "title", "type": "label", "pos": [title["x"], title["y"]], "size": [title["w"], title["h"]], "text_macro": title_macro, "source": title.get("source")},
            {"id": "hint", "type": "label", "pos": [hint["x"], hint["y"]], "size": [hint["w"], hint["h"]], "text_macro": hint_macro, "source": hint.get("source")},
            *[{"id": f"mood_{m['id']}", "type": "mood_button", "button": m["button"], "icon": m["icon"], "image_macro": mood_src_macro[m["id"]]} for m in moods],
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
    mood_macro_defs = "\n\n".join(f"#ifndef {mood_src_macro[m]}\n#define {mood_src_macro[m]} {base.image_source_expr(mood_src[m])}\n#endif" for m in MOOD_ORDER)
    mood_specs = ",\n".join(f"    {{UI_{page_name.upper()}_MOOD_{m['id'].upper()}, {int(m['button']['x'])}, {int(m['button']['y'])}, {int(m['button']['w'])}, {int(m['button']['h'])}, {int(m['icon']['x'] - m['button']['x'])}, {int(m['icon']['y'] - m['button']['y'])}, {int(m['icon']['w'])}, {int(m['icon']['h'])}, {mood_src_macro[m['id']]} }}" for m in moods)

    c_source = f'''
#include "ui_{page_name}.h"

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

#ifndef {title_macro}
#define {title_macro} {base.c_text_expr(title_text)}
#endif

#ifndef {hint_macro}
#define {hint_macro} {base.c_text_expr(hint_text)}
#endif

#define UI_INTERACTIVE_SCENE_WIDTH {width}
#define UI_INTERACTIVE_SCENE_HEIGHT {height}
#define UI_INTERACTIVE_SCENE_MOOD_COUNT 4U

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
static lv_obj_t *s_title;
static lv_obj_t *s_hint;
static lv_obj_t *s_mood_buttons[UI_INTERACTIVE_SCENE_MOOD_COUNT];
static ui_{page_name}_mood_t s_selected_mood = UI_{page_name.upper()}_MOOD_NONE;
static lv_style_t s_panel_style;
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

    lv_style_init(&s_title_style);
    lv_style_set_text_color(&s_title_style, lv_color_hex(0xFFFFFF));
#ifdef UI_FONT_INTERACTIVE_SCENE_TITLE
    lv_style_set_text_font(&s_title_style, UI_FONT_INTERACTIVE_SCENE_TITLE);
#endif

    lv_style_init(&s_hint_style);
    lv_style_set_text_color(&s_hint_style, lv_color_hex(0xFFFFFF));
    lv_style_set_text_opa(&s_hint_style, LV_OPA_90);
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

    h_source = f'''
#ifndef UI_{page_name.upper()}_H
#define UI_{page_name.upper()}_H

#include "lvgl.h"
#include <stdint.h>

{runtime_decls}

typedef enum {{
    UI_{page_name.upper()}_MOOD_NONE = -1,
    UI_{page_name.upper()}_MOOD_NORMAL = 0,
    UI_{page_name.upper()}_MOOD_HAPPY,
    UI_{page_name.upper()}_MOOD_SAD,
    UI_{page_name.upper()}_MOOD_ANGRY,
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
    mood_rel = {key: base.relative_asset_path(Path(asset_aliases[key]), output_dir) for key in MOOD_ORDER}
    preview_buttons = "\n".join(
        f'<div class="mood" style="left:{int(m["button"]["x"])}px;top:{int(m["button"]["y"])}px;width:{int(m["button"]["w"])}px;height:{int(m["button"]["h"])}px"><img src="{base.html_attr(mood_rel[m["id"]])}" style="left:{int(m["icon"]["x"] - m["button"]["x"])}px;top:{int(m["icon"]["y"] - m["button"]["y"])}px;width:{int(m["icon"]["w"])}px;height:{int(m["icon"]["h"])}px" alt=""></div>' for m in moods
    )
    preview = f'''
<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Interactive Scene Preview</title>
<style>
body{{margin:0;min-height:100vh;display:grid;place-items:center;background:#1d2419}}.screen{{position:relative;width:{width}px;height:{height}px;overflow:hidden;background:#79a05f}}.screen img{{position:absolute;display:block;user-select:none;pointer-events:none}}.bg{{inset:0;width:100%;height:100%;object-fit:cover}}.pet{{left:{int(pet['x'])}px;top:{int(pet['y'])}px;width:{int(pet['w'])}px;height:{int(pet['h'])}px}}.panel{{position:absolute;left:{int(panel['x'])}px;top:{int(panel['y'])}px;width:{int(panel['w'])}px;height:{int(panel['h'])}px;border-radius:{int(panel['radius'])}px;background:rgba(255,255,255,.24);border:1px solid rgba(255,255,255,.32)}}.title{{position:absolute;left:{int(title['x'])}px;top:{int(title['y'])}px;width:{int(title['w'])}px;min-height:{int(title['h'])}px;color:#fff;font:600 {int(title.get('font',18))}px/1.35 system-ui,"Microsoft YaHei",sans-serif}}.hint{{position:absolute;left:{int(hint['x'])}px;top:{int(hint['y'])}px;width:{int(hint['w'])}px;min-height:{int(hint['h'])}px;color:rgba(255,255,255,.9);font:{int(hint.get('font',16))}px/1.35 system-ui,"Microsoft YaHei",sans-serif}}.mood{{position:absolute;border-radius:50%;background:#fff}}.mood img{{position:absolute}}
</style></head><body><div class="screen"><img class="bg" src="{base.html_attr(bg_rel)}" alt=""><img class="pet" src="{base.html_attr(pet_rel)}" alt=""><div class="panel"></div><div class="title">{base.html_attr(title_text)}</div><div class="hint">{base.html_attr(hint_text)}</div>{preview_buttons}</div></body></html>
'''
    preview_path.write_text(textwrap.dedent(preview), encoding="utf-8", newline="\n")

    readme = f'''
# Interactive Scene LVGL Page

Generated from the no-favorite interactive scene design.

`preview.html` is an approximate browser preview. Use `analysis_report.json` and `debug_overlay.png` for detection QA.

Detected layout:

- Pet: x={pet['x']}, y={pet['y']}, w={pet['w']}, h={pet['h']}
- Interaction panel: x={panel['x']}, y={panel['y']}, w={panel['w']}, h={panel['h']}
- Mood buttons: {', '.join(f"{m['id']}@({m['button']['x']},{m['button']['y']},{m['button']['w']},{m['button']['h']})" for m in moods)}

Runtime integration:

- Override `{bg_src_macro}`, `{pet_src_macro}`, `{mood_src_macro['normal']}`, `{mood_src_macro['happy']}`, `{mood_src_macro['sad']}`, `{mood_src_macro['angry']}`.
- Override `{title_macro}` and `{hint_macro}` for final product copy.
- Optional font macros: `UI_FONT_INTERACTIVE_SCENE_TITLE`, `UI_FONT_INTERACTIVE_SCENE_HINT`.
- Worker/network threads should call `ui_{page_name}_post_server_update(payload)` instead of touching LVGL objects directly.
'''
    readme_path.write_text(textwrap.dedent(readme), encoding="utf-8", newline="\n")

    validation = base.validate_lvgl_layout_code({"path": str(output_dir)})
    artifact_paths = [c_path, h_path, spec_path, analysis_report_path, preview_path, readme_path]
    if analysis_artifacts.get("debug_overlay"):
        artifact_paths.append(Path(analysis_artifacts["debug_overlay"]))
    artifact_paths.extend(Path(path) for path in asset_aliases.values())
    artifacts = [str(path) for path in artifact_paths if path.exists()]
    manifest = {"ok": validation["ok"], "page_name": page_name, "artifacts": artifacts, "validation": validation, "analysis_ok": analysis.get("ok", False)}
    base._write_json(manifest_path, manifest)
    return {**manifest, "artifacts": artifacts + [str(manifest_path)]}
