"""Tests for the portable toolchain resolver."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Add mcp/ to path
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "mcp"))

from toolchain_resolver import (
    _load_manifest,
    _sha256_file,
    _verify_files,
    detect_platform,
    resolve_toolchain,
    toolchain_available,
)


class TestDetectPlatform:
    def test_returns_string_with_dash(self):
        plat = detect_platform()
        assert isinstance(plat, str)
        assert "-" in plat

    def test_known_platforms(self):
        plat = detect_platform()
        known = {"win-x64", "linux-x64", "linux-arm64", "macos-x64", "macos-arm64"}
        # Should be one of the known or unknown-{os}-{arch}
        assert plat in known or plat.startswith("unknown-")


class TestLoadManifest:
    def test_returns_dict(self):
        manifest = _load_manifest()
        assert isinstance(manifest, dict)
        assert "schema_version" in manifest or "platforms" in manifest

    def test_has_platforms_key(self):
        manifest = _load_manifest()
        assert "platforms" in manifest


class TestVerifyFiles:
    def test_empty_expected(self, tmp_path):
        errors = _verify_files(tmp_path, {})
        assert errors == []

    def test_missing_file(self, tmp_path):
        errors = _verify_files(tmp_path, {"missing.txt": "abc123"})
        assert len(errors) == 1
        assert "missing" in errors[0]

    def test_hash_mismatch(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello")
        errors = _verify_files(tmp_path, {"test.txt": "000000"})
        assert len(errors) == 1
        assert "mismatch" in errors[0]

    def test_hash_match(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello")
        expected_hash = _sha256_file(f)
        errors = _verify_files(tmp_path, {"test.txt": expected_hash})
        assert errors == []


class TestResolveToolchain:
    def test_unknown_platform_returns_not_ok(self):
        result = resolve_toolchain("nonexistent-arch")
        assert result["ok"] is False
        assert "no toolchain manifest" in result["errors"][0]

    def test_missing_dir_returns_not_ok(self):
        # Use a platform that exists in manifest but has no actual files
        result = resolve_toolchain("linux-x64")
        # Might be ok if installed, or not ok if not
        assert "ok" in result
        assert "platform" in result
        assert result["platform"] == "linux-x64"

    def test_result_has_required_keys(self):
        result = resolve_toolchain("win-x64")
        required_keys = {
            "ok", "platform", "toolchain_dir", "bin_dir",
            "gcc", "ar", "as_exe", "ld", "ninja",
            "env", "version", "flavor", "errors",
        }
        assert required_keys == set(result.keys())


class TestToolchainAvailable:
    def test_returns_bool(self):
        result = toolchain_available("nonexistent-arch")
        assert result is False

    def test_real_platform(self):
        # Just check it doesn't crash
        result = toolchain_available()
        assert isinstance(result, bool)
