"""OTA firmware repository management.

Manages a local firmware repository with upload, delete, list, and SHA256 verification.

Repository structure:
    artifacts/firmware/{platform}/{version}/firmware.bin
    artifacts/firmware/{platform}/{version}/manifest.json
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import time
from pathlib import Path
from typing import Any

try:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
except ImportError:  # pragma: no cover - handled as a clear runtime error
    InvalidSignature = Exception
    serialization = None
    Ed25519PublicKey = Any

SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")
MAX_FIRMWARE_SIZE = 16 * 1024 * 1024  # 16MB


def sha256_file(path: Path) -> str:
    """Compute SHA256 hex digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


class FirmwareRepo:
    """Local firmware repository manager."""

    def __init__(self, root: Path, trusted_keys: dict[str, str] | None = None):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._trusted_keys = trusted_keys or {}

    def upload(
        self,
        platform: str,
        version: str,
        file_path: Path,
        description: str = "",
        signature_path: Path | None = None,
        key_id: str | None = None,
    ) -> dict[str, Any]:
        """Upload firmware to repository.

        Args:
            platform: Target platform (esp32, stm32, jl, bk, zephyr)
            version: Semantic version string (x.y.z)
            file_path: Path to firmware binary
            description: Optional description

        Returns:
            {"ok": bool, "manifest": dict, "error": str|None}
        """
        # Validate platform
        if not re.match(r"^[a-z0-9_-]+$", platform):
            return {"ok": False, "error": f"Invalid platform name: {platform}"}

        # Validate version
        if not SEMVER_RE.match(version):
            return {"ok": False, "error": f"Invalid semver: {version}"}

        # Validate file
        if not file_path.is_file():
            return {"ok": False, "error": f"File not found: {file_path}"}

        file_size = file_path.stat().st_size
        if file_size > MAX_FIRMWARE_SIZE:
            return {"ok": False, "error": f"File too large: {file_size} > {MAX_FIRMWARE_SIZE}"}

        if file_size == 0:
            return {"ok": False, "error": "Empty firmware file"}

        if (signature_path is None) != (key_id is None):
            return {"ok": False, "error": "signature_path and key_id must be supplied together"}
        signature: dict[str, Any] = {"verified": False}
        signature_bytes: bytes | None = None
        if signature_path is not None:
            if not signature_path.is_file():
                return {"ok": False, "error": f"Signature file not found: {signature_path}"}
            signature_bytes = signature_path.read_bytes()
            verification = self._verify_bytes(file_path, signature_bytes, key_id or "")
            if not verification["ok"]:
                return verification
            signature = {
                "verified": True,
                "algorithm": "ed25519",
                "key_id": key_id,
                "signature_file": "firmware.sig",
            }

        # Check if version already exists
        dest_dir = self.root / platform / version
        if dest_dir.exists():
            return {"ok": False, "error": f"Version {version} already exists for {platform}"}

        # Copy and compute hash
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_file = dest_dir / "firmware.bin"
        shutil.copy2(file_path, dest_file)
        sha256 = sha256_file(dest_file)
        if signature_bytes is not None:
            (dest_dir / "firmware.sig").write_bytes(signature_bytes)

        # Write manifest
        manifest = {
            "platform": platform,
            "version": version,
            "sha256": sha256,
            "size_bytes": file_size,
            "description": description,
            "uploaded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "firmware_url": f"/firmware/{platform}/{version}/firmware.bin",
            "signature": signature,
        }
        (dest_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        return {"ok": True, "manifest": manifest}

    def verify_artifact(self, platform: str, version: str) -> dict[str, Any]:
        """Verify the stored digest and trusted Ed25519 signature for release gating."""
        manifest = self.get_info(platform, version)
        firmware = self.get_firmware_path(platform, version)
        if not manifest or not firmware:
            return {"ok": False, "error": f"Firmware not found: {platform}/{version}"}
        digest_ok = sha256_file(firmware) == manifest.get("sha256")
        signature = manifest.get("signature", {})
        if not signature.get("verified"):
            return {"ok": False, "sha256_valid": digest_ok, "signature_valid": False,
                    "error": "Firmware is unsigned; signed firmware is required for distribution"}
        signature_path = firmware.with_name(signature.get("signature_file", "firmware.sig"))
        if not signature_path.is_file():
            return {"ok": False, "sha256_valid": digest_ok, "signature_valid": False,
                    "error": "Firmware signature sidecar is missing"}
        result = self._verify_bytes(firmware, signature_path.read_bytes(), str(signature.get("key_id", "")))
        result.update({"sha256_valid": digest_ok, "signature_valid": result.get("ok", False)})
        if not digest_ok:
            result.update({"ok": False, "error": "Firmware SHA-256 does not match manifest"})
        return result

    def list_firmware(self, platform: str | None = None) -> list[dict[str, Any]]:
        """List all firmware, optionally filtered by platform."""
        results = []
        platforms = [platform] if platform else sorted(
            d.name for d in self.root.iterdir() if d.is_dir()
        )
        for plat in platforms:
            plat_dir = self.root / plat
            if not plat_dir.is_dir():
                continue
            for version_dir in sorted(plat_dir.iterdir()):
                manifest_path = version_dir / "manifest.json"
                if manifest_path.is_file():
                    try:
                        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                        results.append(manifest)
                    except (json.JSONDecodeError, OSError):
                        continue
        return results

    def get_info(self, platform: str, version: str) -> dict[str, Any] | None:
        """Get firmware manifest for a specific platform and version."""
        manifest_path = self.root / platform / version / "manifest.json"
        if not manifest_path.is_file():
            return None
        try:
            return json.loads(manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    def get_latest(self, platform: str) -> dict[str, Any] | None:
        """Get the latest firmware version for a platform."""
        plat_dir = self.root / platform
        if not plat_dir.is_dir():
            return None

        versions = []
        for d in plat_dir.iterdir():
            if d.is_dir() and (d / "manifest.json").is_file():
                try:
                    manifest = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
                    versions.append(manifest)
                except (json.JSONDecodeError, OSError):
                    continue

        if not versions:
            return None

        # Sort by version (semver)
        def _version_key(m: dict) -> tuple:
            parts = m.get("version", "0.0.0").split(".")
            return tuple(int(p) for p in parts[:3])

        versions.sort(key=_version_key)
        return versions[-1]

    def delete(self, platform: str, version: str) -> dict[str, Any]:
        """Delete a firmware version."""
        dest_dir = self.root / platform / version
        if not dest_dir.is_dir():
            return {"ok": False, "error": f"Version {version} not found for {platform}"}
        shutil.rmtree(dest_dir)
        return {"ok": True, "deleted": f"{platform}/{version}"}

    def get_firmware_path(self, platform: str, version: str) -> Path | None:
        """Get the path to a firmware binary."""
        path = self.root / platform / version / "firmware.bin"
        return path if path.is_file() else None

    def get_signature_path(self, platform: str, version: str) -> Path | None:
        path = self.root / platform / version / "firmware.sig"
        return path if path.is_file() else None

    def _verify_bytes(self, firmware_path: Path, signature: bytes, key_id: str) -> dict[str, Any]:
        public_key_pem = self._trusted_keys.get(key_id)
        if not public_key_pem:
            return {"ok": False, "error": f"Unknown trusted signing key: {key_id}"}
        if serialization is None:
            return {"ok": False, "error": "cryptography package is required for Ed25519 verification"}
        try:
            public_key = serialization.load_pem_public_key(public_key_pem.encode("utf-8"))
            if not isinstance(public_key, Ed25519PublicKey):
                return {"ok": False, "error": f"Trusted key {key_id} is not an Ed25519 public key"}
            public_key.verify(signature, firmware_path.read_bytes())
            return {"ok": True, "key_id": key_id, "algorithm": "ed25519"}
        except (ValueError, TypeError, InvalidSignature) as exc:
            return {"ok": False, "error": f"Signature verification failed: {exc}"}
