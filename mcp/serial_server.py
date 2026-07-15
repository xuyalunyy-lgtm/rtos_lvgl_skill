#!/usr/bin/env python3
"""Serial MCP Server — stdio JSON-RPC server for serial port debugging.

Exposes serial connect/read/write/search as MCP tools.
All data is stored locally in a ring buffer; AI pulls on demand (no token waste).

Usage:
    python mcp/serial_server.py              # Start server (stdio)
    python mcp/serial_server.py --self-test  # Run self-test

Environment:
    SERIAL_LOG_DIR        — optional directory for persistent RX/TX session logs
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import threading
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from serial_client import SerialBridge, get_bridge
from serial_schemas import SERIAL_RESOURCE_SCHEMAS, SERIAL_TOOL_SCHEMAS
from mcp_runtime import (
    AuditTrail,
    CancellationRegistry,
    jsonrpc_error as _runtime_jsonrpc_error,
    jsonrpc_result as _runtime_jsonrpc_result,
    mcp_result as _runtime_mcp_result,
    serve_stdio as _runtime_serve_stdio,
    validate_tool_arguments as _runtime_validate_tool_arguments,
)

logger = logging.getLogger(__name__)

# ── Protocol constants ──

PROTOCOL_VERSIONS = ["2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25"]
DEFAULT_PROTOCOL_VERSION = "2025-11-25"
SERVER_INFO = {"name": "serial-mcp", "version": "0.1.0"}
_CANCELLATIONS = CancellationRegistry()
_AUDIT = AuditTrail("serial")


def _register_cancellation(request_id: Any) -> threading.Event:
    return _CANCELLATIONS.register(request_id)


def _finish_cancellation(request_id: Any) -> None:
    _CANCELLATIONS.finish(request_id)


def _cancel_request(request_id: Any) -> None:
    _CANCELLATIONS.cancel(request_id)


def _validate_tool_arguments(tool_name: str, arguments: dict[str, Any]) -> list[str]:
    return _runtime_validate_tool_arguments(TOOL_SCHEMA_MAP, tool_name, arguments)

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
        auto_reconnect=args.get("auto_reconnect", True),
    )


def serial_disconnect(args: dict[str, Any]) -> dict[str, Any]:
    """Disconnect from serial port."""
    bridge = get_bridge()
    return bridge.disconnect()


def serial_session_start(args: dict[str, Any]) -> dict[str, Any]:
    """Start a persistent receive-only serial session."""
    bridge = get_bridge()
    return bridge.start_session(
        port=args["port"],
        baudrate=args.get("baudrate", 115200),
        bytesize=args.get("bytesize", 8),
        parity=args.get("parity", "N"),
        stopbits=args.get("stopbits", 1),
        auto_reconnect=args.get("auto_reconnect", True),
    )


def serial_session_poll(args: dict[str, Any]) -> dict[str, Any]:
    """Read only lines received since the caller's previous poll."""
    bridge = get_bridge()
    return bridge.poll_session(
        after_sequence=args.get("after_sequence", 0),
        n=args.get("n", 200),
    )


def serial_session_stop(args: dict[str, Any]) -> dict[str, Any]:
    """Stop the persistent serial session and release its port."""
    bridge = get_bridge()
    return bridge.disconnect()


