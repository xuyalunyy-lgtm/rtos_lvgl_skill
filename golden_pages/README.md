# Golden Pages — LVGL Regression Evaluation Set

12 unique golden pages for testing the LVGL image-to-code pipeline.
Each page has a unique synthetic design image, metadata, and expected outputs.

## Pages

| Page | Description | Key Features |
|------|-------------|--------------|
| `loading_page` | Loading spinner with frosted glass circle | Status bar, text, circle overlay |
| `home_card_page` | Home with weather/schedule cards | Cards, text, navigation button |
| `media_page` | Media player with controls | Dark theme, progress bar, play buttons |
| `settings_page` | Settings with toggles | Toggle switches, labels, list layout |
| `list_page` | Scrollable message list | Avatar circles, contact names, previews |
| `dialog_page` | Confirmation dialog | Modal overlay, title, action buttons |
| `dashboard_page` | Dashboard with stats | Cards, bar chart, temperature/humidity |
| `sensor_page` | Sensor monitor (dark) | Real-time values, gauges, accelerometer |
| `ota_page` | OTA firmware update | Progress bar, version info, cancel button |
| `dark_theme_page` | Dark theme settings | Color swatches, brightness slider |
| `transparent_assets_page` | Gallery with alpha | Transparent cards, layered elements |
| `chinese_text_page` | Mixed CN/EN content | Network info, device info, status text |

## Structure

```
golden_pages/
├── README.md
├── loading_page/
│   ├── design.png          # Unique synthetic design image
│   ├── design_meta.json    # Screen params, description
│   └── expected/
│       ├── analysis_report.json
│       ├── generated.c
│       ├── object_tree.json
│       ├── render.png
│       ├── visual_diff.json
│       ├── cutout_audit.json
│       ├── diff_overlay.png
│       └── manifest.json
├── home_card_page/
│   └── ...
└── ... (12 pages total)
```

## Design Images

All `design.png` files are **synthetically generated** with unique visual content.
Each hash is verified unique — no two pages share the same design image.

```bash
# Verify uniqueness
cd golden_pages && for d in */; do d=${d%/}; echo "$d: $(sha256sum $d/design.png | cut -d' ' -f1)"; done
```

## Running Regression

```bash
# Check all golden page fixtures
python tools/run_lvgl_regression.py --all

# Check one golden page fixture
python tools/run_lvgl_regression.py --page golden_pages/loading_page

# JSON report
python tools/run_lvgl_regression.py --all --json

# List pages with unified status
python tools/run_lvgl_regression.py --list
```

## Regenerating

```bash
# Regenerate all design images
python scripts/generate_golden_designs.py

# Regenerate expected/ structure (preserves existing expected files)
python scripts/generate_golden_expected.py
```

## Status Definitions

| Status | Meaning |
|--------|---------|
| `regression_passed` | file_check, IR validation, cutout audit, and visual diff all passed |
| `regression_passed_with_warnings` | All stages passed, but at least one warning was emitted |
| `failed` | At least one validation or visual diff stage failed |
| `incomplete` | Required design or expected files are missing |

## Definition of Done

Each golden page must satisfy:
- [ ] Design image hash is unique (no duplicates)
- [ ] design_meta.json has correct screen params
- [ ] Expected generated.c compiles against target LVGL version
- [ ] Expected object_tree.json matches generated code structure
- [ ] Mutation test: moving a control causes failure
- [ ] Mutation test: deleting a resource causes failure
- [ ] Mutation test: changing text causes failure
