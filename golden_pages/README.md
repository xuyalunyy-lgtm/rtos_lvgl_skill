# Golden Page Regression Dataset

Fixed page samples for validating the design-to-LVGL pipeline.
Each change to generation logic must pass regression against these baselines.

## Structure

```
golden_pages/
  <page_name>/
    design.png                    # Input: design screenshot
    cutouts/                      # Input: cutout assets (bg.jpg, icon_*.png, etc.)
    design_meta.json              # Input: optional screen params / annotations
    expected/
      analysis_report.json        # Expected: layout tree + component evidence
      cutout_audit.json           # Expected: per-cutout status
      render.png                  # Expected: rendered LVGL output
      manifest.json               # Expected: asset manifest
      generated.c                 # Expected: generated C code
```

## Pages

| Page | Key Features | Status |
|------|-------------|--------|
| `loading_page` | Background, loading icon, glass/blur, status bar icons | ✅ regression_passed |
| `home_card_page` | Large background, cards, title/subtitle, icon buttons | ✅ regression_passed |
| `media_page` | Play button, progress bar, cover image, dynamic text | ✅ regression_passed |

## Status Definitions

| Status | Meaning |
|--------|---------|
| `regression_passed` | file_check, IR validation, cutout audit, and visual diff all passed |
| `regression_passed_with_warnings` | All stages passed, but at least one warning was emitted |
| `failed` | At least one validation or visual diff stage failed |
| `incomplete` | Required design or expected files are missing |

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

## Adding a New Golden Page

1. Create directory: `golden_pages/<name>/`
2. Add `design.png` and `cutouts/`
3. Run generation pipeline to produce expected artifacts
4. Verify `expected/render.png` matches design intent
5. Commit all files
