# L3 LVGL Page Quick Workflow

Use this compact path for a small, confirmed LVGL page when the target
firmware project already has a working LVGL build and display driver.

1. Confirm display size, LVGL version, assets, fonts, and the visible page
   state.
2. Implement dynamic UI with LVGL widgets; retain image assets only where they
   materially improve visual fidelity.
3. Prefer Flex or Grid for repeated groups. Document any fixed-coordinate
   reconstruction beside the code.
4. Build and run the target project. Check the target display or simulator for
   clipping, font fallback, touch handling, and task-safety problems.

The quick path produces no repository-managed generator artifacts. It remains
the target project's responsibility to compile, render, and package the page.
