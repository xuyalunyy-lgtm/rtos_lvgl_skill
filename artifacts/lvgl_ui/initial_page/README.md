# Initial Page LVGL Module

LVGL page generated from two supplied cutouts:

- `ui/VidaWheel 硬件UI/Affirmation-bg.jpg`
- `ui/VidaWheel 硬件UI/宠物.png`

Visible runtime layers:

- Background: `UI_IMG_SRC_INITIAL_PAGE_BG`, default `S:/ui/initial_page_bg.jpg`, 480x800 at `(0,0)`.
- Pet: `UI_IMG_SRC_INITIAL_PAGE_PET`, default `S:/ui/initial_page_pet.png`, 305x428 at `(95,123)`.

Integration:

- Add `ui_initial_page.c` and `ui_initial_page.h` to the LVGL project.
- Copy `assets/initial_page_bg.jpg` and `assets/initial_page_pet.png` to the runtime image path or override the `UI_IMG_SRC_*` macros with your resource descriptors.
- The pet PNG requires alpha support. Keep PNG decoding enabled or provide an alpha-capable `lv_image_dsc_t`.
- Worker/network threads should call `ui_initial_page_post_server_update(payload)` instead of touching LVGL objects directly.

No runtime-drawn copy, labels, panels, or buttons are generated.
