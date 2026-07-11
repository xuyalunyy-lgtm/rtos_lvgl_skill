# Asset-pack contract

`asset.pack` is a read-only image bundle for `lvgl_sim_v9`. It keeps image
decoding out of the runner: Python converts PNG/JPEG input before rendering,
and the runner exposes each entry as an `lv_image_dsc_t`.

- Header: `APK\0`, version `1`, entry count, reserved (`16` bytes, little-endian).
- Entry: ASCII symbol (`1–31` bytes), data offset, RGB bytes, alpha bytes,
  width, height, format, reserved (`64` bytes, little-endian).
- Supported formats: `RGB565`, `RGB565A8`, `ARGB8888`, and `A8`.
- `RGB565A8` is a RGB565 pixel plane followed by an A8 alpha plane, matching
  LVGL v9's `LV_COLOR_FORMAT_RGB565A8`.

Create a pack with:

```text
python mcp/lvgl_ir/asset_pack.py --input assets/ --output artifacts/ui/assets.pack
```

The default `AUTO` format uses RGB565A8 when input has transparency and RGB565
otherwise. Transparent-border cropping is opt-in because it changes layout
geometry. An image UI node must use the exact pack symbol as its `src`, e.g.
`"src": "UI_IMG_LOGO"`.
