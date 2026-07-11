from pathlib import Path

import pytest

from mcp.design_asset_policy import POLICY_ID, assert_design_not_runtime
from mcp.interactive_scene_auto import _write_preview_crops, generate_interactive_scene_page


def test_design_reference_cannot_be_runtime_asset(tmp_path: Path) -> None:
    design = tmp_path / "design.png"
    design.write_bytes(b"reference")

    with pytest.raises(ValueError, match="cannot be used as a runtime asset"):
        assert_design_not_runtime(design, [design])


def test_design_crop_export_is_hard_disabled(tmp_path: Path) -> None:
    assert POLICY_ID == "design-reference-not-runtime-v1"
    assert _write_preview_crops(tmp_path, tmp_path / "design.png", {}, tmp_path / "assets") == {}


def test_interactive_page_rejects_design_as_background(tmp_path: Path) -> None:
    paths = {name: tmp_path / f"{name}.png" for name in ("design", "pet", "calmness", "good", "down", "stressed")}
    for path in paths.values():
        path.write_bytes(b"not-decoded-before-policy")

    with pytest.raises(ValueError, match="cannot be used as a runtime asset"):
        generate_interactive_scene_page({
            "design_path": str(paths["design"]),
            "background_path": str(paths["design"]),
            "pet_path": str(paths["pet"]),
            "mood_paths": {key: str(paths[key]) for key in ("calmness", "good", "down", "stressed")},
            "skip_preflight": True,
            "auto_analyze": False,
            "output_dir": str(tmp_path / "out"),
        })
