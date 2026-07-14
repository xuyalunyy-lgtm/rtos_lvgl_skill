#!/usr/bin/env python3
"""Serial MCP Server — stdio JSON-RPC server for serial port debugging.

Exposes serial connect/read/write/search as MCP tools.
All data is stored locally in a ring buffer; AI pulls on demand (no token waste).

Usage:
    python mcp/serial_server.py              # Start server (stdio)
    python mcp/serial_server.py --self-test  # Run self-test

Environment:
    SERIAL_ALLOWED_PORTS  — comma-separated allowed ports (default: * = all)
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from serial_client import SerialBridge, get_bridge
from serial_schemas import SERIAL_RESOURCE_SCHEMAS, SERIAL_TOOL_SCHEMAS

logger = logging.getLogger(__name__)

# ── Protocol constants ──

PROTOCOL_VERSIONS = ["2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25"]
DEFAULT_PROTOCOL_VERSION = "2025-11-25"
SERVER_INFO = {"name": "serial-mcp", "version": "0.1.0"}

# ── Tool implementations ──


def serial_list(args: dict[str, Any]) -> dict[str, Any]:
    """List available serial ports."""
    bridge = get_bridge()
    ports = bridge.list_ports()
    return {"ok": True, "count": len(ports), "ports": ports}


def serial_connect(args: dict[str, Any]) -> dict[str, Any]:
    """Connect to a serial port."""
    bridge = get_bridge()
    return bridge.connect(
        port=args["port"],
        baudrate=args.get("baudrate", 115200),
        bytesize=args.get("bytesize", 8),
        parity=args.get("parity", "N"),
        stopbits=args.get("stopbits", 1),
    )


def serial_disconnect(args: dict[str, Any]) -> dict[str, Any]:
    """Disconnect from serial port."""
    bridge = get_bridge()
    return bridge.disconnect()


def serial_write(args: dict[str, Any]) -> dict[str, Any]:
    """Send data to serial port."""
    bridge = get_bridge()
    return bridge.write(
        data=args["data"],
        newline=args.get("newline", ""),
    )


def serial_get_lines(args: dict[str, Any]) -> dict[str, Any]:
    """Read lines from local ring buffer."""
    bridge = get_bridge()
    lines = bridge.get_lines(
        n=args.get("n", 100),
        direction=args.get("direction"),
    )
    return {"ok": True, "count": len(lines), "lines": lines}


def serial_search(args: dict[str, Any]) -> dict[str, Any]:
    """Search ring buffer for keyword."""
    bridge = get_bridge()
    results = bridge.search(
        keyword=args["keyword"],
        n=args.get("n", 50),
    )
    return {"ok": True, "count": len(results), "matches": results}


def serial_get_stats(args: dict[str, Any]) -> dict[str, Any]:
    """Get buffer statistics."""
    bridge = get_bridge()
    stats = bridge.get_stats()
    return {"ok": True, **stats}


def serial_watch(args: dict[str, Any]) -> dict[str, Any]:
    """Start/stop/query background symptom watch."""
    bridge = get_bridge()
    action = args["action"]

    if action == "start":
        return bridge.start_watch(
            platform=args.get("platform", "esp32"),
            max_alerts=50,
        )
    elif action == "stop":
        return bridge.stop_watch()
    elif action == "alerts":
        alerts = bridge.get_watch_alerts(n=args.get("n", 20))
        return {"ok": True, "count": len(alerts), "alerts": alerts}
    elif action == "status":
        status = bridge.get_watch_status()
        return {"ok": True, **status}
    else:
        return {"ok": False, "error": f"Unknown action: {action}"}


def serial_summary(args: dict[str, Any]) -> dict[str, Any]:
    """Analyze buffer and return health summary."""
    bridge = get_bridge()
    return bridge.summarize_buffer(n=args.get("n", 500))


# ── Tool dispatch ──

TOOLS = {
    "serial_list": serial_list,
    "serial_connect": serial_connect,
    "serial_disconnect": serial_disconnect,
    "serial_write": serial_write,
    "serial_get_lines": serial_get_lines,
    "serial_search": serial_search,
    "serial_get_stats": serial_get_stats,
    "serial_watch": serial_watch,
    "serial_summary": serial_summary,
}

TOOL_SCHEMA_MAP = {s["name"]: s for s in SERIAL_TOOL_SCHEMAS}


# ── Resource implementations ──


def get_connection_status() -> dict[str, Any]:
    bridge = get_bridge()
    return {"uri": "serial://connection-status", "mimeType": "application/json", "text": json.dumps(bridge.status)}


def get_log_buffer() -> dict[str, Any]:
    bridge = get_bridge()
    lines = bridge.get_lines(n=100)
    return {"uri": "serial://log-buffer", "mimeType": "application/json", "text": json.dumps(lines)}


def get_available_ports() -> dict[str, Any]:
    bridge = get_bridge()
    ports = bridge.list_ports()
    return {"uri": "serial://available-ports", "mimeType": "application/json", "text": json.dumps(ports)}


RESOURCES = {
    "serial://connection-status": get_connection_status,
    "serial://log-buffer": get_log_buffer,
    "serial://available-ports": get_available_ports,
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
        return _jsonrpc_result({"tools": SERIAL_TOOL_SCHEMAS}, req_id)

    if method == "resources/list":
        return _jsonrpc_result({"resources": SERIAL_RESOURCE_SCHEMAS}, req_id)

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

    # Test 1: Schema validation
    check("has tool schemas", len(SERIAL_TOOL_SCHEMAS) == 9)
    check("has resource schemas", len(SERIAL_RESOURCE_SCHEMAS) == 3)
    check("all tools registered", set(TOOLS.keys()) == set(TOOL_SCHEMA_MAP.keys()))

    for schema in SERIAL_TOOL_SCHEMAS:
        check(f"schema {schema['name']} has name", "name" in schema)
        check(f"schema {schema['name']} has inputSchema", "inputSchema" in schema)

    # Test 2: SerialBridge instantiation
    bridge = SerialBridge(max_lines=100)
    check("bridge created", bridge is not None)
    check("bridge not connected", not bridge.status["connected"])

    # Test 3: Port listing (just check it doesn't crash)
    ports = bridge.list_ports()
    check("list_ports returns list", isinstance(ports, list))

    # Test 4: Ring buffer operations
    bridge._buffer.append({"ts": 1.0, "raw": "Hello from device", "direction": "rx"})
    bridge._buffer.append({"ts": 2.0, "raw": "AT+RST", "direction": "tx"})
    bridge._buffer.append({"ts": 3.0, "raw": "OK", "direction": "rx"})
    bridge._buffer.append({"ts": 4.0, "raw": "ERROR: timeout", "direction": "rx"})
    bridge._buffer.append({"ts": 5.0, "raw": "ready", "direction": "rx"})

    # Test get_lines
    all_lines = bridge.get_lines(n=10)
    check("get_lines returns all", len(all_lines) == 5)

    rx_lines = bridge.get_lines(n=10, direction="rx")
    check("get_lines filters rx", len(rx_lines) == 4)

    tx_lines = bridge.get_lines(n=10, direction="tx")
    check("get_lines filters tx", len(tx_lines) == 1)

    recent = bridge.get_lines(n=2)
    check("get_lines respects n", len(recent) == 2 and recent[-1]["raw"] == "ready")

    # Test 5: Search
    errors = bridge.search("ERROR")
    check("search finds ERROR", len(errors) == 1 and errors[0]["raw"] == "ERROR: timeout")

    not_found = bridge.search("NONEXISTENT")
    check("search empty for miss", len(not_found) == 0)

    at_results = bridge.search("AT")
    check("search finds AT", len(at_results) == 1)

    # Test 6: Stats
    stats = bridge.get_stats()
    check("stats total_lines", stats["total_lines"] == 5)
    check("stats rx_lines", stats["rx_lines"] == 4)
    check("stats tx_lines", stats["tx_lines"] == 1)
    check("stats first_ts", stats["first_ts"] == 1.0)
    check("stats last_ts", stats["last_ts"] == 5.0)

    # Test 7: Ring buffer overflow
    small_bridge = SerialBridge(max_lines=3)
    for i in range(5):
        small_bridge._buffer.append({"ts": float(i), "raw": f"line {i}", "direction": "rx"})
    check("ring buffer overflow", len(small_bridge._buffer) == 3)
    check("ring buffer keeps newest", small_bridge._buffer[-1]["raw"] == "line 4")

    # Test 8: Status
    status = bridge.status
    check("status has connected", "connected" in status)
    check("status has buffer_size", "buffer_size" in status)
    check("status buffer_size correct", status["buffer_size"] == 5)

    # Test 9: Port allowlist
    check("* allows all ports", bridge._is_port_allowed("COM99"))
    bridge2 = SerialBridge()
    bridge2._port = "test"
    # Default SERIAL_ALLOWED_PORTS is *, so all allowed

    # Test 10: JSON-RPC handler
    resp = _handle_request({"method": "initialize", "params": {"protocolVersion": "2025-11-25"}, "id": 1})
    check("initialize works", resp is not None and resp.get("result", {}).get("protocolVersion") == "2025-11-25")

    resp = _handle_request({"method": "tools/list", "params": {}, "id": 2})
    check("tools/list returns 9", resp is not None and len(resp.get("result", {}).get("tools", [])) == 9)

    resp = _handle_request({"method": "resources/list", "params": {}, "id": 3})
    check("resources/list returns 3", resp is not None and len(resp.get("result", {}).get("resources", [])) == 3)

    resp = _handle_request({"method": "ping", "params": {}, "id": 4})
    check("ping works", resp is not None and "result" in resp)

    resp = _handle_request({"method": "unknown_method", "params": {}, "id": 5})
    check("unknown method returns error", resp is not None and resp.get("error", {}).get("code") == -32601)

    # Test 11: Tool call — list ports
    resp = _handle_request({"method": "tools/call", "params": {"name": "serial_list", "arguments": {}}, "id": 6})
    check("serial_list tool call", resp is not None)
    if resp:
        result = resp.get("result", {})
        content = result.get("content", [{}])
        if content:
            inner = json.loads(content[0].get("text", "{}"))
            check("serial_list returns ok", inner.get("ok") is True)

    # Test 12: Tool call — get_stats
    resp = _handle_request({"method": "tools/call", "params": {"name": "serial_get_stats", "arguments": {}}, "id": 7})
    check("serial_get_stats tool call", resp is not None)

    # Test 13: Tool call — connect without valid port (should error gracefully)
    resp = _handle_request({"method": "tools/call", "params": {"name": "serial_connect", "arguments": {"port": "INVALID_PORT"}}, "id": 8})
    check("connect invalid port handled", resp is not None)
    if resp:
        result = resp.get("result", {})
        content = result.get("content", [{}])
        if content:
            inner = json.loads(content[0].get("text", "{}"))
            check("connect invalid port returns error", inner.get("ok") is False)

    # Cleanup
    bridge.shutdown()

    print(f"\nSelf-test: {passed} passed, {failed} failed")
    return 0 if failed == 0 else 1


# ── CLI ──


def main() -> int:
    parser = argparse.ArgumentParser(description="Serial MCP Server")
    parser.add_argument("--self-test", action="store_true", help="Run self-test")
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    serve_stdio()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
