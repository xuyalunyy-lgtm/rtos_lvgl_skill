"""OTA HTTP server — serves firmware files and device registration API.

Runs in a background thread. Provides:
- GET  /firmware/{platform}/{version}/firmware.bin  — download firmware
- GET  /firmware/{platform}/latest                  — latest version info
- POST /device/register                              — device registration/heartbeat
- GET  /device/{ip}/status                           — device status
"""
from __future__ import annotations

import json
import logging
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, parse_qs

from ota_firmware import FirmwareRepo
from ota_device import DeviceRegistry
from ota_protocol import OtaProtocol

logger = logging.getLogger(__name__)

ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get("OTA_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if h.strip()
]


class OtaRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for OTA server."""

    # Injected by OtaHttpServer
    repo: FirmwareRepo = None
    devices: DeviceRegistry = None
    protocol: OtaProtocol = None
    firmware_base_url: str = ""

    def log_message(self, format, *args):
        """Suppress default stderr logging."""
        logger.debug(format, *args)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        # GET /firmware/{platform}/{version}/firmware.bin
        if path.startswith("/firmware/") and path.endswith("/firmware.bin"):
            parts = path.split("/")
            if len(parts) == 5:
                platform, version = parts[2], parts[3]
                self._serve_firmware(platform, version)
                return

        # GET /firmware/{platform}/latest
        if path.startswith("/firmware/") and path.endswith("/latest"):
            parts = path.split("/")
            if len(parts) == 4:
                platform = parts[2]
                self._serve_latest(platform)
                return

        # GET /device/{ip}/status
        if path.startswith("/device/") and path.endswith("/status"):
            parts = path.split("/")
            if len(parts) == 4:
                device_ip = parts[2]
                self._serve_device_status(device_ip)
                return

        self._json_response(404, {"error": "Not found"})

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        # POST /device/register
        if path == "/device/register":
            self._handle_register()
            return

        self._json_response(404, {"error": "Not found"})

    def _serve_firmware(self, platform: str, version: str):
        """Serve firmware binary for download."""
        fw_path = self.repo.get_firmware_path(platform, version)
        if not fw_path:
            self._json_response(404, {"error": f"Firmware not found: {platform}/{version}"})
            return

        size = fw_path.stat().st_size
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(size))
        self.send_header("Content-Disposition", f'attachment; filename="firmware_{platform}_{version}.bin"')
        self.end_headers()

        with open(fw_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                self.wfile.write(chunk)

    def _serve_latest(self, platform: str):
        """Serve latest firmware info for a platform."""
        latest = self.repo.get_latest(platform)
        if not latest:
            self._json_response(404, {"error": f"No firmware available for {platform}"})
            return

        self._json_response(200, latest)

    def _serve_device_status(self, device_ip: str):
        """Serve device status."""
        device = self.devices.get_device(device_ip)
        if not device:
            self._json_response(404, {"error": f"Device not found: {device_ip}"})
            return

        self._json_response(200, device)

    def _handle_register(self):
        """Handle device registration/heartbeat."""
        # Read request body
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length > 4096:
            self._json_response(413, {"error": "Request too large"})
            return

        try:
            body = json.loads(self.rfile.read(content_length))
        except (json.JSONDecodeError, ValueError):
            self._json_response(400, {"error": "Invalid JSON"})
            return

        # Parse using protocol config
        parsed = self.protocol.parse_register_request(body)
        if "error" in parsed:
            self._json_response(400, parsed)
            return

        # Register device
        result = self.devices.register(
            device_ip=parsed["device_ip"],
            platform=parsed["platform"],
            current_version=parsed["current_version"],
            mac=parsed.get("mac", "unknown"),
            device_name=parsed.get("device_name", ""),
            hardware_rev=parsed.get("hardware_rev", ""),
            extra=parsed.get("_extra", {}),
        )

        # Check for upgrade
        latest = self.repo.get_latest(parsed["platform"])
        response = self.protocol.build_register_response(
            current_version=parsed["current_version"],
            latest_manifest=latest,
            firmware_base_url=self.firmware_base_url,
        )

        response["ok"] = True
        response["device_id"] = result["device_id"]

        self._json_response(200, response)

    def _json_response(self, code: int, data: dict):
        """Send JSON response."""
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class OtaHttpServer:
    """OTA HTTP server running in a background thread."""

    def __init__(
        self,
        host: str,
        port: int,
        repo: FirmwareRepo,
        devices: DeviceRegistry,
        protocol: OtaProtocol,
    ):
        self.host = host
        self.port = port
        self.repo = repo
        self.devices = devices
        self.protocol = protocol
        self._server: HTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._running = False

    def start(self) -> dict[str, Any]:
        """Start the HTTP server in a background thread."""
        if self._running:
            return {"ok": False, "error": "Server already running"}

        if not self._is_host_allowed(self.host):
            return {"ok": False, "error": f"Host '{self.host}' not in allowed hosts: {ALLOWED_HOSTS}"}

        try:
            # Configure handler with shared state
            handler = OtaRequestHandler
            handler.repo = self.repo
            handler.devices = self.devices
            handler.protocol = self.protocol
            handler.firmware_base_url = f"http://{self.host}:{self.port}"

            self._server = HTTPServer((self.host, self.port), handler)
            self._running = True
            self._thread = threading.Thread(target=self._serve, daemon=True)
            self._thread.start()

            return {
                "ok": True,
                "host": self.host,
                "port": self.port,
                "url": f"http://{self.host}:{self.port}",
            }
        except OSError as e:
            return {"ok": False, "error": f"Failed to start server: {e}"}

    def stop(self) -> dict[str, Any]:
        """Stop the HTTP server."""
        if not self._running:
            return {"ok": True, "message": "Server not running"}

        self._running = False
        if self._server:
            self._server.shutdown()
            self._server = None

        return {"ok": True, "message": "Server stopped"}

    @property
    def status(self) -> dict[str, Any]:
        """Server status."""
        return {
            "running": self._running,
            "host": self.host,
            "port": self.port,
            "url": f"http://{self.host}:{self.port}" if self._running else None,
            "device_count": self.devices.device_count,
        }

    def _serve(self):
        """Server loop (runs in background thread)."""
        try:
            self._server.serve_forever()
        except Exception as e:
            logger.error("OTA server error: %s", e)
        finally:
            self._running = False

    def _is_host_allowed(self, host: str) -> bool:
        if host in ("localhost", "127.0.0.1", "::1"):
            return True
        return host in ALLOWED_HOSTS
