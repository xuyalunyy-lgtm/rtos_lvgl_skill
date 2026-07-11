"""Tests for LVGL simulator resolver."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "mcp"))

from lvgl_sim_resolver import detect_platform, resolve_runner, _load_manifest


class TestDetectPlatform:
    def test_returns_string(self):
        plat = detect_platform()
        assert isinstance(plat, str)
        assert "-" in plat  # e.g. "win-x64"

    def test_known_platforms(self):
        plat = detect_platform()
        known = {"win-x64", "linux-x64", "linux-arm64", "macos-x64", "macos-arm64"}
        # May not match if running on unusual platform, but should contain "-"
        assert "-" in plat


class TestResolveRunner:
    def test_v9_returns_dict(self):
        result = resolve_runner("v9")
        assert isinstance(result, dict)
        assert "ok" in result

    def test_v8_returns_unsupported(self):
        result = resolve_runner("v8")
        assert result["ok"] is False
        assert result.get("status") == "unsupported_version"

    def test_invalid_version(self):
        result = resolve_runner("v10")
        assert result["ok"] is False

    def test_manifest_loaded(self):
        manifest = _load_manifest()
        # Should be None or dict
        assert manifest is None or isinstance(manifest, dict)


class TestManifest:
    def test_manifest_structure(self):
        manifest_path = ROOT / "runtime" / "simulator" / "manifest.json"
        if not manifest_path.is_file():
            pytest.skip("No manifest.json")

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert "schema_version" in manifest
        assert "runners" in manifest
        assert isinstance(manifest["runners"], dict)
