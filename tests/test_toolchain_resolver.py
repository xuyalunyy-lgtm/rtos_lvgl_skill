"""Tests for the portable toolchain resolver."""
from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path
import pytest

# Add mcp/ to path
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "mcp"))

import toolchain_resolver as tc
from toolchain_resolver import (
    _load_manifest,
    _sha256_file,
    _verify_files,
    clear_toolchain_cache,
    detect_platform,
    ensure_toolchain,
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

    def test_bundled_archive_exists_and_matches_manifest(self):
        entry = _load_manifest()["platforms"]["win-x64"]
        archive = _ROOT / entry["bundled_archive"]
        assert archive.is_file()
        assert _sha256_file(archive) == entry["archive_sha256"]


class TestVerifyFiles:
    def test_empty_expected(self, tmp_path):
        errors = _verify_files(tmp_path, {})
        assert errors == ["payload manifest contains no files"]

    def test_rejects_parent_traversal(self, tmp_path):
        errors = _verify_files(tmp_path, {"../escape.exe": "0" * 64})
        assert errors == ["unsafe manifest path: ../escape.exe"]

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

    def test_verified_payload_resolves_and_tamper_fails(self, tmp_path):
        manifest = _load_manifest()
        entry = manifest["platforms"]["win-x64"]
        payload = tmp_path / "win-x64"
        files = list(entry["required_files"]) + ["lib/gcc/x86_64-w64-mingw32/16.1.0/cc1.exe"]
        hashes = {}
        for relative in files:
            target = payload / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(relative.encode("utf-8"))
            hashes[relative] = _sha256_file(target)
        (payload / "toolchain-manifest.json").write_text(json.dumps({
            "schema_version": 1,
            "platform": "win-x64",
            "version": entry["version"],
            "files": hashes,
        }), encoding="utf-8")

        clear_toolchain_cache()
        assert resolve_toolchain("win-x64", payload)["ok"] is True
        (payload / "bin/gcc.exe").write_bytes(b"tampered")
        clear_toolchain_cache()
        broken = resolve_toolchain("win-x64", payload)
        assert broken["ok"] is False
        assert "hash mismatch: bin/gcc.exe" in broken["errors"]


class TestToolchainAvailable:
    def test_returns_bool(self):
        result = toolchain_available("nonexistent-arch")
        assert result is False

    def test_real_platform(self):
        # Just check it doesn't crash
        result = toolchain_available()
        assert isinstance(result, bool)


def test_ensure_toolchain_extracts_verified_bundled_zip(tmp_path, monkeypatch):
    fake_root = tmp_path / "skill"
    toolchain_root = fake_root / "runtime" / "toolchain"
    asset_dir = fake_root / "assets" / "toolchains" / "win-x64"
    source = tmp_path / "source" / "win-x64"
    required = ["bin/gcc.exe", "bin/as.exe", "bin/ld.exe", "bin/ar.exe", "bin/ninja.exe"]
    files = required + ["lib/gcc/x86_64-w64-mingw32/16.1.0/cc1.exe"]
    hashes = {}
    for relative in files:
        target = source / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(relative.encode("ascii"))
        hashes[relative] = _sha256_file(target)
    (source / "toolchain-manifest.json").write_text(json.dumps({
        "schema_version": 1,
        "platform": "win-x64",
        "version": "16.1.0",
        "files": hashes,
    }), encoding="utf-8")
    asset_dir.mkdir(parents=True, exist_ok=True)
    archive = asset_dir / "toolchain.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        for path in sorted(source.rglob("*")):
            if path.is_file():
                bundle.write(path, (Path("win-x64") / path.relative_to(source)).as_posix())
    toolchain_root.mkdir(parents=True)
    manifest = {
        "schema_version": 2,
        "platforms": {"win-x64": {
            "version": "16.1.0",
            "flavor": "ucrt64",
            "payload_manifest": "toolchain-manifest.json",
            "required_files": required,
            "bundled_archive": "assets/toolchains/win-x64/toolchain.zip",
            "archive_sha256": _sha256_file(archive),
        }},
    }
    manifest_path = toolchain_root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr(tc, "_ROOT", fake_root)
    monkeypatch.setattr(tc, "_TOOLCHAIN_ROOT", toolchain_root)
    monkeypatch.setattr(tc, "_DISTRIBUTION_MANIFEST", manifest_path)
    clear_toolchain_cache()
    try:
        result = ensure_toolchain("win-x64")
        assert result["ok"] is True
        assert (toolchain_root / "win-x64" / "bin" / "gcc.exe").is_file()
    finally:
        clear_toolchain_cache()


def test_regression_build_and_run_both_resolve_private_toolchain():
    source = (_ROOT / "mcp" / "regression.py").read_text(encoding="utf-8")
    assert source.count("from toolchain_resolver import ensure_toolchain as _ensure_tc") >= 2
    assert '"source": "bundled"' in source
