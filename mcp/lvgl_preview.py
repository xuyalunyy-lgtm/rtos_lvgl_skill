"""Pure-Python LVGL preview renderer with zero native dependencies.

The renderer is intentionally approximate. It is meant for quick visual smoke
checks when the native LVGL/SDL sandbox is not available. It renders layout
spec JSON or object-tree JSON into a PNG using only Python stdlib helpers from
``image_io``.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

try:  # Works when executed as ``python mcp/lvgl_preview.py``.
    from image_io import _write_png, read_png, read_png_rgba
except ImportError:  # Works when imported as a package module.
    from .image_io import _write_png, read_png, read_png_rgba


RGB = tuple[int, int, int]
RGBA = tuple[int, int, int, int]

DEFAULT_WIDTH = 480
DEFAULT_HEIGHT = 800
DEFAULT_BG: RGB = (32, 36, 42)
DEFAULT_TEXT: RGB = (245, 247, 250)
DEFAULT_PRIMARY: RGB = (33, 150, 243)
DEFAULT_MUTED: RGB = (92, 101, 113)


def _build_font() -> dict[int, list[int]]:
    raw: dict[int, list[int]] = {
        32: [0, 0, 0, 0, 0, 0, 0],
        33: [4, 4, 4, 4, 4, 0, 4],
        34: [10, 10, 10, 0, 0, 0, 0],
        35: [10, 10, 31, 10, 31, 10, 10],
        36: [4, 30, 5, 14, 20, 15, 4],
        37: [3, 19, 8, 4, 2, 25, 24],
        38: [6, 9, 5, 2, 21, 9, 22],
        39: [4, 4, 4, 0, 0, 0, 0],
        40: [8, 4, 2, 2, 2, 4, 8],
        41: [2, 4, 8, 8, 8, 4, 2],
        42: [0, 4, 21, 14, 21, 4, 0],
        43: [0, 4, 4, 31, 4, 4, 0],
        44: [0, 0, 0, 0, 0, 4, 2],
        45: [0, 0, 0, 31, 0, 0, 0],
        46: [0, 0, 0, 0, 0, 0, 4],
        47: [16, 16, 8, 4, 2, 1, 1],
        48: [14, 17, 25, 21, 19, 17, 14],
        49: [4, 6, 4, 4, 4, 4, 14],
        50: [14, 17, 16, 8, 4, 2, 31],
        51: [31, 8, 4, 8, 16, 17, 14],
        52: [8, 12, 10, 9, 31, 8, 8],
        53: [31, 1, 15, 16, 16, 17, 14],
        54: [12, 2, 1, 15, 17, 17, 14],
        55: [31, 16, 8, 4, 2, 2, 2],
        56: [14, 17, 17, 14, 17, 17, 14],
        57: [14, 17, 17, 30, 16, 8, 6],
        58: [0, 0, 4, 0, 0, 4, 0],
        59: [0, 0, 4, 0, 0, 4, 2],
        60: [8, 4, 2, 1, 2, 4, 8],
        61: [0, 0, 31, 0, 31, 0, 0],
        62: [2, 4, 8, 16, 8, 4, 2],
        63: [14, 17, 16, 8, 4, 0, 4],
        64: [14, 17, 21, 29, 29, 1, 14],
        65: [4, 10, 17, 17, 31, 17, 17],
        66: [15, 17, 17, 15, 17, 17, 15],
        67: [14, 17, 1, 1, 1, 17, 14],
        68: [7, 9, 17, 17, 17, 9, 7],
        69: [31, 1, 1, 15, 1, 1, 31],
        70: [31, 1, 1, 15, 1, 1, 1],
        71: [14, 17, 1, 29, 17, 17, 14],
        72: [17, 17, 17, 31, 17, 17, 17],
        73: [14, 4, 4, 4, 4, 4, 14],
        74: [28, 8, 8, 8, 8, 9, 6],
        75: [17, 9, 5, 3, 5, 9, 17],
        76: [1, 1, 1, 1, 1, 1, 31],
        77: [17, 27, 21, 21, 17, 17, 17],
        78: [17, 19, 21, 25, 17, 17, 17],
        79: [14, 17, 17, 17, 17, 17, 14],
        80: [15, 17, 17, 15, 1, 1, 1],
        81: [14, 17, 17, 17, 21, 9, 22],
        82: [15, 17, 17, 15, 5, 9, 17],
        83: [14, 17, 1, 14, 16, 17, 14],
        84: [31, 4, 4, 4, 4, 4, 4],
        85: [17, 17, 17, 17, 17, 17, 14],
        86: [17, 17, 17, 17, 10, 10, 4],
        87: [17, 17, 17, 21, 21, 27, 17],
        88: [17, 17, 10, 4, 10, 17, 17],
        89: [17, 17, 10, 4, 4, 4, 4],
        90: [31, 16, 8, 4, 2, 1, 31],
        91: [14, 2, 2, 2, 2, 2, 14],
        92: [1, 1, 2, 4, 8, 16, 16],
        93: [14, 8, 8, 8, 8, 8, 14],
        94: [4, 10, 17, 0, 0, 0, 0],
        95: [0, 0, 0, 0, 0, 0, 31],
        96: [2, 4, 8, 0, 0, 0, 0],
        123: [12, 2, 2, 1, 2, 2, 12],
        124: [4, 4, 4, 0, 4, 4, 4],
        125: [6, 8, 8, 16, 8, 8, 6],
        126: [0, 0, 6, 25, 0, 0, 0],
    }
    for i in range(26):
        raw[97 + i] = raw[65 + i]
    raw.update(
        {
            97: [0, 0, 14, 16, 30, 17, 30],
            98: [1, 1, 15, 17, 17, 17, 15],
            99: [0, 0, 14, 17, 1, 17, 14],
            100: [16, 16, 30, 17, 17, 17, 30],
            101: [0, 0, 14, 17, 31, 1, 14],
            102: [12, 18, 2, 7, 2, 2, 2],
            103: [0, 0, 30, 17, 30, 16, 14],
            104: [1, 1, 15, 17, 17, 17, 17],
            105: [0, 4, 0, 6, 4, 4, 14],
            106: [0, 8, 0, 12, 8, 9, 6],
            107: [1, 1, 9, 5, 3, 5, 9],
            108: [6, 4, 4, 4, 4, 4, 14],
            109: [0, 0, 11, 21, 21, 17, 17],
            110: [0, 0, 15, 17, 17, 17, 17],
            111: [0, 0, 14, 17, 17, 17, 14],
            112: [0, 0, 15, 17, 15, 1, 1],
            113: [0, 0, 30, 17, 30, 16, 16],
            114: [0, 0, 13, 19, 1, 1, 1],
            115: [0, 0, 30, 1, 14, 16, 15],
            116: [2, 2, 7, 2, 2, 18, 12],
            117: [0, 0, 17, 17, 17, 17, 30],
            118: [0, 0, 17, 17, 10, 10, 4],
            119: [0, 0, 17, 17, 21, 21, 10],
            120: [0, 0, 17, 10, 4, 10, 17],
            121: [0, 0, 17, 17, 30, 16, 14],
            122: [0, 0, 31, 8, 4, 2, 31],
        }
    )
    return raw


_GLYPHS = _build_font()
_FONT_W = 5
_FONT_H = 7
_FONT_STEP = 6


class Canvas:
    """Small RGB pixel buffer with the primitives needed for UI previews."""

    def __init__(self, width: int, height: int, bg: RGB = DEFAULT_BG):
        if width <= 0 or height <= 0:
            raise ValueError("canvas dimensions must be positive")
        self.width = width
        self.height = height
        self.pixels: list[RGB] = [bg] * (width * height)

    def _idx(self, x: int, y: int) -> int:
        return y * self.width + x

    def set_pixel(self, x: int, y: int, color: RGB, alpha: int = 255) -> None:
        if not (0 <= x < self.width and 0 <= y < self.height):
            return
        idx = self._idx(x, y)
        self.pixels[idx] = _blend(color, self.pixels[idx], alpha)

    def fill_rect(self, x: int, y: int, w: int, h: int, color: RGB, alpha: int = 255) -> None:
        if w <= 0 or h <= 0 or alpha <= 0:
            return
        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(self.width, x + w)
        y1 = min(self.height, y + h)
        for py in range(y0, y1):
            start = py * self.width
            for px in range(x0, x1):
                idx = start + px
                self.pixels[idx] = _blend(color, self.pixels[idx], alpha)

    def stroke_rect(self, x: int, y: int, w: int, h: int, color: RGB, thickness: int = 1, alpha: int = 255) -> None:
        thickness = max(1, int(thickness))
        self.fill_rect(x, y, w, thickness, color, alpha)
        self.fill_rect(x, y + h - thickness, w, thickness, color, alpha)
        self.fill_rect(x, y, thickness, h, color, alpha)
        self.fill_rect(x + w - thickness, y, thickness, h, color, alpha)

    def fill_rounded_rect(self, x: int, y: int, w: int, h: int, radius: int, color: RGB, alpha: int = 255) -> None:
        r = max(0, min(int(radius), w // 2, h // 2))
        if r <= 0:
            self.fill_rect(x, y, w, h, color, alpha)
            return
        self.fill_rect(x + r, y, w - 2 * r, h, color, alpha)
        self.fill_rect(x, y + r, r, h - 2 * r, color, alpha)
        self.fill_rect(x + w - r, y + r, r, h - 2 * r, color, alpha)
        for dy in range(r + 1):
            for dx in range(r + 1):
                if dx * dx + dy * dy <= r * r:
                    self.set_pixel(x + r - dx, y + r - dy, color, alpha)
                    self.set_pixel(x + w - r - 1 + dx, y + r - dy, color, alpha)
                    self.set_pixel(x + r - dx, y + h - r - 1 + dy, color, alpha)
                    self.set_pixel(x + w - r - 1 + dx, y + h - r - 1 + dy, color, alpha)

    def draw_line(self, x0: int, y0: int, x1: int, y1: int, color: RGB, alpha: int = 255) -> None:
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        while True:
            self.set_pixel(x0, y0, color, alpha)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def draw_text(
        self,
        x: int,
        y: int,
        text: str,
        color: RGB,
        *,
        max_width: int = 0,
        scale: int = 1,
    ) -> int:
        scale = max(1, int(scale))
        cx = x
        for ch in str(text):
            if ch == "\n":
                break
            glyph = _GLYPHS.get(ord(ch), _GLYPHS[63])
            char_w = _FONT_STEP * scale
            if max_width > 0 and cx + char_w > x + max_width:
                break
            for row, bits in enumerate(glyph):
                for col in range(_FONT_W):
                    if bits & (1 << (_FONT_W - 1 - col)):
                        self.fill_rect(cx + col * scale, y + row * scale, scale, scale, color)
            cx += char_w
        return cx - x

    def draw_text_box(
        self,
        x: int,
        y: int,
        w: int,
        h: int,
        text: str,
        color: RGB,
        *,
        align: str = "left",
        valign: str = "center",
        scale: int = 1,
        pad: int = 4,
    ) -> None:
        scale = max(1, int(scale))
        text = str(text)
        text_w = min(self.text_width(text, scale), max(0, w - pad * 2))
        text_h = self.text_height(scale)
        if align in {"center", "mid"}:
            tx = x + max(pad, (w - text_w) // 2)
        elif align in {"right", "end"}:
            tx = x + max(pad, w - text_w - pad)
        else:
            tx = x + pad
        if valign in {"top", "start"}:
            ty = y + pad
        elif valign in {"bottom", "end"}:
            ty = y + max(pad, h - text_h - pad)
        else:
            ty = y + max(0, (h - text_h) // 2)
        self.draw_text(tx, ty, text, color, max_width=max(0, w - pad * 2), scale=scale)

    def text_width(self, text: str, scale: int = 1) -> int:
        return len(str(text)) * _FONT_STEP * max(1, int(scale))

    def text_height(self, scale: int = 1) -> int:
        return _FONT_H * max(1, int(scale))

    def blit_rgba(self, x: int, y: int, w: int, h: int, src_w: int, src_h: int, pixels: list[RGBA]) -> None:
        if w <= 0 or h <= 0 or src_w <= 0 or src_h <= 0:
            return
        for py in range(max(0, h)):
            sy = min(src_h - 1, int(py * src_h / h))
            for px in range(max(0, w)):
                sx = min(src_w - 1, int(px * src_w / w))
                r, g, b, a = pixels[sy * src_w + sx]
                self.set_pixel(x + px, y + py, (r, g, b), a)

    def save_png(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        _write_png(path, self.width, self.height, self.pixels)


def _blend(fg: RGB, bg: RGB, alpha: int) -> RGB:
    alpha = max(0, min(255, int(alpha)))
    if alpha == 255:
        return fg
    if alpha == 0:
        return bg
    inv = 255 - alpha
    return (
        (fg[0] * alpha + bg[0] * inv) // 255,
        (fg[1] * alpha + bg[1] * inv) // 255,
        (fg[2] * alpha + bg[2] * inv) // 255,
    )


def _as_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).strip()
    if not text:
        return default
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return default
    return int(float(match.group(0)))


def _parse_color(value: Any, default: RGB = DEFAULT_MUTED) -> RGB:
    if value is None or value == "":
        return default
    if isinstance(value, (tuple, list)) and len(value) >= 3:
        return (int(value[0]) & 0xFF, int(value[1]) & 0xFF, int(value[2]) & 0xFF)
    if isinstance(value, int):
        return ((value >> 16) & 0xFF, (value >> 8) & 0xFF, value & 0xFF)
    text = str(value).strip()
    lower = text.lower()
    names = {
        "black": (0, 0, 0),
        "white": (255, 255, 255),
        "red": (244, 67, 54),
        "green": (76, 175, 80),
        "blue": DEFAULT_PRIMARY,
        "gray": DEFAULT_MUTED,
        "grey": DEFAULT_MUTED,
        "transparent": default,
        "none": default,
    }
    if lower in names:
        return names[lower]
    if lower.startswith("lv_color_hex"):
        match = re.search(r"0x([0-9a-fA-F]{6})|([0-9a-fA-F]{6})", text)
        if match:
            text = match.group(1) or match.group(2)
    if lower.startswith("0x"):
        text = text[2:]
    if text.startswith("#"):
        text = text[1:]
    text = text.strip()
    if len(text) == 3 and all(ch in "0123456789abcdefABCDEF" for ch in text):
        return (int(text[0] * 2, 16), int(text[1] * 2, 16), int(text[2] * 2, 16))
    if len(text) >= 6 and all(ch in "0123456789abcdefABCDEF" for ch in text[:6]):
        return (int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16))
    return default


def _parse_opa(value: Any, default: int = 255) -> int:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return 255 if value else 0
    if isinstance(value, (int, float)):
        if isinstance(value, float) and 0 <= value <= 1:
            return int(float(value) * 255)
        return max(0, min(255, int(value)))
    text = str(value).strip().upper()
    if text in {"LV_OPA_TRANSP", "TRANSPARENT", "NONE"}:
        return 0
    if text in {"LV_OPA_COVER", "COVER", "OPAQUE"}:
        return 255
    if text.endswith("%"):
        return max(0, min(255, int(float(text[:-1]) * 2.55)))
    match = re.search(r"(\d+)", text)
    if not match:
        return default
    number = int(match.group(1))
    if "LV_OPA_" in text and number <= 100:
        return max(0, min(255, int(number * 2.55)))
    return max(0, min(255, number))


def _resolve_measure(value: Any, parent_size: int, default: int = 0) -> int:
    if value is None or value == "":
        return default
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).strip()
    pct = re.search(r"(?:LV_PCT|pct)?\(?\s*(-?\d+(?:\.\d+)?)\s*%?\)?", text, re.IGNORECASE)
    if text.endswith("%") or text.lower().startswith(("lv_pct", "pct(")):
        if pct:
            return int(parent_size * float(pct.group(1)) / 100)
    try:
        return int(float(text))
    except ValueError:
        return default


def _style(node: dict[str, Any]) -> dict[str, Any]:
    style: dict[str, Any] = {}
    for key in ("style", "styles", "computed_styles"):
        value = node.get(key)
        if isinstance(value, dict):
            style.update(value)
    for key in (
        "bg_color",
        "bg_opa",
        "color",
        "text_color",
        "text_opa",
        "font_size",
        "text_font_size",
        "radius",
        "border_color",
        "border_width",
        "border_opa",
        "indicator_color",
        "knob_color",
        "opa",
        "pad",
        "pad_all",
        "pad_top",
        "pad_bottom",
        "pad_left",
        "pad_right",
        "gap",
        "pad_gap",
        "text_align",
        "align",
    ):
        if key in node and key not in style:
            style[key] = node[key]
    return style


def _kind(node: dict[str, Any]) -> str:
    raw = str(node.get("type", node.get("class", "obj"))).lower()
    raw = raw.replace("lv_", "").replace("_t", "").replace("-", "_")
    if raw in {"btn", "button"}:
        return "button"
    if raw in {"label", "text"}:
        return "label"
    if raw in {"image", "img", "picture"}:
        return "image"
    if raw in {"container", "cont", "screen", "scr", "obj", "root"}:
        return "container"
    if raw in {"bar", "progress"}:
        return "bar"
    if raw in {"slider"}:
        return "slider"
    if raw in {"checkbox", "check_box"}:
        return "checkbox"
    return raw


def _children(node: dict[str, Any]) -> list[dict[str, Any]]:
    children = node.get("children", [])
    if isinstance(children, list):
        return [child for child in children if isinstance(child, dict)]
    return []


def _has_explicit_position(node: dict[str, Any]) -> bool:
    keys = {"x", "y", "left", "top", "abs_x", "abs_y", "absolute_x", "absolute_y", "rect", "bbox", "coords"}
    return any(key in node for key in keys)


def _rect_from_node(
    node: dict[str, Any],
    parent_x: int,
    parent_y: int,
    parent_w: int,
    parent_h: int,
    default_w: int,
    default_h: int,
) -> dict[str, int]:
    rect = node.get("rect") or node.get("coords") or node.get("bbox")
    if isinstance(rect, dict):
        x_value = rect.get("x", rect.get("left", node.get("x")))
        y_value = rect.get("y", rect.get("top", node.get("y")))
        w_value = rect.get("w", rect.get("width", node.get("w", node.get("width"))))
        h_value = rect.get("h", rect.get("height", node.get("h", node.get("height"))))
    elif isinstance(rect, list) and len(rect) >= 4:
        x_value, y_value, w_value, h_value = rect[:4]
    else:
        x_value = node.get("x", node.get("left"))
        y_value = node.get("y", node.get("top"))
        w_value = node.get("w", node.get("width"))
        h_value = node.get("h", node.get("height"))

    if "abs_x" in node or "absolute_x" in node:
        x = _resolve_measure(node.get("abs_x", node.get("absolute_x")), parent_w, parent_x)
    elif x_value is None:
        x = parent_x
    else:
        x = parent_x + _resolve_measure(x_value, parent_w, 0)

    if "abs_y" in node or "absolute_y" in node:
        y = _resolve_measure(node.get("abs_y", node.get("absolute_y")), parent_h, parent_y)
    elif y_value is None:
        y = parent_y
    else:
        y = parent_y + _resolve_measure(y_value, parent_h, 0)

    w = _resolve_measure(w_value, parent_w, default_w)
    h = _resolve_measure(h_value, parent_h, default_h)
    return {"x": x, "y": y, "w": max(1, w), "h": max(1, h)}


def _default_size(child: dict[str, Any], parent_w: int, parent_h: int) -> tuple[int, int]:
    kind = _kind(child)
    text = str(child.get("text", child.get("label", "")))
    if kind == "label":
        return (min(parent_w, max(40, len(text) * 7 + 8)), 24)
    if kind == "button":
        return (min(parent_w, max(76, len(text) * 8 + 28)), 40)
    if kind in {"bar", "slider"}:
        return (max(60, parent_w), 16)
    if kind == "checkbox":
        return (min(parent_w, max(72, len(text) * 7 + 28)), 24)
    if kind == "image":
        return (min(96, parent_w), min(96, parent_h))
    return (parent_w, 40)


def _layout_value(node: dict[str, Any], key: str, default: Any = None) -> Any:
    layout = node.get("layout")
    if isinstance(layout, dict) and key in layout:
        return layout[key]
    return node.get(key, default)


def _flow_direction(node: dict[str, Any]) -> str:
    value = _layout_value(node, "main_direction", _layout_value(node, "flex_direction", "column"))
    text = str(value).lower()
    if "row" in text:
        return "row"
    return "column"


def _place(value: Any, default: str = "start") -> str:
    text = str(value or default).lower()
    if "center" in text or "mid" in text:
        return "center"
    if "end" in text or "right" in text or "bottom" in text:
        return "end"
    if "space" in text and "between" in text:
        return "space_between"
    return "start"


def _pad_values(node: dict[str, Any]) -> tuple[int, int, int, int, int]:
    style = _style(node)
    pad = _as_int(style.get("pad", style.get("pad_all", node.get("pad_all"))), 0)
    top = _as_int(style.get("pad_top"), pad)
    bottom = _as_int(style.get("pad_bottom"), pad)
    left = _as_int(style.get("pad_left"), pad)
    right = _as_int(style.get("pad_right"), pad)
    gap = _as_int(style.get("gap", style.get("pad_gap", node.get("gap"))), 8)
    return top, right, bottom, left, gap


def _flex_rects(children: list[dict[str, Any]], x: int, y: int, w: int, h: int, parent: dict[str, Any]) -> list[dict[str, int]]:
    top, right, bottom, left, gap = _pad_values(parent)
    inner_x = x + left
    inner_y = y + top
    inner_w = max(1, w - left - right)
    inner_h = max(1, h - top - bottom)
    direction = _flow_direction(parent)
    main_place = _place(_layout_value(parent, "main_place", _layout_value(parent, "flex_main_place", "start")))
    cross_place = _place(_layout_value(parent, "cross_place", _layout_value(parent, "flex_cross_place", "start")))

    sizes: list[tuple[int, int]] = []
    for child in children:
        dw, dh = _default_size(child, inner_w, inner_h)
        sizes.append(
            (
                _resolve_measure(child.get("w", child.get("width")), inner_w, dw),
                _resolve_measure(child.get("h", child.get("height")), inner_h, dh),
            )
        )

    rects: list[dict[str, int]] = []
    if direction == "row":
        total = sum(size[0] for size in sizes)
        free = max(0, inner_w - total)
        actual_gap = gap
        if len(children) > 1 and main_place == "space_between":
            actual_gap = free // (len(children) - 1)
            start_x = inner_x
        elif main_place == "center":
            start_x = inner_x + max(0, (inner_w - total - gap * (len(children) - 1)) // 2)
        elif main_place == "end":
            start_x = inner_x + max(0, inner_w - total - gap * (len(children) - 1))
        else:
            start_x = inner_x
        cx = start_x
        for child, (cw, ch) in zip(children, sizes):
            if cross_place == "center":
                cy = inner_y + max(0, (inner_h - ch) // 2)
            elif cross_place == "end":
                cy = inner_y + max(0, inner_h - ch)
            else:
                cy = inner_y
            rects.append({"x": cx, "y": cy, "w": max(1, cw), "h": max(1, ch)})
            cx += cw + actual_gap
    else:
        total = sum(size[1] for size in sizes)
        free = max(0, inner_h - total)
        actual_gap = gap
        if len(children) > 1 and main_place == "space_between":
            actual_gap = free // (len(children) - 1)
            start_y = inner_y
        elif main_place == "center":
            start_y = inner_y + max(0, (inner_h - total - gap * (len(children) - 1)) // 2)
        elif main_place == "end":
            start_y = inner_y + max(0, inner_h - total - gap * (len(children) - 1))
        else:
            start_y = inner_y
        cy = start_y
        for child, (cw, ch) in zip(children, sizes):
            if cross_place == "center":
                cx = inner_x + max(0, (inner_w - cw) // 2)
            elif cross_place == "end":
                cx = inner_x + max(0, inner_w - cw)
            else:
                cx = inner_x
            rects.append({"x": cx, "y": cy, "w": max(1, cw), "h": max(1, ch)})
            cy += ch + actual_gap
    return rects


def _child_rects(node: dict[str, Any], children: list[dict[str, Any]], x: int, y: int, w: int, h: int) -> list[dict[str, int]]:
    flex = _flex_rects(children, x, y, w, h, node)
    rects: list[dict[str, int]] = []
    for child, default in zip(children, flex):
        if _has_explicit_position(child):
            rects.append(_rect_from_node(child, x, y, w, h, default["w"], default["h"]))
        else:
            rects.append(default)
    return rects


def _is_hidden(node: dict[str, Any]) -> bool:
    for key in ("hidden", "visible"):
        if key in node:
            value = node[key]
            if key == "hidden" and bool(value):
                return True
            if key == "visible" and value is False:
                return True
    flags = str(node.get("flags", "")).lower()
    return "hidden" in flags


def _font_scale(style: dict[str, Any]) -> int:
    size = _as_int(style.get("font_size", style.get("text_font_size")), 10)
    if size <= 12:
        return 1
    if size <= 22:
        return 2
    return 3


def _draw_background(canvas: Canvas, kind: str, style: dict[str, Any], x: int, y: int, w: int, h: int, depth: int) -> None:
    if kind == "label":
        default_opa = 0
    elif kind == "image":
        default_opa = 0
    elif depth == 0:
        default_opa = 255
    elif "bg_color" in style or "color" in style:
        default_opa = 255
    else:
        default_opa = 0
    bg = _parse_color(style.get("bg_color", style.get("color")), DEFAULT_BG if depth == 0 else (48, 54, 62))
    alpha = _parse_opa(style.get("bg_opa", style.get("opa")), default_opa)
    radius = _as_int(style.get("radius"), 0)
    if alpha > 0:
        canvas.fill_rounded_rect(x, y, w, h, radius, bg, alpha)
    border_width = _as_int(style.get("border_width"), 0)
    border_alpha = _parse_opa(style.get("border_opa"), 255)
    if border_width > 0 and border_alpha > 0:
        border = _parse_color(style.get("border_color"), (130, 144, 160))
        canvas.stroke_rect(x, y, w, h, border, border_width, border_alpha)


def _value_ratio(node: dict[str, Any]) -> float:
    value = float(_as_int(node.get("value", node.get("current_value", 0)), 0))
    min_value = float(_as_int(node.get("min", node.get("range_min", 0)), 0))
    max_value = float(_as_int(node.get("max", node.get("range_max", 100)), 100))
    if max_value <= min_value:
        return 0.0
    return max(0.0, min(1.0, (value - min_value) / (max_value - min_value)))


def _draw_bar(canvas: Canvas, node: dict[str, Any], style: dict[str, Any], x: int, y: int, w: int, h: int, *, slider: bool) -> None:
    radius = _as_int(style.get("radius"), max(1, h // 2))
    track = _parse_color(style.get("bg_color"), (68, 75, 86))
    fill = _parse_color(style.get("indicator_color", style.get("color")), DEFAULT_PRIMARY)
    canvas.fill_rounded_rect(x, y, w, h, radius, track, _parse_opa(style.get("bg_opa"), 255))
    ratio = _value_ratio(node)
    fill_w = max(0, min(w, int(w * ratio)))
    if fill_w > 0:
        canvas.fill_rounded_rect(x, y, fill_w, h, radius, fill, _parse_opa(style.get("indicator_opa"), 255))
    if slider:
        knob = _parse_color(style.get("knob_color"), DEFAULT_TEXT)
        knob_size = max(h + 4, 12)
        knob_x = x + fill_w - knob_size // 2
        knob_y = y + (h - knob_size) // 2
        canvas.fill_rounded_rect(knob_x, knob_y, knob_size, knob_size, knob_size // 2, knob, 255)


def _clean_src(value: Any) -> str:
    text = str(value or "").strip()
    if text.startswith("&"):
        text = text[1:]
    if text.startswith('"') and text.endswith('"'):
        text = text[1:-1]
    if text.startswith("S:"):
        text = text[2:]
    return text


def _draw_image(canvas: Canvas, node: dict[str, Any], style: dict[str, Any], x: int, y: int, w: int, h: int, base_dir: Path | None) -> None:
    src = _clean_src(node.get("src", node.get("image_src", node.get("source", ""))))
    path = Path(src) if src else None
    if path is not None and not path.is_absolute() and base_dir is not None:
        path = base_dir / path
    if path is not None and path.is_file() and path.suffix.lower() == ".png":
        try:
            src_w, src_h, pixels = read_png_rgba(path)
            canvas.blit_rgba(x, y, w, h, src_w, src_h, pixels)
            return
        except Exception:
            pass
    bg = _parse_color(style.get("bg_color"), (54, 61, 70))
    fg = _parse_color(style.get("text_color"), (172, 184, 198))
    canvas.fill_rounded_rect(x, y, w, h, _as_int(style.get("radius"), 4), bg, _parse_opa(style.get("bg_opa"), 190))
    canvas.stroke_rect(x, y, w, h, fg, 1, 180)
    canvas.draw_line(x, y, x + w - 1, y + h - 1, fg, 140)
    canvas.draw_line(x + w - 1, y, x, y + h - 1, fg, 140)
    canvas.draw_text_box(x, y, w, h, "IMG", fg, align="center", scale=1)


def _draw_checkbox(canvas: Canvas, node: dict[str, Any], style: dict[str, Any], x: int, y: int, w: int, h: int) -> None:
    box = min(h - 4, 18)
    box_x = x + 2
    box_y = y + max(0, (h - box) // 2)
    border = _parse_color(style.get("border_color"), DEFAULT_PRIMARY)
    canvas.stroke_rect(box_x, box_y, box, box, border, 1, 255)
    checked = bool(node.get("checked", node.get("value", False)))
    if checked:
        canvas.fill_rect(box_x + 3, box_y + 3, max(1, box - 6), max(1, box - 6), border, 255)
    text = str(node.get("text", node.get("label", "")))
    if text:
        canvas.draw_text_box(x + box + 6, y, max(1, w - box - 6), h, text, _parse_color(style.get("text_color"), DEFAULT_TEXT), valign="center")


def _draw_text_for_node(canvas: Canvas, node: dict[str, Any], kind: str, style: dict[str, Any], x: int, y: int, w: int, h: int) -> None:
    text = node.get("text", node.get("label"))
    if text is None:
        return
    scale = _font_scale(style)
    color = _parse_color(style.get("text_color"), DEFAULT_TEXT)
    alpha = _parse_opa(style.get("text_opa"), 255)
    if alpha < 255:
        color = _blend(color, DEFAULT_BG, alpha)
    align = _place(style.get("text_align", style.get("align", "center" if kind == "button" else "left")))
    if align == "end":
        align = "right"
    if kind == "button":
        valign = "center"
    else:
        valign = str(style.get("valign", "center")).lower()
    canvas.draw_text_box(x, y, w, h, str(text), color, align=align, valign=valign, scale=scale)


def _render_node(canvas: Canvas, node: dict[str, Any], x: int, y: int, w: int, h: int, *, depth: int = 0, base_dir: Path | None = None) -> None:
    if _is_hidden(node) or w <= 0 or h <= 0:
        return
    kind = _kind(node)
    style = _style(node)

    if kind in {"bar", "slider"}:
        _draw_bar(canvas, node, style, x, y, w, h, slider=kind == "slider")
    elif kind == "image":
        _draw_image(canvas, node, style, x, y, w, h, base_dir)
    elif kind == "checkbox":
        _draw_background(canvas, "label", style, x, y, w, h, depth)
        _draw_checkbox(canvas, node, style, x, y, w, h)
    else:
        _draw_background(canvas, kind, style, x, y, w, h, depth)
        _draw_text_for_node(canvas, node, kind, style, x, y, w, h)

    kids = _children(node)
    if not kids:
        return
    for child, rect in zip(kids, _child_rects(node, kids, x, y, w, h)):
        _render_node(canvas, child, rect["x"], rect["y"], rect["w"], rect["h"], depth=depth + 1, base_dir=base_dir)


def _display_size(tree_data: dict[str, Any], root: dict[str, Any], default_width: int, default_height: int) -> tuple[int, int]:
    display = tree_data.get("display", tree_data.get("screen", {}))
    width = _resolve_measure(display.get("width") if isinstance(display, dict) else None, default_width, default_width)
    height = _resolve_measure(display.get("height") if isinstance(display, dict) else None, default_height, default_height)
    width = _resolve_measure(root.get("w", root.get("width")), width, width)
    height = _resolve_measure(root.get("h", root.get("height")), height, height)
    return max(1, width), max(1, height)


def _root_from_tree(tree_data: dict[str, Any]) -> dict[str, Any]:
    root = tree_data.get("tree", tree_data.get("root"))
    if isinstance(root, dict):
        return root
    return tree_data


def render_tree_to_png(
    tree_data: dict[str, Any],
    output_dir: Path | str,
    filename: str = "preview.png",
    *,
    base_dir: Path | str | None = None,
    display_width: int = DEFAULT_WIDTH,
    display_height: int = DEFAULT_HEIGHT,
) -> Path:
    """Render object-tree JSON to a PNG file."""
    output_dir = Path(output_dir)
    root = _root_from_tree(tree_data)
    width, height = _display_size(tree_data, root, display_width, display_height)
    root_style = _style(root)
    bg = _parse_color(root_style.get("bg_color", root_style.get("color")), DEFAULT_BG)
    canvas = Canvas(width, height, bg)
    _render_node(canvas, root, 0, 0, width, height, depth=0, base_dir=Path(base_dir) if base_dir else None)
    png_path = output_dir / filename
    canvas.save_png(png_path)
    return png_path


def _theme_colors(spec: dict[str, Any]) -> dict[str, Any]:
    theme = spec.get("theme", {})
    if isinstance(theme, dict):
        colors = theme.get("colors", {})
        if isinstance(colors, dict):
            return colors
    return {}


def _component_to_node(component: dict[str, Any], colors: dict[str, Any]) -> dict[str, Any]:
    kind = _kind(component)
    style: dict[str, Any] = {}
    component_style = component.get("style")
    if isinstance(component_style, dict):
        style.update(component_style)
    for key in (
        "bg_color",
        "bg_opa",
        "color",
        "text_color",
        "font_size",
        "radius",
        "border_color",
        "border_width",
        "indicator_color",
        "knob_color",
        "pad",
        "pad_all",
        "pad_top",
        "pad_bottom",
        "pad_left",
        "pad_right",
        "gap",
        "text_align",
    ):
        if key in component:
            style[key] = component[key]

    if kind == "label":
        style.setdefault("bg_opa", 0)
        style.setdefault("text_color", component.get("color", colors.get("text", "#FFFFFF")))
    elif kind == "button":
        style.setdefault("bg_color", component.get("color", colors.get("primary", "#2196F3")))
        style.setdefault("text_color", "#FFFFFF")
        style.setdefault("radius", 8)
    elif kind in {"bar", "slider"}:
        style.setdefault("bg_color", component.get("track_color", "#444B56"))
        style.setdefault("indicator_color", component.get("color", colors.get("primary", "#2196F3")))
        style.setdefault("radius", 6)
    elif kind == "image":
        style.setdefault("bg_opa", 0)
    else:
        if "bg_color" not in style and "color" not in style:
            style.setdefault("bg_opa", 0)

    node: dict[str, Any] = {
        "id": component.get("id", component.get("name", "")),
        "type": component.get("type", "container"),
        "computed_styles": style,
    }
    for key in (
        "x",
        "y",
        "w",
        "h",
        "width",
        "height",
        "text",
        "label",
        "value",
        "min",
        "max",
        "src",
        "image_src",
        "checked",
        "layout",
        "flex_direction",
        "main_direction",
        "main_place",
        "cross_place",
        "gap",
        "pad",
        "pad_all",
    ):
        if key in component:
            node[key] = component[key]
    children = component.get("children", [])
    if isinstance(children, list):
        node["children"] = [_component_to_node(child, colors) for child in children if isinstance(child, dict)]
    else:
        node["children"] = []
    return node


def spec_to_tree(spec_data: dict[str, Any], *, display_width: int = DEFAULT_WIDTH, display_height: int = DEFAULT_HEIGHT) -> dict[str, Any]:
    """Convert a layout spec dict into the object-tree shape used by the renderer."""
    spec = spec_data.get("spec", spec_data)
    if not isinstance(spec, dict):
        raise ValueError("spec_data must be a dict or {'spec': dict}")
    display_cfg = spec.get("display_config", spec.get("display", {}))
    if not isinstance(display_cfg, dict):
        display_cfg = {}
    width = _resolve_measure(display_cfg.get("width"), display_width, display_width)
    height = _resolve_measure(display_cfg.get("height"), display_height, display_height)
    colors = _theme_colors(spec)
    components = spec.get("components", [])
    if not isinstance(components, list):
        components = []
    root_style = {
        "bg_color": colors.get("background", spec.get("background", "#20242A")),
        "bg_opa": 255,
        "pad_all": spec.get("pad", spec.get("pad_all", 0)),
    }
    if len(components) == 1 and _kind(components[0]) in {"container", "screen"}:
        root = _component_to_node(components[0], colors)
        root.setdefault("computed_styles", {}).setdefault("bg_color", root_style["bg_color"])
        root.setdefault("computed_styles", {}).setdefault("bg_opa", 255)
    else:
        root = {
            "id": spec.get("page_name", spec.get("name", "preview_root")),
            "type": "screen",
            "w": width,
            "h": height,
            "layout": {"main_direction": "column", "main_place": "start", "cross_place": "start"},
            "computed_styles": root_style,
            "children": [_component_to_node(component, colors) for component in components if isinstance(component, dict)],
        }
    root["w"] = _resolve_measure(root.get("w", root.get("width")), width, width)
    root["h"] = _resolve_measure(root.get("h", root.get("height")), height, height)
    return {"display": {"width": width, "height": height}, "tree": root}


def render_spec_to_png(
    spec_data: dict[str, Any],
    output_dir: Path | str,
    filename: str = "preview.png",
    *,
    display_width: int = DEFAULT_WIDTH,
    display_height: int = DEFAULT_HEIGHT,
    base_dir: Path | str | None = None,
) -> Path:
    """Render layout spec JSON to a PNG file."""
    tree = spec_to_tree(spec_data, display_width=display_width, display_height=display_height)
    return render_tree_to_png(
        tree,
        output_dir,
        filename,
        base_dir=base_dir,
        display_width=display_width,
        display_height=display_height,
    )


def write_object_tree(tree_data: dict[str, Any], output_dir: Path | str, filename: str = "object_tree.json") -> Path:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / filename
    path.write_text(json.dumps(tree_data, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
    return path


def _load_json(path: Path | str) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return data


def _assert_png_nonblank(path: Path) -> None:
    width, height, pixels = read_png(path)
    assert width > 0 and height > 0
    assert len(set(pixels)) > 2, "preview image is blank"


def _self_test() -> int:
    import tempfile

    tree = {
        "display": {"width": 240, "height": 320},
        "tree": {
            "type": "screen",
            "w": 240,
            "h": 320,
            "computed_styles": {"bg_color": "#20242A", "bg_opa": 255},
            "children": [
                {"type": "label", "x": 20, "y": 20, "w": 180, "h": 28, "text": "Hello LVGL", "computed_styles": {"text_color": "#FFFFFF"}},
                {"type": "button", "x": 30, "y": 72, "w": 170, "h": 46, "text": "START", "computed_styles": {"bg_color": "#2196F3", "radius": 8}},
                {"type": "bar", "x": 30, "y": 142, "w": 170, "h": 14, "value": 64, "computed_styles": {"indicator_color": "#FF9800"}},
                {"type": "slider", "x": 30, "y": 182, "w": 170, "h": 10, "value": 35},
            ],
        },
    }

    spec = {
        "spec": {
            "display_config": {"width": 320, "height": 240},
            "theme": {"colors": {"background": "#101820", "text": "#FFFFFF", "primary": "#2E7D32"}},
            "components": [
                {
                    "id": "root",
                    "type": "container",
                    "w": 320,
                    "h": 240,
                    "pad": 18,
                    "gap": 12,
                    "layout": {"main_direction": "column", "main_place": "start", "cross_place": "center"},
                    "children": [
                        {"id": "title", "type": "label", "text": "Preview"},
                        {"id": "go", "type": "button", "text": "RUN", "w": 120, "h": 38},
                        {"id": "progress", "type": "bar", "w": 180, "h": 12, "value": 72},
                    ],
                }
            ],
        }
    }

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        tree_png = render_tree_to_png(tree, out, "tree.png")
        _assert_png_nonblank(tree_png)
        spec_png = render_spec_to_png(spec, out, "spec.png")
        _assert_png_nonblank(spec_png)
        object_tree = spec_to_tree(spec)
        tree_path = write_object_tree(object_tree, out)
        assert tree_path.is_file()
        print(f"OK: tree render -> {tree_png.stat().st_size} bytes")
        print(f"OK: spec render -> {spec_png.stat().st_size} bytes")

    print("lvgl_preview self-test passed")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render LVGL layout spec/object-tree JSON to PNG using pure Python")
    parser.add_argument("--self-test", action="store_true", help="run renderer self-test")
    parser.add_argument("--tree", type=Path, help="object-tree JSON path")
    parser.add_argument("--spec", type=Path, help="layout spec JSON path")
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/lvgl_preview"))
    parser.add_argument("--filename", default="preview.png")
    parser.add_argument("--width", type=int, default=DEFAULT_WIDTH)
    parser.add_argument("--height", type=int, default=DEFAULT_HEIGHT)
    parser.add_argument("--base-dir", type=Path, help="base directory for relative PNG image sources")
    parser.add_argument("--write-object-tree", action="store_true", help="write normalized object_tree.json beside the PNG")
    args = parser.parse_args(argv)

    if args.self_test:
        return _self_test()
    if args.tree and args.spec:
        parser.error("--tree and --spec are mutually exclusive")

    if args.tree:
        tree = _load_json(args.tree)
        png = render_tree_to_png(tree, args.output_dir, args.filename, base_dir=args.base_dir or args.tree.parent, display_width=args.width, display_height=args.height)
        if args.write_object_tree:
            write_object_tree(tree, args.output_dir)
    elif args.spec:
        spec = _load_json(args.spec)
        tree = spec_to_tree(spec, display_width=args.width, display_height=args.height)
        png = render_tree_to_png(tree, args.output_dir, args.filename, base_dir=args.base_dir or args.spec.parent, display_width=args.width, display_height=args.height)
        if args.write_object_tree:
            write_object_tree(tree, args.output_dir)
    else:
        parser.error("provide --tree, --spec, or --self-test")

    print(str(png))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
