#!/usr/bin/env python3
"""MQTT MCP Server — stdio JSON-RPC server for MQTT pub/sub/debugging.

Exposes MQTT connect/publish/subscribe/message-history as MCP tools.
Follows the same JSON-RPC 2.0 over stdio pattern as the main MCP server.

Usage:
    python mcp/mqtt_server.py              # Start server (stdio)
    python mcp/mqtt_server.py --self-test  # Run self-test

Environment:
    MQTT_ALLOWED_HOSTS  — comma-separated broker hostnames (default: localhost)
    MQTT_DEFAULT_HOST   — default broker host for self-test
    MQTT_DEFAULT_PORT   — default broker port for self-test
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

from mqtt_client import MqttBridge, get_bridge
from mqtt_schemas import MQTT_RESOURCE_SCHEMAS, MQTT_TOOL_SCHEMAS

logger = logging.getLogger(__name__)

# ── Protocol constants ──

PROTOCOL_VERSIONS = ["2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25"]
DEFAULT_PROTOCOL_VERSION = "2025-11-25"
SERVER_INFO = {"name": "mqtt-mcp", "version": "0.1.0"}

# ── Tool implementations ──


def mqtt_connect(args: dict[str, Any]) -> dict[str, Any]:
    """Connect to MQTT broker."""
    bridge = get_bridge()
    return bridge.connect(
        host=args["host"],
        port=args.get("port", 1883),
        client_id=args.get("client_id"),
        username=args.get("username"),
        password=args.get("password"),
        tls=args.get("tls", False),
        keepalive=args.get("keepalive", 60),
        will_topic=args.get("will_topic"),
        will_payload=args.get("will_payload"),
        will_qos=args.get("will_qos", 1),
        will_retain=args.get("will_retain", True),
    )


def mqtt_disconnect(args: dict[str, Any]) -> dict[str, Any]:
    """Disconnect from MQTT broker."""
    bridge = get_bridge()
    return bridge.disconnect()


def mqtt_publish(args: dict[str, Any]) -> dict[str, Any]:
    """Publish a message."""
    bridge = get_bridge()
    return bridge.publish(
        topic=args["topic"],
        payload=args["payload"],
        qos=args.get("qos", 0),
        retain=args.get("retain", False),
    )


def mqtt_subscribe(args: dict[str, Any]) -> dict[str, Any]:
    """Subscribe to a topic."""
    bridge = get_bridge()
    return bridge.subscribe(
        topic=args["topic"],
        qos=args.get("qos", 0),
    )


def mqtt_unsubscribe(args: dict[str, Any]) -> dict[str, Any]:
    """Unsubscribe from a topic."""
    bridge = get_bridge()
    return bridge.unsubscribe(topic=args["topic"])


def mqtt_validate_qos_policy(args: dict[str, Any]) -> dict[str, Any]:
    """Validate QoS/retain use before publishing."""
    return get_bridge().validate_qos_policy(args["message_class"], args["qos"], args["retain"])


def mqtt_verify_retained(args: dict[str, Any]) -> dict[str, Any]:
    """Verify that a broker replays a retained message to a new subscriber."""
    return get_bridge().verify_retained(args["topic"], args.get("expected_payload"), args.get("timeout_seconds", 5))


def mqtt_test_will(args: dict[str, Any]) -> dict[str, Any]:
    """Test a Last Will using isolated probe clients."""
    return get_bridge().test_will(
        args["topic"], args["payload"], args.get("qos", 1),
        args.get("retain", True), args.get("timeout_seconds", 5),
    )


def mqtt_list_topics(args: dict[str, Any]) -> dict[str, Any]:
    """List subscribed topics."""
    bridge = get_bridge()
    return {"ok": True, "topics": bridge.subscribed_topics}


def mqtt_get_messages(args: dict[str, Any]) -> dict[str, Any]:
    """Read message history."""
    bridge = get_bridge()
    messages = bridge.get_messages(
        topic=args.get("topic"),
        limit=args.get("limit", 100),
        since=args.get("since_timestamp"),
    )
    return {"ok": True, "count": len(messages), "messages": messages}


def mqtt_clear_messages(args: dict[str, Any]) -> dict[str, Any]:
    """Clear message history."""
    bridge = get_bridge()
    return bridge.clear_messages(topic=args.get("topic"))


# ── Tool dispatch ──

TOOLS = {
    "mqtt_connect": mqtt_connect,
    "mqtt_disconnect": mqtt_disconnect,
    "mqtt_publish": mqtt_publish,
    "mqtt_subscribe": mqtt_subscribe,
    "mqtt_unsubscribe": mqtt_unsubscribe,
    "mqtt_validate_qos_policy": mqtt_validate_qos_policy,
    "mqtt_verify_retained": mqtt_verify_retained,
    "mqtt_test_will": mqtt_test_will,
    "mqtt_list_topics": mqtt_list_topics,
    "mqtt_get_messages": mqtt_get_messages,
    "mqtt_clear_messages": mqtt_clear_messages,
}

TOOL_SCHEMA_MAP = {s["name"]: s for s in MQTT_TOOL_SCHEMAS}


# ── Resource implementations ──


def get_connection_status() -> dict[str, Any]:
    """Get connection status resource."""
    bridge = get_bridge()
    return {"uri": "mqtt://connection-status", "mimeType": "application/json", "text": json.dumps(bridge.status)}


def get_message_history() -> dict[str, Any]:
    """Get message history resource."""
    bridge = get_bridge()
    messages = bridge.get_messages(limit=100)
    return {"uri": "mqtt://message-history", "mimeType": "application/json", "text": json.dumps(messages)}


def get_subscribed_topics() -> dict[str, Any]:
    """Get subscribed topics resource."""
    bridge = get_bridge()
    return {"uri": "mqtt://subscribed-topics", "mimeType": "application/json", "text": json.dumps(bridge.subscribed_topics)}


RESOURCES = {
    "mqtt://connection-status": get_connection_status,
    "mqtt://message-history": get_message_history,
    "mqtt://subscribed-topics": get_subscribed_topics,
}


# ── MCP helpers ──


def _mcp_result(payload: dict[str, Any]) -> dict[str, Any]:
    """Wrap tool result in MCP content format."""
    return {
        "content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}],
        "isError": not payload.get("ok", True),
    }


def _jsonrpc_error(code: int, message: str, id: Any = None) -> dict[str, Any]:
    """Build JSON-RPC error response."""
    return {"jsonrpc": "2.0", "error": {"code": code, "message": message}, "id": id}


def _jsonrpc_result(result: Any, id: Any) -> dict[str, Any]:
    """Build JSON-RPC success response."""
    return {"jsonrpc": "2.0", "result": result, "id": id}


# ── Request handlers ──


def _handle_request(req: dict[str, Any]) -> dict[str, Any] | None:
    """Handle a single JSON-RPC request."""
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
        return _jsonrpc_result({"tools": MQTT_TOOL_SCHEMAS}, req_id)

    if method == "resources/list":
        return _jsonrpc_result({"resources": MQTT_RESOURCE_SCHEMAS}, req_id)

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
    """Run the MCP server over stdio (JSON-RPC 2.0)."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            response = _jsonrpc_error(-32700, "Parse error")
            print(json.dumps(response), flush=True)
            continue

        # Handle batch requests
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
            response = _jsonrpc_error(-32600, "Invalid request")
            print(json.dumps(response), flush=True)


