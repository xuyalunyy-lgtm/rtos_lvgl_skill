"""OTA protocol configuration — customizable version comparison and API format.

Loads ota_protocol.json from project root. Falls back to sensible defaults
when the file doesn't exist.

Customizable:
- Version comparison method (semver, integer, date, custom)
- Register request field names
- Register response field names
- Notification payload format
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

# ── Default configuration ──

DEFAULT_CONFIG = {
    "version_compare": {
        "field": "current_version",
        "method": "semver",
        "custom_parser": None,
    },
    "register_request": {
        "required_fields": ["device_ip", "platform", "current_version"],
        "optional_fields": ["mac", "device_name", "hardware_rev"],
    },
    "register_response": {
        "upgrade_available_field": "upgrade_available",
        "latest_version_field": "latest_version",
        "firmware_url_field": "firmware_url",
        "custom_fields": {},
    },
    "notification_payload": {
        "topic": "ota/notify",
        "format": {
            "platform": "{platform}",
            "version": "{version}",
            "url": "{firmware_url}",
            "sha256": "{sha256}",
            "size": "{size_bytes}",
        },
    },
}


class OtaProtocol:
    """Load and apply custom OTA protocol configuration."""

    def __init__(self, config_path: Path | None = None):
        self.config = self._load_config(config_path)
        self._method = self.config["version_compare"]["method"]
        self._custom_parser = self.config["version_compare"].get("custom_parser")

    def _load_config(self, path: Path | None) -> dict:
        """Load ota_protocol.json, fall back to defaults."""
        if path and path.is_file():
            try:
                user_config = json.loads(path.read_text(encoding="utf-8"))
                # Deep merge with defaults
                config = DEFAULT_CONFIG.copy()
                for key in config:
                    if key in user_config and isinstance(config[key], dict):
                        config[key] = {**config[key], **user_config[key]}
                    elif key in user_config:
                        config[key] = user_config[key]
                return config
            except (json.JSONDecodeError, OSError):
                pass
        return DEFAULT_CONFIG.copy()

    def compare_versions(self, current: str, target: str) -> int:
        """Compare two version strings.

        Returns:
            -1 if current < target (upgrade available)
             0 if current == target (up to date)
             1 if current > target (current is newer)
        """
        if self._method == "semver":
            return self._compare_semver(current, target)
        elif self._method == "integer":
            return self._compare_integer(current, target)
        elif self._method == "date":
            return self._compare_date(current, target)
        elif self._method == "custom":
            return self._compare_custom(current, target)
        else:
            return self._compare_semver(current, target)

    def parse_register_request(self, body: dict) -> dict[str, Any]:
        """Parse device register request using configured field names.

        Returns:
            Parsed dict with standardized field names, or {"error": str} on failure.
        """
        req_config = self.config["register_request"]
        required = req_config["required_fields"]
        optional = req_config.get("optional_fields", [])

        # Extract required fields
        result = {}
        for field_name in required:
            # Try configured field name, then standard names
            value = body.get(field_name)
            if value is None and field_name == "current_version":
                value = body.get("version") or body.get("fw_ver") or body.get("app_version")
            if value is None and field_name == "device_ip":
                value = body.get("ip") or body.get("device_ip")
            if value is None:
                return {"error": f"Missing required field: {field_name}"}
            result[field_name] = str(value)

        # Extract optional fields
        for field_name in optional:
            if field_name in body:
                result[field_name] = body[field_name]

        # Extract any extra fields
        known = set(required) | set(optional)
        result["_extra"] = {k: v for k, v in body.items() if k not in known}

        return result

    def build_register_response(
        self,
        current_version: str,
        latest_manifest: dict | None = None,
        firmware_base_url: str = "",
    ) -> dict[str, Any]:
        """Build register response using configured field names.

        Args:
            current_version: Device's current firmware version
            latest_manifest: Latest firmware manifest (None if no firmware available)
            firmware_base_url: Base URL for firmware downloads

        Returns:
            Response dict with configured field names.
        """
        resp_config = self.config["register_response"]
        upgrade_field = resp_config["upgrade_available_field"]
        version_field = resp_config["latest_version_field"]
        url_field = resp_config["firmware_url_field"]
        custom_fields = resp_config.get("custom_fields", {})

        if latest_manifest is None:
            return {
                upgrade_field: False,
                version_field: current_version,
                url_field: "",
                **custom_fields,
            }

        target_version = latest_manifest.get("version", "0.0.0")
        upgrade_available = self.compare_versions(current_version, target_version) < 0

        firmware_url = firmware_base_url + latest_manifest.get("firmware_url", "")

        return {
            upgrade_field: upgrade_available,
            version_field: target_version,
            url_field: firmware_url if upgrade_available else "",
            "sha256": latest_manifest.get("sha256", ""),
            "size_bytes": latest_manifest.get("size_bytes", 0),
            **custom_fields,
        }

    def build_notification_payload(
        self,
        platform: str,
        version: str,
        firmware_url: str,
        sha256: str,
        size_bytes: int,
    ) -> dict[str, Any]:
        """Build upgrade notification payload using configured format."""
        format_spec = self.config["notification_payload"]["format"]
        replacements = {
            "platform": platform,
            "version": version,
            "firmware_url": firmware_url,
            "sha256": sha256,
            "size_bytes": str(size_bytes),
        }
        result = {}
        for key, template in format_spec.items():
            if isinstance(template, str):
                result[key] = template.format(**replacements)
            else:
                result[key] = template
        return result

    @property
    def notification_topic(self) -> str:
        return self.config["notification_payload"]["topic"]

    # ── Version comparison implementations ──

    def _compare_semver(self, current: str, target: str) -> int:
        """Semantic version comparison: major.minor.patch."""
        def _parse(v: str) -> tuple:
            parts = re.findall(r"\d+", v)
            return tuple(int(p) for p in parts[:3]) + (0,) * 3
        c = _parse(current)
        t = _parse(target)
        return (c > t) - (c < t)

    def _compare_integer(self, current: str, target: str) -> int:
        """Integer version comparison."""
        try:
            c = int(re.search(r"\d+", current).group())
            t = int(re.search(r"\d+", target).group())
            return (c > t) - (c < t)
        except (ValueError, AttributeError):
            return 0

    def _compare_date(self, current: str, target: str) -> int:
        """Date version comparison: YYYYMMDD."""
        try:
            c = re.search(r"\d{8}", current).group()
            t = re.search(r"\d{8}", target).group()
            return (c > t) - (c < t)
        except AttributeError:
            return 0

    def _compare_custom(self, current: str, target: str) -> int:
        """Custom version comparison using configured parser."""
        if not self._custom_parser:
            return self._compare_semver(current, target)

        try:
            extract_expr = self._custom_parser.get("extract", "v")
            compare_expr = self._custom_parser.get("compare", "v")

            def _eval(v: str):
                return eval(compare_expr, {"v": eval(extract_expr, {"v": v})})

            c = _eval(current)
            t = _eval(target)
            return (c > t) - (c < t)
        except Exception:
            return self._compare_semver(current, target)
