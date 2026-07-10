"""LVGL simulator, rendering, and regression helpers."""
from __future__ import annotations

try:
    from codegen import (
        build_lvgl_regression_sandbox,
        compare_lvgl_object_tree,
        compare_lvgl_screenshot,
        list_lvgl_regression_artifacts,
        lvgl_render,
        prepare_lvgl_regression_sandbox,
        prepare_lvgl_sim_project,
        run_lvgl_regression_sandbox,
        run_lvgl_ui_regression,
    )
except ImportError:  # pragma: no cover - package import fallback
    from .codegen import (
        build_lvgl_regression_sandbox,
        compare_lvgl_object_tree,
        compare_lvgl_screenshot,
        list_lvgl_regression_artifacts,
        lvgl_render,
        prepare_lvgl_regression_sandbox,
        prepare_lvgl_sim_project,
        run_lvgl_regression_sandbox,
        run_lvgl_ui_regression,
    )


__all__ = [
    "build_lvgl_regression_sandbox",
    "compare_lvgl_object_tree",
    "compare_lvgl_screenshot",
    "list_lvgl_regression_artifacts",
    "lvgl_render",
    "prepare_lvgl_regression_sandbox",
    "prepare_lvgl_sim_project",
    "run_lvgl_regression_sandbox",
    "run_lvgl_ui_regression",
]