# ── Self-test ──


def run_self_test() -> int:
    """Run self-test without connecting to a real broker."""
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

    # Test 1: Tool schemas are valid
    check("has tool schemas", len(MQTT_TOOL_SCHEMAS) == 11)
    for schema in MQTT_TOOL_SCHEMAS:
        check(f"schema {schema['name']} has name", "name" in schema)
        check(f"schema {schema['name']} has inputSchema", "inputSchema" in schema)

    # Test 2: Resource schemas are valid
    check("has resource schemas", len(MQTT_RESOURCE_SCHEMAS) == 3)

    # Test 3: All tools are registered
    check("all tools registered", set(TOOLS.keys()) == set(TOOL_SCHEMA_MAP.keys()))

    # Test 4: MqttBridge instantiation
    bridge = MqttBridge(max_messages=10)
    check("bridge created", bridge is not None)
    check("bridge not connected", not bridge.status["connected"])

    # Test 5: Message buffer
    bridge._messages.append({"topic": "test/a", "payload": "hello", "timestamp": 1.0, "qos": 0, "retain": False})
    bridge._messages.append({"topic": "test/b", "payload": "world", "timestamp": 2.0, "qos": 0, "retain": False})
    msgs = bridge.get_messages(topic="test/a")
    check("topic filter works", len(msgs) == 1 and msgs[0]["payload"] == "hello")

    cleared = bridge.clear_messages()
    check("clear works", cleared["ok"] and cleared["cleared"] == 2)

    # Test 6: Ring buffer overflow
    for i in range(15):
        bridge._messages.append({"topic": f"t/{i}", "payload": str(i), "timestamp": float(i), "qos": 0, "retain": False})
    bridge._messages = bridge._messages[-bridge._max_messages:]
    check("ring buffer respects max", len(bridge._messages) <= bridge._max_messages)

    # Test 7: Host allowlist
    check("localhost allowed", bridge._is_host_allowed("localhost"))
    check("127.0.0.1 allowed", bridge._is_host_allowed("127.0.0.1"))
    check("evil.com blocked", not bridge._is_host_allowed("evil.com"))

    # Test 8: QoS policy keeps retained availability separate from commands.
    check("availability QoS policy accepted", bridge.validate_qos_policy("availability", 1, True)["ok"])
    check("unsafe retained command rejected", not bridge.validate_qos_policy("command", 1, True)["ok"])

    # Test 9: JSON-RPC handler
    resp = _handle_request({"method": "initialize", "params": {"protocolVersion": "2025-11-25"}, "id": 1})
    check("initialize works", resp is not None and resp.get("result", {}).get("protocolVersion") == "2025-11-25")

    resp = _handle_request({"method": "tools/list", "params": {}, "id": 2})
    check("tools/list returns schemas", resp is not None and len(resp.get("result", {}).get("tools", [])) == 11)

    resp = _handle_request({"method": "resources/list", "params": {}, "id": 3})
    check("resources/list returns schemas", resp is not None and len(resp.get("result", {}).get("resources", [])) == 3)

    resp = _handle_request({"method": "ping", "params": {}, "id": 4})
    check("ping works", resp is not None and "result" in resp)

    resp = _handle_request({"method": "unknown_method", "params": {}, "id": 5})
    check("unknown method returns error", resp is not None and resp.get("error", {}).get("code") == -32601)

    # Test 9: Tool call without connection
    resp = _handle_request({"method": "tools/call", "params": {"name": "mqtt_publish", "arguments": {"topic": "t", "payload": "x"}}, "id": 6})
    check("publish without connection returns error", resp is not None)
    if resp:
        result = resp.get("result", {})
        content = result.get("content", [{}])
        if content:
            inner = json.loads(content[0].get("text", "{}"))
            check("error message mentions not connected", "not connected" in inner.get("error", "").lower())

    resp = _handle_request({"method": "tools/call", "params": {"name": "mqtt_validate_qos_policy", "arguments": {"message_class": "ota", "qos": 1, "retain": False}}, "id": 7})
    check("QoS policy JSON-RPC path works", resp is not None and not resp.get("result", {}).get("isError", True))

    print(f"\nSelf-test: {passed} passed, {failed} failed")
    return 0 if failed == 0 else 1


# ── CLI ──


def main() -> int:
    parser = argparse.ArgumentParser(description="MQTT MCP Server")
    parser.add_argument("--self-test", action="store_true", help="Run self-test")
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    serve_stdio()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
