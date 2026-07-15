"""OTA device registry — track online devices and upgrade status.

Devices register via HTTP POST and send periodic heartbeats.
The registry tracks current version, platform, and upgrade status.
"""
from __future__ import annotations

import hashlib
import time
from copy import deepcopy
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
    active_partition: str = "A"
    previous_partition: str | None = None
    pending_partition: str | None = None
    pending_version: str | None = None
    rollback_reason: str | None = None
    boot_attempts: int = 0
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

    def prepare_ab_switch(self, device_ip: str, target_version: str, target_partition: str | None = None) -> dict[str, Any]:
        """Schedule the inactive A/B slot; actual switching remains device/bootloader owned."""
        dev = self._find(device_ip)
        if not dev:
            return {"ok": False, "error": f"Device not found: {device_ip}"}
        active = dev.active_partition.upper()
        if active not in {"A", "B"}:
            return {"ok": False, "error": f"Invalid active partition: {dev.active_partition}"}
        target = (target_partition or ("B" if active == "A" else "A")).upper()
        if target not in {"A", "B"} or target == active:
            return {"ok": False, "error": "target_partition must be the inactive A/B partition"}
        dev.pending_partition = target
        dev.pending_version = target_version
        dev.rollback_reason = None
        dev.boot_attempts = 0
        dev.upgrade_status = "switch_pending"
        return {"ok": True, "device": self._device_to_dict(dev), "next_action": "device must boot pending partition and report result"}

    def report_boot_result(self, device_ip: str, partition: str, success: bool, reason: str = "") -> dict[str, Any]:
        """Apply device-reported boot outcome; failed pending boots retain the known-good slot."""
        dev = self._find(device_ip)
        if not dev:
            return {"ok": False, "error": f"Device not found: {device_ip}"}
        partition = partition.upper()
        if partition not in {"A", "B"}:
            return {"ok": False, "error": "partition must be A or B"}
        if partition != dev.pending_partition:
            return {"ok": False, "error": f"No pending switch for partition {partition}"}
        dev.boot_attempts += 1
        if success:
            dev.previous_partition = dev.active_partition
            dev.active_partition = partition
            dev.current_version = dev.pending_version or dev.current_version
            dev.pending_partition = None
            dev.pending_version = None
            dev.rollback_reason = None
            dev.upgrade_status = "done"
            return {"ok": True, "rolled_back": False, "device": self._device_to_dict(dev)}
        dev.pending_partition = None
        dev.pending_version = None
        dev.rollback_reason = reason or "pending partition boot failed"
        dev.upgrade_status = "rolled_back"
        return {"ok": True, "rolled_back": True, "device": self._device_to_dict(dev)}

    def validate_ab_state(self, device_ip: str) -> dict[str, Any]:
        dev = self._find(device_ip)
        if not dev:
            return {"ok": False, "error": f"Device not found: {device_ip}"}
        errors = []
        if dev.active_partition.upper() not in {"A", "B"}:
            errors.append("active_partition must be A or B")
        if dev.pending_partition and dev.pending_partition == dev.active_partition:
            errors.append("pending_partition must differ from active_partition")
        if dev.pending_partition and not dev.pending_version:
            errors.append("pending_version is required while a partition switch is pending")
        return {"ok": not errors, "errors": errors, "device": self._device_to_dict(dev)}

    def test_rollback(self, device_ip: str) -> dict[str, Any]:
        """Dry-run the failure path and restore registry state afterwards."""
        dev = self._find(device_ip)
        if not dev:
            return {"ok": False, "error": f"Device not found: {device_ip}"}
        if not dev.pending_partition:
            return {"ok": False, "error": "Prepare an A/B switch before running a rollback test"}
        original = deepcopy(dev)
        expected_active = dev.active_partition
        result = self.report_boot_result(device_ip, dev.pending_partition, False, "simulated rollback test")
        rollback_safe = result.get("rolled_back") and self._find(device_ip).active_partition == expected_active
        self._devices[dev.device_id] = original
        return {"ok": bool(rollback_safe), "simulated": True, "active_partition_preserved": rollback_safe,
                "restored_device": self._device_to_dict(original)}

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

    def _find(self, device_ip: str) -> DeviceInfo | None:
        return next((dev for dev in self._devices.values() if dev.device_ip == device_ip), None)

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
            "active_partition": dev.active_partition,
            "previous_partition": dev.previous_partition,
            "pending_partition": dev.pending_partition,
            "pending_version": dev.pending_version,
            "rollback_reason": dev.rollback_reason,
            "boot_attempts": dev.boot_attempts,
            "last_seen": dev.last_seen,
            "last_seen_ago": round(time.time() - dev.last_seen, 1),
            "extra": dev.extra,
        }
