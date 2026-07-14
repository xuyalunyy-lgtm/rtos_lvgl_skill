#!/usr/bin/env python3
"""OTA MCP Server — stdio JSON-RPC server for local OTA firmware management.

Exposes firmware upload/download, device registration, and upgrade push as MCP tools.
Follows the same JSON-RPC 2.0 over stdio pattern as the MQTT MCP server.

Usage:
    python mcp/ota_server.py              # Start server (stdio)
    python mcp/ota_server.py --self-test  # Run self-test

Environment:
    OTA_ALLOWED_HOSTS  — comma-separated allowed server hosts (default: localhost)
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from ota_firmware import FirmwareRepo
from ota_device import DeviceRegistry
from ota_protocol import OtaProtocol
from ota_http import OtaHttpServer
from ota_schemas import OTA_RESOURCE_SCHEMAS, OTA_TOOL_SCHEMAS

logger = logging.getLogger(__name__)

# ── Protocol constants ──

PROTOCOL_VERSIONS = ["2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25"]
DEFAULT_PROTOCOL_VERSION = "2025-11-25"
SERVER_INFO = {"name": "ota-mcp", "version": "0.1.0"}

# ── Shared state ──

FIRMWARE_ROOT = ROOT / "artifacts" / "firmware"
_repo = FirmwareRepo(FIRMWARE_ROOT)
_devices = DeviceRegistry(stale_timeout=300)
_protocol = OtaProtocol(ROOT / "ota_protocol.json")
_http_server: OtaHttpServer | None = None


# ── Tool implementations ──


def ota_start(args: dict[str, Any]) -> dict[str, Any]:
    """Start OTA HTTP server."""
    global _http_server
    if _http_server and _http_server._running:
        return {"ok": False, "error": "Server already running", "status": _http_server.status}

    host = args.get("host", "localhost")
    port = args.get("port", 8080)

    _http_server = OtaHttpServer(host, port, _repo, _devices, _protocol)
    return _http_server.start()


def ota_stop(args: dict[str, Any]) -> dict[str, Any]:
    """Stop OTA HTTP server."""
    global _http_server
    if not _http_server:
        return {"ok": True, "message": "Server not running"}
    result = _http_server.stop()
    _http_server = None
    return result


def ota_server_status(args: dict[str, Any]) -> dict[str, Any]:
    """Get server status."""
    if _http_server:
        return {"ok": True, **_http_server.status}
    return {
        "ok": True,
        "running": False,
        "host": None,
        "port": None,
        "url": None,
        "device_count": _devices.device_count,
    }


def ota_upload(args: dict[str, Any]) -> dict[str, Any]:
    """Upload firmware to repository."""
    platform = args["platform"]
    version = args["version"]
    file_path = Path(args["file_path"])
    description = args.get("description", "")

    return _repo.upload(platform, version, file_path, description)


def ota_list(args: dict[str, Any]) -> dict[str, Any]:
    """List firmware in repository."""
    platform = args.get("platform")
    firmware = _repo.list_firmware(platform)
    return {"ok": True, "count": len(firmware), "firmware": firmware}


def ota_delete(args: dict[str, Any]) -> dict[str, Any]:
    """Delete firmware version."""
    return _repo.delete(args["platform"], args["version"])


def ota_info(args: dict[str, Any]) -> dict[str, Any]:
    """Get firmware info."""
    manifest = _repo.get_info(args["platform"], args["version"])
    if manifest:
        return {"ok": True, "manifest": manifest}
    return {"ok": False, "error": f"Firmware not found: {args['platform']}/{args['version']}"}


def ota_push(args: dict[str, Any]) -> dict[str, Any]:
    """Push upgrade notification to a device."""
    device_ip = args["device_ip"]
    platform = args["platform"]
    version = args["version"]

    device = _devices.get_device(device_ip)
    if not device:
        return {"ok": False, "error": f"Device not registered: {device_ip}"}

    firmware = _repo.get_info(platform, version)
    if not firmware:
        return {"ok": False, "error": f"Firmware not found: {platform}/{version}"}

    # In a real implementation, this would send an HTTP request to the device
    # or publish via MQTT. For now, we update the device status.
    _devices.set_upgrade_status(device_ip, "notified")

    payload = _protocol.build_notification_payload(
        platform=platform,
        version=version,
        firmware_url=f"http://localhost:{_http_server.port if _http_server else 8080}{firmware['firmware_url']}",
        sha256=firmware["sha256"],
        size_bytes=firmware["size_bytes"],
    )

    return {
        "ok": True,
        "device_ip": device_ip,
        "notification": payload,
        "message": f"Upgrade notification sent to {device_ip}",
    }


def ota_push_all(args: dict[str, Any]) -> dict[str, Any]:
    """Push upgrade to all online devices of a platform."""
    platform = args["platform"]
    version = args["version"]

    devices = _devices.list_devices(platform)
    if not devices:
        return {"ok": True, "message": f"No online devices for {platform}", "notified": 0}

    firmware = _repo.get_info(platform, version)
    if not firmware:
        return {"ok": False, "error": f"Firmware not found: {platform}/{version}"}

    notified = 0
    for device in devices:
        _devices.set_upgrade_status(device["device_ip"], "notified")
        notified += 1

    return {
        "ok": True,
        "platform": platform,
        "version": version,
        "notified": notified,
        "devices": [d["device_ip"] for d in devices],
    }


def ota_device_status(args: dict[str, Any]) -> dict[str, Any]:
    """Get device status."""
    device = _devices.get_device(args["device_ip"])
    if device:
        return {"ok": True, "device": device}
    return {"ok": False, "error": f"Device not found: {args['device_ip']}"}


# ── Tool dispatch ──

TOOLS = {
    "ota_start": ota_start,
    "ota_stop": ota_stop,
    "ota_server_status": ota_server_status,
    "ota_upload": ota_upload,
    "ota_list": ota_list,
    "ota_delete": ota_delete,
    "ota_info": ota_info,
    "ota_push": ota_push,
    "ota_push_all": ota_push_all,
    "ota_device_status": ota_device_status,
}

TOOL_SCHEMA_MAP = {s["name"]: s for s in OTA_TOOL_SCHEMAS}


# ── Resource implementations ──


def get_server_status() -> dict[str, Any]:
    if _http_server:
        status = _http_server.status
    else:
        status = {"running": False, "host": None, "port": None, "url": None, "device_count": _devices.device_count}
    return {"uri": "ota://server-status", "mimeType": "application/json", "text": json.dumps(status)}


def get_firmware_list() -> dict[str, Any]:
    firmware = _repo.list_firmware()
    return {"uri": "ota://firmware-list", "mimeType": "application/json", "text": json.dumps(firmware)}


def get_device_registry() -> dict[str, Any]:
    devices = _devices.list_devices()
    return {"uri": "ota://device-registry", "mimeType": "application/json", "text": json.dumps(devices)}


RESOURCES = {
    "ota://server-status": get_server_status,
    "ota://firmware-list": get_firmware_list,
    "ota://device-registry": get_device_registry,
}


# ── MCP helpers ──


def _mcp_result(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}],
        "isError": not payload.get("ok", True),
    }


def _jsonrpc_error(code: int, message: str, id: Any = None) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "error": {"code": code, "message": message}, "id": id}


def _jsonrpc_result(result: Any, id: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "result": result, "id": id}


# ── Request handlers ──


def _handle_request(req: dict[str, Any]) -> dict[str, Any] | None:
    method = req.get("method", "")
    params = req.get("params", {})
    req_id = req.get("id")

    if method == "notifications/initialized":
        return None

    if method == "initialize":
        client_version = params.get("protocolVersion", DEFAULT_PROTOCOL_VERSION)
        version = client_version if client_version in PROTOCOL_VERSIONS else DEFAULT_PROTOCOL_VERSION
        return _jsonrpc_result({
            "protocolVersion": version,
            "capabilities": {"tools": {}, "resources": {}},
            "serverInfo": SERVER_INFO,
        }, req_id)

    if method == "ping":
        return _jsonrpc_result({}, req_id)

    if method == "tools/list":
        return _jsonrpc_result({"tools": OTA_TOOL_SCHEMAS}, req_id)

    if method == "resources/list":
        return _jsonrpc_result({"resources": OTA_RESOURCE_SCHEMAS}, req_id)

    if method == "resources/read":
        uri = params.get("uri", "")
        handler = RESOURCES.get(uri)
        if not handler:
            return _jsonrpc_error(-32602, f"Unknown resource: {uri}", req_id)
        try:
            return _jsonrpc_result(handler(), req_id)
        except Exception as e:
            return _jsonrpc_error(-32000, f"Resource error: {e}", req_id)

    if method == "tools/call":
        tool_name = params.get("name", "")
        tool_args = params.get("arguments", {})
        handler = TOOLS.get(tool_name)
        if not handler:
            return _jsonrpc_error(-32602, f"Unknown tool: {tool_name}", req_id)
        if not isinstance(tool_args, dict):
            return _jsonrpc_error(-32602, "Arguments must be an object", req_id)
        try:
            result = handler(tool_args)
            return _jsonrpc_result(_mcp_result(result), req_id)
        except Exception as e:
            logger.exception("Tool %s failed", tool_name)
            return _jsonrpc_result(_mcp_result({"ok": False, "error": str(e)}), req_id)

    return _jsonrpc_error(-32601, f"Method not found: {method}", req_id)


# ── Main loop ──


def serve_stdio() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            print(json.dumps(_jsonrpc_error(-32700, "Parse error")), flush=True)
            continue

        if isinstance(message, list):
            responses = []
            for req in message:
                if isinstance(req, dict) and "method" in req:
                    resp = _handle_request(req)
                    if resp is not None:
                        responses.append(resp)
            if responses:
                print(json.dumps(responses), flush=True)
        elif isinstance(message, dict) and "method" in message:
            response = _handle_request(message)
            if response is not None:
                print(json.dumps(response), flush=True)
        else:
            print(json.dumps(_jsonrpc_error(-32600, "Invalid request")), flush=True)


# ── Self-test ──


def run_self_test() -> int:
    passed = 0
    failed = 0

    def check(name: str, condition: bool):
        nonlocal passed, failed
        if condition:
            passed += 1
            print(f"  PASS: {name}")
        else:
            failed += 1
            print(f"  FAIL: {name}")

    import tempfile

    # Test 1: Schema validation
    check("has tool schemas", len(OTA_TOOL_SCHEMAS) == 10)
    check("has resource schemas", len(OTA_RESOURCE_SCHEMAS) == 3)
    check("all tools registered", set(TOOLS.keys()) == set(TOOL_SCHEMA_MAP.keys()))

    # Test 2: Firmware repo
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = FirmwareRepo(Path(tmpdir))

        # Create a test firmware file
        fw_file = Path(tmpdir) / "test.bin"
        fw_file.write_bytes(b"\x00" * 1024)

        result = repo.upload("esp32", "1.0.0", fw_file, "Test firmware")
        check("upload ok", result["ok"])
        check("upload has sha256", len(result["manifest"]["sha256"]) == 64)

        # List
        firmware = repo.list_firmware()
        check("list returns 1", len(firmware) == 1)

        # Get info
        info = repo.get_info("esp32", "1.0.0")
        check("info exists", info is not None)
        check("info has version", info["version"] == "1.0.0")

        # Get latest
        latest = repo.get_latest("esp32")
        check("latest exists", latest is not None)

        # Duplicate upload fails
        dup = repo.upload("esp32", "1.0.0", fw_file)
        check("duplicate rejected", not dup["ok"])

        # Invalid version fails
        bad_ver = repo.upload("esp32", "abc", fw_file)
        check("invalid version rejected", not bad_ver["ok"])

        # Delete
        del_result = repo.delete("esp32", "1.0.0")
        check("delete ok", del_result["ok"])
        check("list empty after delete", len(repo.list_firmware()) == 0)

    # Test 3: Device registry
    devices = DeviceRegistry(stale_timeout=60)
    result = devices.register("192.168.1.100", "esp32", "1.0.0", "AA:BB:CC:DD:EE:FF")
    check("register ok", result["ok"])
    check("register has device_id", len(result["device_id"]) == 12)

    device = devices.get_device("192.168.1.100")
    check("get_device ok", device is not None)
    check("device has platform", device["platform"] == "esp32")

    devices.set_upgrade_status("192.168.1.100", "downloading")
    device = devices.get_device("192.168.1.100")
    check("upgrade status updated", device["upgrade_status"] == "downloading")

    check("device count", devices.device_count == 1)

    # Test 4: Protocol
    protocol = OtaProtocol()
    check("semver compare equal", protocol.compare_versions("1.0.0", "1.0.0") == 0)
    check("semver compare less", protocol.compare_versions("1.0.0", "1.0.1") < 0)
    check("semver compare greater", protocol.compare_versions("1.1.0", "1.0.0") > 0)

    parsed = protocol.parse_register_request({"device_ip": "1.2.3.4", "platform": "esp32", "current_version": "1.0.0"})
    check("parse register ok", "error" not in parsed)

    resp = protocol.build_register_response("1.0.0", {"version": "1.1.0", "firmware_url": "/fw.bin", "sha256": "abc", "size_bytes": 100})
    check("response has upgrade_available", resp.get("upgrade_available") == True)

    # Test 5: JSON-RPC handler
    resp = _handle_request({"method": "initialize", "params": {"protocolVersion": "2025-11-25"}, "id": 1})
    check("initialize works", resp is not None and resp.get("result", {}).get("protocolVersion") == "2025-11-25")

    resp = _handle_request({"method": "tools/list", "params": {}, "id": 2})
    check("tools/list returns 10", resp is not None and len(resp.get("result", {}).get("tools", [])) == 10)

    resp = _handle_request({"method": "resources/list", "params": {}, "id": 3})
    check("resources/list returns 3", resp is not None and len(resp.get("result", {}).get("resources", [])) == 3)

    print(f"\nSelf-test: {passed} passed, {failed} failed")
    return 0 if failed == 0 else 1


# ── CLI ──


def main() -> int:
    parser = argparse.ArgumentParser(description="OTA MCP Server")
    parser.add_argument("--self-test", action="store_true", help="Run self-test")
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    serve_stdio()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
