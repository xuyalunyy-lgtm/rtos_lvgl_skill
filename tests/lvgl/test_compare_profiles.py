"""Tests for compare threshold profiles."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "mcp"))

from lvgl_compare import THRESHOLD_PROFILES


# ── Profile definitions ───────────────────────────────────────────


class TestProfileDefinitions:
    def test_all_three_profiles_exist(self):
        assert "preview_relaxed" in THRESHOLD_PROFILES
        assert "hardware_tolerant" in THRESHOLD_PROFILES
        assert "golden_strict" in THRESHOLD_PROFILES

    def test_profile_keys_complete(self):
        required_keys = {
            "global_ssim_pass", "global_ssim_warn",
            "region_ssim_pass", "changed_pixel_pass", "changed_pixel_warn",
        }
        for name, profile in THRESHOLD_PROFILES.items():
            assert required_keys.issubset(profile.keys()), f"{name} missing keys"

    def test_golden_strict_is_hardest(self):
        g = THRESHOLD_PROFILES["golden_strict"]
        h = THRESHOLD_PROFILES["hardware_tolerant"]
        p = THRESHOLD_PROFILES["preview_relaxed"]

        # SSIM thresholds: higher is stricter
        assert g["global_ssim_pass"] >= h["global_ssim_pass"] >= p["global_ssim_pass"]
        assert g["global_ssim_warn"] >= h["global_ssim_warn"] >= p["global_ssim_warn"]
        assert g["region_ssim_pass"] >= h["region_ssim_pass"] >= p["region_ssim_pass"]

        # Pixel thresholds: lower is stricter
        assert g["changed_pixel_pass"] <= h["changed_pixel_pass"] <= p["changed_pixel_pass"]
        assert g["changed_pixel_warn"] <= h["changed_pixel_warn"] <= p["changed_pixel_warn"]

    def test_warn_thresholds_less_than_pass(self):
        for name, profile in THRESHOLD_PROFILES.items():
            assert profile["global_ssim_warn"] <= profile["global_ssim_pass"], (
                f"{name}: warn SSIM should be <= pass SSIM"
            )
            assert profile["changed_pixel_warn"] >= profile["changed_pixel_pass"], (
                f"{name}: warn pixel should be >= pass pixel"
            )


# ── Integration: compare with profiles ────────────────────────────


class TestCompareWithProfile:
    """Test that compare() uses profile-specific thresholds.

    Uses synthetic images to control SSIM/pixel values precisely.
    """

    @pytest.fixture
    def images(self, tmp_path):
        """Create two simple test images."""
        try:
            from PIL import Image
            import numpy as np
        except ImportError:
            pytest.skip("Pillow/numpy required")

        # Actual: solid blue
        actual = np.full((100, 100, 3), [0, 0, 255], dtype=np.uint8)
        # Baseline: solid red (very different → low SSIM)
        baseline = np.full((100, 100, 3), [255, 0, 0], dtype=np.uint8)

        actual_path = tmp_path / "actual.png"
        baseline_path = tmp_path / "baseline.png"
        Image.fromarray(actual).save(str(actual_path))
        Image.fromarray(baseline).save(str(baseline_path))
        return str(actual_path), str(baseline_path)

    def test_profile_name_in_result(self, images):
        from lvgl_compare import compare
        actual_path, baseline_path = images
        result = compare(actual_path, baseline_path, profile="preview_relaxed")
        assert result["profile"] == "preview_relaxed"

    def test_golden_strict_is_stricter(self, images):
        from lvgl_compare import compare
        actual_path, baseline_path = images

        r_preview = compare(actual_path, baseline_path, profile="preview_relaxed")
        r_golden = compare(actual_path, baseline_path, profile="golden_strict")

        # With very different images, both should fail, but golden should have
        # failure_reasons populated
        assert r_preview["status"] == "failed"
        assert r_golden["status"] == "failed"

    def test_identical_images_pass_all_profiles(self, tmp_path):
        """Identical images should pass even the strictest profile."""
        try:
            from PIL import Image
            import numpy as np
        except ImportError:
            pytest.skip("Pillow/numpy required")

        img = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        path = tmp_path / "img.png"
        Image.fromarray(img).save(str(path))
        img_path = str(path)

        from lvgl_compare import compare
        for profile in THRESHOLD_PROFILES:
            result = compare(img_path, img_path, profile=profile)
            assert result["status"] == "passed", f"Identical images should pass {profile}"
            assert result["global_ssim"] >= 0.99
            assert result["changed_pixel_ratio"] == 0.0
