# LVGL UI TestKit

Compiles and executes generated LVGL page C code against a headless RGB565
framebuffer. Unlike the scene-protocol runner, this target calls the generated
page's real `create` and `destroy` functions.

Inputs are prepared by `tests/ui_testkit_prepare.py`. The output contains a
native PPM screenshot, binary object tree, and execution report. Python
post-processing converts these to PNG/JSON and applies the deterministic 90%
visual gate.