def serial_request(args: dict[str, Any], *, cancel_event: threading.Event | None = None) -> dict[str, Any]:
    """Send a command and wait for a matching response."""
    bridge = get_bridge()
    return bridge.request(
        command=args["command"],
        expect=args["expect"],
        timeout=args.get("timeout", 5.0),
        newline=args.get("newline", "\r\n"),
        context_lines=args.get("context_lines", 5),
        cancel_event=cancel_event,
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
        case_sensitive=args.get("case_sensitive", True),
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
    "serial_session_start": serial_session_start,
    "serial_session_poll": serial_session_poll,
    "serial_session_stop": serial_session_stop,
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
    return _runtime_mcp_result(payload)


def _jsonrpc_error(code: int, message: str, id: Any = None) -> dict[str, Any]:
    return _runtime_jsonrpc_error(code, message, id)


def _jsonrpc_result(result: Any, id: Any) -> dict[str, Any]:
    return _runtime_jsonrpc_result(result, id)


# ── Request handlers ──


def _handle_request(req: dict[str, Any]) -> dict[str, Any] | None:
    method = req.get("method", "")
    params = req.get("params", {})
    req_id = req.get("id")

    if method == "notifications/initialized":
        return None

    if method == "notifications/cancelled":
        if not isinstance(params, dict):
            return None
        cancelled_id = params.get("requestId", params.get("request_id", params.get("id")))
        if cancelled_id is not None:
            _cancel_request(cancelled_id)
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
        if not isinstance(params, dict):
            return _jsonrpc_error(-32602, "Tool call params must be an object", req_id)
        tool_name = params.get("name", "")
        tool_args = params.get("arguments", {})
        handler = TOOLS.get(tool_name)
        if not handler:
            return _jsonrpc_error(-32602, f"Unknown tool: {tool_name}", req_id)
        if not isinstance(tool_args, dict):
            return _jsonrpc_error(-32602, "Arguments must be an object", req_id)
        errors = _validate_tool_arguments(tool_name, tool_args)
        if errors:
            _AUDIT.record("tool_rejected", request_id=req_id, tool=tool_name, arguments=tool_args, errors=errors)
            return _jsonrpc_error(-32602, f"Invalid arguments for {tool_name}: {'; '.join(errors)}", req_id)
        cancel_event: threading.Event | None = None
        if tool_name == "serial_request" and req_id is not None:
            cancel_event = _register_cancellation(req_id)
        try:
            _AUDIT.record("tool_call", request_id=req_id, tool=tool_name, arguments=tool_args)
            result = handler(tool_args, cancel_event=cancel_event) if tool_name == "serial_request" else handler(tool_args)
            _AUDIT.record("tool_result", request_id=req_id, tool=tool_name, ok=result.get("ok", True))
            return _jsonrpc_result(_mcp_result(result), req_id)
        except Exception as e:
            logger.exception("Tool %s failed", tool_name)
            _AUDIT.record("tool_error", request_id=req_id, tool=tool_name, error=str(e))
            return _jsonrpc_result(_mcp_result({"ok": False, "error": str(e)}), req_id)
        finally:
            if cancel_event is not None:
                _finish_cancellation(req_id)

    return _jsonrpc_error(-32601, f"Method not found: {method}", req_id)


# ── Main loop ──


def _is_cancellable_tool_call(message: dict[str, Any]) -> bool:
    params = message.get("params")
    return (
        message.get("method") == "tools/call"
        and isinstance(params, dict)
        and params.get("name") == "serial_request"
        and message.get("id") is not None
    )


def serve_stdio() -> None:
    _runtime_serve_stdio(_handle_request, _is_cancellable_tool_call)


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

    # Test 11: Every serial tool reaches its JSON-RPC tools/call path.
    tool_cases = [
        ("serial_list", {}),
        ("serial_connect", {"port": "INVALID_PORT"}),
        ("serial_disconnect", {}),
        ("serial_session_start", {"port": "INVALID_PORT"}),
        ("serial_session_poll", {"after_sequence": 0, "n": 10}),
        ("serial_session_stop", {}),
        ("serial_write", {"data": "AT"}),
        ("serial_request", {"command": "AT", "expect": "OK", "timeout": 0.1}),
        ("serial_get_lines", {}),
        ("serial_search", {"keyword": "ERROR", "case_sensitive": False}),
        ("serial_check_device", {}),
        ("serial_get_stats", {}),
        ("serial_watch", {"action": "status"}),
        ("serial_bookmark", {"label": "self-test"}),
        ("serial_export_bundle", {}),
        ("serial_summary", {"n": 50}),
    ]
    for index, (tool_name, arguments) in enumerate(tool_cases, start=6):
        resp = _handle_request({
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
            "id": index,
        })
        content = resp.get("result", {}).get("content", []) if resp else []
        check(f"{tool_name} JSON-RPC path", bool(content) and content[0].get("type") == "text")

    # Test 12: Input schemas reject wrong types, missing fields, and unknown keys.
    resp = _handle_request({
        "method": "tools/call",
        "params": {"name": "serial_connect", "arguments": {"port": 123}},
        "id": 30,
    })
    check("input schema rejects wrong type", resp is not None and resp.get("error", {}).get("code") == -32602)
    resp = _handle_request({
        "method": "tools/call",
        "params": {"name": "serial_write", "arguments": {}},
        "id": 31,
    })
    check("input schema rejects missing field", resp is not None and resp.get("error", {}).get("code") == -32602)
    resp = _handle_request({
        "method": "tools/call",
        "params": {"name": "serial_get_stats", "arguments": {"unexpected": True}},
        "id": 32,
    })
    check("input schema rejects unknown field", resp is not None and resp.get("error", {}).get("code") == -32602)

    # Test 13: notifications/cancelled reaches the request-specific event.
    cancel_id = "self-test-cancel"
    cancellation = _register_cancellation(cancel_id)
    resp = _handle_request({"method": "notifications/cancelled", "params": {"requestId": cancel_id}})
    check("cancel notification is acknowledged", resp is None and cancellation.is_set())
    _finish_cancellation(cancel_id)

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
