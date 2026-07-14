"""OTA device registry — track online devices and upgrade status.

Devices register via HTTP POST and send periodic heartbeats.
The registry tracks current version, platform, and upgrade status.
"""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class DeviceInfo:
    """Registered device information."""
    device_ip: str
    platform: str
    current_version: str
    mac: str
    device_id: str
    last_seen: float
    upgrade_status: str = "idle"  # idle | downloading | installing | done | failed
    device_name: str = ""
    hardware_rev: str = ""
    extra: dict = field(default_factory=dict)


class DeviceRegistry:
    """Device registration table with heartbeat tracking."""

    def __init__(self, stale_timeout: int = 300):
        self._devices: dict[str, DeviceInfo] = {}
        self._stale_timeout = stale_timeout

    def register(
        self,
        device_ip: str,
        platform: str,
        current_version: str,
        mac: str,
        device_name: str = "",
        hardware_rev: str = "",
        extra: dict | None = None,
    ) -> dict[str, Any]:
        """Register or update a device.

        Returns:
            {"ok": bool, "device_id": str, "device": dict}
        """
        device_id = self._make_device_id(platform, mac)
        now = time.time()

        if device_id in self._devices:
            # Update existing device
            dev = self._devices[device_id]
            dev.current_version = current_version
            dev.last_seen = now
            dev.device_ip = device_ip
            if device_name:
                dev.device_name = device_name
            if hardware_rev:
                dev.hardware_rev = hardware_rev
            if extra:
                dev.extra.update(extra)
        else:
            # New device
            self._devices[device_id] = DeviceInfo(
                device_ip=device_ip,
                platform=platform,
                current_version=current_version,
                mac=mac,
                device_id=device_id,
                last_seen=now,
                device_name=device_name,
                hardware_rev=hardware_rev,
                extra=extra or {},
            )

        return {
            "ok": True,
            "device_id": device_id,
            "device": self._device_to_dict(self._devices[device_id]),
        }

    def list_devices(self, platform: str | None = None) -> list[dict[str, Any]]:
        """List registered devices, optionally filtered by platform."""
        self.cleanup_stale()
        devices = list(self._devices.values())
        if platform:
            devices = [d for d in devices if d.platform == platform]
        return [self._device_to_dict(d) for d in devices]

    def get_device(self, device_ip: str) -> dict[str, Any] | None:
        """Get device by IP address."""
        for dev in self._devices.values():
            if dev.device_ip == device_ip:
                return self._device_to_dict(dev)
        return None

    def get_device_by_id(self, device_id: str) -> dict[str, Any] | None:
        """Get device by device_id."""
        dev = self._devices.get(device_id)
        return self._device_to_dict(dev) if dev else None

    def set_upgrade_status(self, device_ip: str, status: str) -> bool:
        """Update upgrade status for a device."""
        for dev in self._devices.values():
            if dev.device_ip == device_ip:
                dev.upgrade_status = status
                return True
        return False

    def cleanup_stale(self) -> int:
        """Remove devices that haven't sent a heartbeat within timeout."""
        now = time.time()
        stale = [
            did for did, dev in self._devices.items()
            if now - dev.last_seen > self._stale_timeout
        ]
        for did in stale:
            del self._devices[did]
        return len(stale)

    @property
    def device_count(self) -> int:
        return len(self._devices)

    def _make_device_id(self, platform: str, mac: str) -> str:
        """Generate deterministic device ID from platform and MAC."""
        raw = f"{platform}_{mac}".lower()
        return hashlib.md5(raw.encode()).hexdigest()[:12]

    def _device_to_dict(self, dev: DeviceInfo) -> dict[str, Any]:
        """Convert DeviceInfo to dict."""
        return {
            "device_id": dev.device_id,
            "device_ip": dev.device_ip,
            "platform": dev.platform,
            "current_version": dev.current_version,
            "mac": dev.mac,
            "device_name": dev.device_name,
            "hardware_rev": dev.hardware_rev,
            "upgrade_status": dev.upgrade_status,
            "last_seen": dev.last_seen,
            "last_seen_ago": round(time.time() - dev.last_seen, 1),
            "extra": dev.extra,
        }
