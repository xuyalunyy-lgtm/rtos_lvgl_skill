#!/usr/bin/env python3
"""Generate synthetic design images for golden page evaluation set.

Each image is visually distinct and represents a different page type.
Used for LVGL regression testing — not real designs, but structurally valid.

Usage:
    python scripts/generate_golden_designs.py
    python scripts/generate_golden_designs.py --output-dir golden_pages
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("Pillow not installed. Run: pip install Pillow")
    raise SystemExit(1)

ROOT = Path(__file__).resolve().parent.parent

# ── Page definitions ──────────────────────────────────────────────

PAGES = [
    {
        "name": "loading_page",
        "description": "Loading page with frosted glass circle, loading text, and status bar",
        "bg_color": (245, 245, 250),
        "elements": [
            {"type": "rect", "pos": (0, 0, 480, 40), "fill": (50, 50, 60), "text": "12:30", "text_color": (255, 255, 255), "text_pos": (220, 10)},
            {"type": "circle", "pos": (190, 250, 290, 350), "fill": (200, 210, 230, 180), "outline": (180, 190, 210)},
            {"type": "text", "pos": (180, 380), "text": "Loading...", "color": (80, 80, 100), "size": 24},
            {"type": "text", "pos": (160, 420), "text": "Please wait", "color": (150, 150, 160), "size": 16},
        ],
    },
    {
        "name": "home_card_page",
        "description": "Home page with weather card, schedule card, and navigation",
        "bg_color": (240, 243, 247),
        "elements": [
            {"type": "rect", "pos": (0, 0, 480, 40), "fill": (33, 150, 243), "text": "Home", "text_color": (255, 255, 255), "text_pos": (210, 10)},
            {"type": "rect", "pos": (20, 60, 460, 180), "fill": (255, 255, 255), "outline": (220, 220, 220), "radius": 12},
            {"type": "text", "pos": (40, 80), "text": "Weather: Sunny 28°C", "color": (50, 50, 60), "size": 20},
            {"type": "text", "pos": (40, 120), "text": "Humidity: 45%", "color": (120, 120, 130), "size": 14},
            {"type": "rect", "pos": (20, 200, 460, 350), "fill": (255, 255, 255), "outline": (220, 220, 220), "radius": 12},
            {"type": "text", "pos": (40, 220), "text": "Today's Schedule", "color": (50, 50, 60), "size": 18},
            {"type": "text", "pos": (40, 260), "text": "09:00 - Team Meeting", "color": (80, 80, 100), "size": 14},
            {"type": "text", "pos": (40, 290), "text": "14:00 - Code Review", "color": (80, 80, 100), "size": 14},
            {"type": "rect", "pos": (160, 700, 320, 760), "fill": (33, 150, 243), "radius": 24, "text": "Navigate", "text_color": (255, 255, 255), "text_pos": (195, 725)},
        ],
    },
    {
        "name": "media_page",
        "description": "Media player with cover art, progress bar, play controls",
        "bg_color": (30, 30, 40),
        "elements": [
            {"type": "rect", "pos": (0, 0, 480, 40), "fill": (20, 20, 30), "text": "Now Playing", "text_color": (200, 200, 210), "text_pos": (190, 10)},
            {"type": "rect", "pos": (90, 80, 390, 380), "fill": (60, 60, 80), "radius": 16},
            {"type": "text", "pos": (150, 400), "text": "Song Title - Artist", "color": (230, 230, 240), "size": 20},
            {"type": "rect", "pos": (40, 460, 440, 470), "fill": (80, 80, 100), "radius": 4},
            {"type": "rect", "pos": (40, 460, 240, 470), "fill": (33, 150, 243), "radius": 4},
            {"type": "text", "pos": (30, 480), "text": "1:23", "color": (150, 150, 160), "size": 12},
            {"type": "text", "pos": (410, 480), "text": "3:45", "color": (150, 150, 160), "size": 12},
            {"type": "circle", "pos": (200, 530, 280, 610), "fill": (33, 150, 243), "text": "▶", "text_color": (255, 255, 255), "text_pos": (228, 555)},
            {"type": "circle", "pos": (100, 545, 160, 605), "fill": (60, 60, 80), "text": "⏮", "text_color": (200, 200, 210), "text_pos": (118, 562)},
            {"type": "circle", "pos": (320, 545, 380, 605), "fill": (60, 60, 80), "text": "⏭", "text_color": (200, 200, 210), "text_pos": (338, 562)},
        ],
    },
    {
        "name": "settings_page",
        "description": "Settings page with toggle switches and labels",
        "bg_color": (245, 245, 250),
        "elements": [
            {"type": "rect", "pos": (0, 0, 480, 50), "fill": (33, 150, 243), "text": "Settings", "text_color": (255, 255, 255), "text_pos": (200, 15)},
            {"type": "rect", "pos": (0, 60, 480, 110), "fill": (255, 255, 255)},
            {"type": "text", "pos": (20, 75), "text": "Wi-Fi", "color": (50, 50, 60), "size": 18},
            {"type": "rect", "pos": (400, 70, 450, 100), "fill": (76, 175, 80), "radius": 15},
            {"type": "rect", "pos": (0, 120, 480, 170), "fill": (255, 255, 255)},
            {"type": "text", "pos": (20, 135), "text": "Bluetooth", "color": (50, 50, 60), "size": 18},
            {"type": "rect", "pos": (400, 130, 450, 160), "fill": (200, 200, 200), "radius": 15},
            {"type": "rect", "pos": (0, 180, 480, 230), "fill": (255, 255, 255)},
            {"type": "text", "pos": (20, 195), "text": "Notifications", "color": (50, 50, 60), "size": 18},
            {"type": "rect", "pos": (400, 190, 450, 220), "fill": (76, 175, 80), "radius": 15},
            {"type": "rect", "pos": (0, 240, 480, 290), "fill": (255, 255, 255)},
            {"type": "text", "pos": (20, 255), "text": "Dark Mode", "color": (50, 50, 60), "size": 18},
            {"type": "rect", "pos": (400, 250, 450, 280), "fill": (200, 200, 200), "radius": 15},
        ],
    },
    {
        "name": "list_page",
        "description": "List page with scrollable items and icons",
        "bg_color": (245, 245, 250),
        "elements": [
            {"type": "rect", "pos": (0, 0, 480, 50), "fill": (33, 150, 243), "text": "Messages", "text_color": (255, 255, 255), "text_pos": (195, 15)},
        ] + [
            {"type": "rect", "pos": (0, 60 + i * 70, 480, 120 + i * 70), "fill": (255, 255, 255)} for i in range(5)
        ] + [
            {"type": "circle", "pos": (20, 70 + i * 70, 60, 110 + i * 70), "fill": (33, 150, 243)} for i in range(5)
        ] + [
            {"type": "text", "pos": (80, 75 + i * 70), "text": f"Contact {i+1}", "color": (50, 50, 60), "size": 16} for i in range(5)
        ] + [
            {"type": "text", "pos": (80, 100 + i * 70), "text": f"Last message preview {i+1}...", "color": (150, 150, 160), "size": 12} for i in range(5)
        ],
    },
    {
        "name": "dialog_page",
        "description": "Dialog/modal with title, message, and action buttons",
        "bg_color": (200, 200, 210),
        "elements": [
            {"type": "rect", "pos": (40, 250, 440, 550), "fill": (255, 255, 255), "radius": 16},
            {"type": "text", "pos": (180, 280), "text": "Confirm Delete?", "color": (50, 50, 60), "size": 22},
            {"type": "text", "pos": (80, 330), "text": "This action cannot be undone.", "color": (120, 120, 130), "size": 16},
            {"type": "text", "pos": (80, 370), "text": "All data will be permanently removed.", "color": (120, 120, 130), "size": 14},
            {"type": "rect", "pos": (60, 470, 220, 520), "fill": (244, 67, 54), "radius": 8, "text": "Delete", "text_color": (255, 255, 255), "text_pos": (115, 488)},
            {"type": "rect", "pos": (260, 470, 420, 520), "fill": (200, 200, 210), "radius": 8, "text": "Cancel", "text_color": (80, 80, 100), "text_pos": (315, 488)},
        ],
    },
    {
        "name": "dashboard_page",
        "description": "Dashboard with stats cards and charts placeholder",
        "bg_color": (235, 238, 242),
        "elements": [
            {"type": "rect", "pos": (0, 0, 480, 50), "fill": (33, 150, 243), "text": "Dashboard", "text_color": (255, 255, 255), "text_pos": (195, 15)},
            {"type": "rect", "pos": (15, 65, 230, 175), "fill": (255, 255, 255), "radius": 12},
            {"type": "text", "pos": (30, 80), "text": "Temperature", "color": (120, 120, 130), "size": 14},
            {"type": "text", "pos": (30, 110), "text": "24.5°C", "color": (50, 50, 60), "size": 28},
            {"type": "rect", "pos": (250, 65, 465, 175), "fill": (255, 255, 255), "radius": 12},
            {"type": "text", "pos": (265, 80), "text": "Humidity", "color": (120, 120, 130), "size": 14},
            {"type": "text", "pos": (265, 110), "text": "62%", "color": (50, 50, 60), "size": 28},
            {"type": "rect", "pos": (15, 195, 465, 450), "fill": (255, 255, 255), "radius": 12},
            {"type": "text", "pos": (30, 210), "text": "Weekly Trend", "color": (50, 50, 60), "size": 16},
            {"type": "rect", "pos": (30, 250, 80, 400), "fill": (33, 150, 243), "radius": 4},
            {"type": "rect", "pos": (100, 280, 150, 400), "fill": (33, 150, 243), "radius": 4},
            {"type": "rect", "pos": (170, 260, 220, 400), "fill": (33, 150, 243), "radius": 4},
            {"type": "rect", "pos": (240, 300, 290, 400), "fill": (33, 150, 243), "radius": 4},
            {"type": "rect", "pos": (310, 270, 360, 400), "fill": (33, 150, 243), "radius": 4},
            {"type": "rect", "pos": (380, 240, 430, 400), "fill": (33, 150, 243), "radius": 4},
        ],
    },
    {
        "name": "sensor_page",
        "description": "Sensor data display with real-time values and gauges",
        "bg_color": (20, 25, 35),
        "elements": [
            {"type": "rect", "pos": (0, 0, 480, 50), "fill": (15, 20, 30), "text": "Sensor Monitor", "text_color": (100, 200, 255), "text_pos": (175, 15)},
            {"type": "rect", "pos": (15, 65, 230, 200), "fill": (30, 35, 50), "radius": 12},
            {"type": "text", "pos": (30, 80), "text": "Temperature", "color": (100, 200, 255), "size": 14},
            {"type": "text", "pos": (30, 120), "text": "23.7°C", "color": (0, 255, 150), "size": 32},
            {"type": "rect", "pos": (250, 65, 465, 200), "fill": (30, 35, 50), "radius": 12},
            {"type": "text", "pos": (265, 80), "text": "Pressure", "color": (100, 200, 255), "size": 14},
            {"type": "text", "pos": (265, 120), "text": "1013 hPa", "color": (255, 200, 50), "size": 28},
            {"type": "rect", "pos": (15, 220, 465, 500), "fill": (30, 35, 50), "radius": 12},
            {"type": "text", "pos": (30, 235), "text": "Accelerometer", "color": (100, 200, 255), "size": 14},
            {"type": "text", "pos": (30, 280), "text": "X: 0.12  Y: -0.03  Z: 9.81", "color": (200, 200, 210), "size": 16},
        ],
    },
    {
        "name": "ota_page",
        "description": "OTA update page with progress bar and status",
        "bg_color": (245, 245, 250),
        "elements": [
            {"type": "rect", "pos": (0, 0, 480, 50), "fill": (33, 150, 243), "text": "Firmware Update", "text_color": (255, 255, 255), "text_pos": (175, 15)},
            {"type": "rect", "pos": (40, 100, 440, 200), "fill": (255, 255, 255), "outline": (220, 220, 220), "radius": 12},
            {"type": "text", "pos": (60, 120), "text": "Current Version: v2.1.0", "color": (80, 80, 100), "size": 16},
            {"type": "text", "pos": (60, 155), "text": "Available: v2.2.0", "color": (33, 150, 243), "size": 18},
            {"type": "text", "pos": (60, 185), "text": "Size: 1.2 MB", "color": (150, 150, 160), "size": 14},
            {"type": "rect", "pos": (40, 250, 440, 290), "fill": (230, 230, 235), "radius": 8},
            {"type": "rect", "pos": (40, 250, 280, 290), "fill": (33, 150, 243), "radius": 8},
            {"type": "text", "pos": (200, 262), "text": "65%", "color": (255, 255, 255), "size": 16},
            {"type": "text", "pos": (180, 310), "text": "Downloading...", "color": (80, 80, 100), "size": 16},
            {"type": "rect", "pos": (140, 400, 340, 450), "fill": (244, 67, 54), "radius": 8, "text": "Cancel Update", "text_color": (255, 255, 255), "text_pos": (165, 418)},
        ],
    },
    {
        "name": "dark_theme_page",
        "description": "Dark theme settings page with contrast elements",
        "bg_color": (18, 18, 24),
        "elements": [
            {"type": "rect", "pos": (0, 0, 480, 50), "fill": (10, 10, 15), "text": "Dark Theme", "text_color": (200, 200, 210), "text_pos": (190, 15)},
            {"type": "rect", "pos": (15, 65, 465, 160), "fill": (30, 30, 40), "radius": 12},
            {"type": "text", "pos": (30, 80), "text": "Accent Color", "color": (200, 200, 210), "size": 16},
            {"type": "circle", "pos": (30, 110, 70, 150), "fill": (33, 150, 243)},
            {"type": "circle", "pos": (85, 110, 125, 150), "fill": (76, 175, 80)},
            {"type": "circle", "pos": (140, 110, 180, 150), "fill": (255, 152, 0)},
            {"type": "circle", "pos": (195, 110, 235, 150), "fill": (244, 67, 54)},
            {"type": "rect", "pos": (15, 180, 465, 270), "fill": (30, 30, 40), "radius": 12},
            {"type": "text", "pos": (30, 195), "text": "Brightness", "color": (200, 200, 210), "size": 16},
            {"type": "rect", "pos": (30, 230, 430, 245), "fill": (50, 50, 65), "radius": 7},
            {"type": "rect", "pos": (30, 230, 280, 245), "fill": (33, 150, 243), "radius": 7},
        ],
    },
    {
        "name": "transparent_assets_page",
        "description": "Page with transparent/alpha assets and layered elements",
        "bg_color": (100, 180, 240),
        "elements": [
            {"type": "rect", "pos": (0, 0, 480, 50), "fill": (50, 130, 200), "text": "Gallery", "text_color": (255, 255, 255), "text_pos": (210, 15)},
            {"type": "rect", "pos": (20, 70, 230, 280), "fill": (255, 255, 255, 200), "radius": 12},
            {"type": "rect", "pos": (250, 70, 460, 280), "fill": (255, 255, 255, 200), "radius": 12},
            {"type": "rect", "pos": (20, 300, 230, 510), "fill": (255, 255, 255, 200), "radius": 12},
            {"type": "rect", "pos": (250, 300, 460, 510), "fill": (255, 255, 255, 200), "radius": 12},
            {"type": "text", "pos": (60, 250), "text": "Photo 1", "color": (50, 50, 60), "size": 14},
            {"type": "text", "pos": (290, 250), "text": "Photo 2", "color": (50, 50, 60), "size": 14},
            {"type": "text", "pos": (60, 480), "text": "Photo 3", "color": (50, 50, 60), "size": 14},
            {"type": "text", "pos": (290, 480), "text": "Photo 4", "color": (50, 50, 60), "size": 14},
        ],
    },
    {
        "name": "chinese_text_page",
        "description": "Chinese text page with mixed CN/EN content",
        "bg_color": (245, 245, 250),
        "elements": [
            {"type": "rect", "pos": (0, 0, 480, 50), "fill": (33, 150, 243), "text": "Settings", "text_color": (255, 255, 255), "text_pos": (200, 15)},
            {"type": "rect", "pos": (15, 65, 465, 160), "fill": (255, 255, 255), "radius": 12},
            {"type": "text", "pos": (30, 80), "text": "Network Settings", "color": (50, 50, 60), "size": 18},
            {"type": "text", "pos": (30, 115), "text": "WiFi: Connected", "color": (80, 80, 100), "size": 14},
            {"type": "text", "pos": (30, 140), "text": "IP: 192.168.1.100", "color": (150, 150, 160), "size": 12},
            {"type": "rect", "pos": (15, 180, 465, 320), "fill": (255, 255, 255), "radius": 12},
            {"type": "text", "pos": (30, 195), "text": "Device Info", "color": (50, 50, 60), "size": 18},
            {"type": "text", "pos": (30, 230), "text": "Model: Smart Display v2", "color": (80, 80, 100), "size": 14},
            {"type": "text", "pos": (30, 260), "text": "Firmware: v2.2.0", "color": (80, 80, 100), "size": 14},
            {"type": "text", "pos": (30, 290), "text": "Serial: SN-2026-001", "color": (150, 150, 160), "size": 12},
        ],
    },
]


def draw_rounded_rect(draw: ImageDraw.Draw, bbox: tuple, radius: int, fill=None, outline=None):
    """Draw a rounded rectangle."""
    x0, y0, x1, y1 = bbox
    draw.rounded_rectangle(bbox, radius=radius, fill=fill, outline=outline)


def generate_page_image(page: dict, width: int = 480, height: int = 800) -> Image.Image:
    """Generate a synthetic design image for a golden page."""
    bg = page.get("bg_color", (245, 245, 250))
    if len(bg) == 3:
        img = Image.new("RGB", (width, height), bg)
    else:
        img = Image.new("RGBA", (width, height), bg)
    draw = ImageDraw.Draw(img)

    for elem in page.get("elements", []):
        etype = elem["type"]
        pos = elem["pos"]
        fill = elem.get("fill")
        outline = elem.get("outline")

        if etype == "rect":
            radius = elem.get("radius", 0)
            if radius > 0:
                draw_rounded_rect(draw, pos, radius, fill=fill, outline=outline)
            else:
                draw.rectangle(pos, fill=fill, outline=outline)
            # Draw text if present
            if "text" in elem:
                text_pos = elem.get("text_pos", (pos[0] + 10, pos[1] + 10))
                text_color = elem.get("text_color", (0, 0, 0))
                size = elem.get("text_size", 16)
                try:
                    font = ImageFont.truetype("arial.ttf", size)
                except (OSError, IOError):
                    font = ImageFont.load_default()
                draw.text(text_pos, elem["text"], fill=text_color, font=font)

        elif etype == "circle":
            draw.ellipse(pos, fill=fill, outline=outline)
            if "text" in elem:
                text_pos = elem.get("text_pos", (pos[0] + 10, pos[1] + 10))
                text_color = elem.get("text_color", (0, 0, 0))
                size = elem.get("text_size", 16)
                try:
                    font = ImageFont.truetype("arial.ttf", size)
                except (OSError, IOError):
                    font = ImageFont.load_default()
                draw.text(text_pos, elem["text"], fill=text_color, font=font)

        elif etype == "text":
            color = elem.get("color", (0, 0, 0))
            size = elem.get("size", 16)
            try:
                font = ImageFont.truetype("arial.ttf", size)
            except (OSError, IOError):
                font = ImageFont.load_default()
            draw.text(pos, elem["text"], fill=color, font=font)

    return img


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default=str(ROOT / "golden_pages"), help="Output directory")
    parser.add_argument("--width", type=int, default=480)
    parser.add_argument("--height", type=int, default=800)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for page in PAGES:
        page_dir = output_dir / page["name"]
        page_dir.mkdir(parents=True, exist_ok=True)

        # Generate design image
        img = generate_page_image(page, args.width, args.height)
        design_path = page_dir / "design.png"
        img.save(str(design_path))
        print(f"[OK] {page['name']}/design.png ({img.size})")

        # Generate design_meta.json
        meta = {
            "page_name": page["name"],
            "screen": {
                "width": args.width,
                "height": args.height,
                "lvgl_version": "v9",
                "color_depth": 16,
            },
            "description": page["description"],
        }
        meta_path = page_dir / "design_meta.json"
        meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[OK] {page['name']}/design_meta.json")

    print(f"\nGenerated {len(PAGES)} golden page designs in {output_dir}")


if __name__ == "__main__":
    main()
