#!/usr/bin/env python3
"""Serial MCP Server — stdio JSON-RPC server for serial port debugging.

Exposes serial connect/read/write/search as MCP tools.
All data is stored locally in a ring buffer; AI pulls on demand (no token waste).

Usage:
    python mcp/serial_server.py              # Start server (stdio)
    python mcp/serial_server.py --self-test  # Run self-test

Environment:
    SERIAL_ALLOWED_PORTS  — required comma-separated allowlist, e.g. COM3,COM5
    SERIAL_LOG_DIR        — optional directory for persistent RX/TX session logs
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


def serial_request(args: dict[str, Any]) -> dict[str, Any]:
    """Send a command and wait for a matching response."""
    bridge = get_bridge()
    return bridge.request(
        command=args["command"],
        expect=args["expect"],
        timeout=args.get("timeout", 5.0),
        newline=args.get("newline", "\r\n"),
        context_lines=args.get("context_lines", 5),
    )


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


def serial_check_device(args: dict[str, Any]) -> dict[str, Any]:
    """Check if the previously connected device is still present."""
    bridge = get_bridge()
    return bridge.check_device_present()


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


def serial_bookmark(args: dict[str, Any]) -> dict[str, Any]:
    """Mark a moment in the log with a labeled bookmark."""
    bridge = get_bridge()
    return bridge.bookmark(label=args["label"])


def serial_export_bundle(args: dict[str, Any]) -> dict[str, Any]:
    """Export a minimal reproduction bundle."""
    bridge = get_bridge()
    return bridge.export_bundle(
        context_lines=args.get("context_lines", 200),
        include_alerts=args.get("include_alerts", True),
    )


# ── Tool dispatch ──

TOOLS = {
    "serial_list": serial_list,
    "serial_connect": serial_connect,
    "serial_disconnect": serial_disconnect,
    "serial_write": serial_write,
    "serial_request": serial_request,
    "serial_get_lines": serial_get_lines,
    "serial_search": serial_search,
    "serial_check_device": serial_check_device,
    "serial_get_stats": serial_get_stats,
    "serial_watch": serial_watch,
    "serial_bookmark": serial_bookmark,
    "serial_export_bundle": serial_export_bundle,
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
    check("has tool schemas", bool(SERIAL_TOOL_SCHEMAS))
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

    # Test 9: serial_request on disconnected bridge returns error
    req_result = bridge.request("AT+RST", "ready", timeout=0.5)
    check("request while disconnected returns error", req_result.get("ok") is False)

    # Test 9b: serial_request with invalid regex returns error (works even disconnected)
    req_result2 = bridge.request("AT+RST", "(?P<incomplete", timeout=0.5)
    check("request invalid regex returns error", req_result2.get("ok") is False and "Invalid regex" in req_result2.get("error", ""))

    # Test 9c: serial_request timeout returns recent_rx
    req_bridge = SerialBridge(max_lines=100)
    req_bridge._buffer.append({"ts": 1.0, "raw": "some log line", "direction": "rx"})
    req_bridge._buffer.append({"ts": 2.0, "raw": "another line", "direction": "rx"})
    # Simulate connected state for timeout test
    req_bridge._connected = True
    req_bridge._serial = None  # Will cause write failure
    req_result3 = req_bridge.request("AT", "OK", timeout=0.2)
    check("request with no serial returns write error", req_result3.get("ok") is False)
    req_bridge.shutdown()

    # Test 9d: check_device_present with no identity returns not present
    check_result = bridge.check_device_present()
    check("check_device with no identity returns not present", check_result.get("present") is False)

    # Test 9e: _allowlist_entry_matches with serial
    identity = {"serial_number": "ABC123", "vid": "0x1a86", "pid": "0x7523"}
    check("allowlist serial match", SerialBridge._allowlist_entry_matches("serial:ABC123", identity))
    check("allowlist serial no match", not SerialBridge._allowlist_entry_matches("serial:XYZ", identity))

    # Test 9f: _allowlist_entry_matches with vid:pid
    check("allowlist vid:pid match", SerialBridge._allowlist_entry_matches("vid:1a86 pid:7523", identity))
    check("allowlist vid only match", SerialBridge._allowlist_entry_matches("vid:1a86", identity))
    check("allowlist vid:pid no match", not SerialBridge._allowlist_entry_matches("vid:1a86 pid:9999", identity))
    check("allowlist vid no match", not SerialBridge._allowlist_entry_matches("vid:0000", identity))

    # Test 9g: Default-deny and explicit allowlist.
    check("default denies unconfigured port", not bridge._is_port_allowed("COM99"))
    allowed_bridge = SerialBridge(allowed_ports=("COM7",))
    check("explicit allowlist permits configured port", allowed_bridge._is_port_allowed("COM7"))
    check("explicit allowlist blocks other port", not allowed_bridge._is_port_allowed("COM8"))

    # Test 10: Configured log directory stores an RX/TX session record.
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        log_bridge = SerialBridge(log_dir=Path(tmpdir))
        log_bridge._open_log_file("COM7")
        log_bridge._record_line("boot complete", "rx")
        log_path = log_bridge._log_path
        log_bridge._close_log_file()
        check("log path created", log_path is not None and log_path.is_file())
        log_content = log_path.read_text(encoding="utf-8") if log_path else ""
        check("log record persisted", log_path is not None and "[RX] boot complete" in log_content)
        check("log has metadata header", "port: COM7" in log_content)

    # Test 10b: Redaction masks sensitive data.
    with tempfile.TemporaryDirectory() as tmpdir:
        redact_bridge = SerialBridge(log_dir=Path(tmpdir))
        redact_bridge._open_log_file("COM8")
        redact_bridge._record_line("AT+CWJAP=\"MyWifi\",\"secret123\"", "tx")
        redact_bridge._record_line("token=abc123xyz", "tx")
        redact_bridge._close_log_file()
        redact_path = redact_bridge._log_path
        redact_content = redact_path.read_text(encoding="utf-8") if redact_path else ""
        check("redaction masks password", "secret123" not in redact_content)
        check("redaction masks token", "abc123xyz" not in redact_content)
        check("redaction has marker", "[REDACTED]" in redact_content)

    # Test 10c: Bookmark writes to log and buffer.
    with tempfile.TemporaryDirectory() as tmpdir:
        bm_bridge = SerialBridge(log_dir=Path(tmpdir))
        bm_bridge._connected = True
        bm_bridge._open_log_file("COM9")
        bm_result = bm_bridge.bookmark("test-start")
        check("bookmark returns ok", bm_result.get("ok") is True)
        bm_bridge._close_log_file()
        bm_content = bm_bridge._log_path.read_text(encoding="utf-8") if bm_bridge._log_path else ""
        check("bookmark in log", "BOOKMARK" in bm_content and "test-start" in bm_content)
        bm_lines = bm_bridge.get_lines(n=1, direction="bookmark")
        check("bookmark in buffer", len(bm_lines) == 1)

    # Test 10d: Export bundle creates JSON file.
    with tempfile.TemporaryDirectory() as tmpdir:
        export_bridge = SerialBridge(log_dir=Path(tmpdir))
        export_bridge._buffer.append({"ts": 1.0, "raw": "line1", "direction": "rx"})
        export_result = export_bridge.export_bundle(context_lines=10)
        check("export bundle ok", export_result.get("ok") is True)
        bundle_path = export_result.get("path", "")
        check("export bundle file exists", Path(bundle_path).is_file() if bundle_path else False)

    # Test 10e: RotatingLogWriter respects max_size.
    with tempfile.TemporaryDirectory() as tmpdir:
        from serial_client import RotatingLogWriter
        writer = RotatingLogWriter(Path(tmpdir), "COM10", max_size=200, max_files=3)
        writer.open()
        for i in range(50):
            writer.write("rx", f"test line {i} with some padding data")
        writer.close()
        log_files = sorted(Path(tmpdir).glob("COM10_*.log"))
        check("rotation creates multiple files", len(log_files) > 1)

    # Test 10: JSON-RPC handler
    resp = _handle_request({"method": "initialize", "params": {"protocolVersion": "2025-11-25"}, "id": 1})
    check("initialize works", resp is not None and resp.get("result", {}).get("protocolVersion") == "2025-11-25")

    resp = _handle_request({"method": "tools/list", "params": {}, "id": 2})
    check(
        "tools/list returns every schema",
        resp is not None and len(resp.get("result", {}).get("tools", [])) == len(SERIAL_TOOL_SCHEMAS),
    )

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
