"""Shared JSON-RPC safety runtime for the local MCP servers.

This module deliberately contains no transport or device business logic.  It
provides the common protocol boundary: JSON-schema validation, cancellation
tokens, fragmented-stdio buffering, and redacted optional audit records.
"""
from __future__ import annotations

import json
import os
import re
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable, Iterable

_SENSITIVE_KEY = re.compile(r"(?:password|token|secret|api[_-]?key|authorization|private[_-]?key)", re.IGNORECASE)
_SENSITIVE_TEXT = re.compile(r"(?i)(password|token|secret|api[_-]?key)\s*[:=]\s*[^\s,;]+|bearer\s+[^\s,;]+")


def redact(value: Any) -> Any:
    """Recursively remove credentials from MCP output and audit events."""
    if isinstance(value, dict):
        return {key: "[REDACTED]" if _SENSITIVE_KEY.search(str(key)) else redact(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, tuple):
        return [redact(item) for item in value]
    if isinstance(value, str):
        return _SENSITIVE_TEXT.sub(lambda match: f"{match.group(1)}=[REDACTED]", value)
    return value


def mcp_result(payload: dict[str, Any]) -> dict[str, Any]:
    safe_payload = redact(payload)
    return {
        "content": [{"type": "text", "text": json.dumps(safe_payload, ensure_ascii=False)}],
        "isError": not payload.get("ok", True),
    }


def jsonrpc_error(code: int, message: str, request_id: Any = None) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "error": {"code": code, "message": message}, "id": request_id}


def jsonrpc_result(result: Any, request_id: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "result": result, "id": request_id}


def validate_schema_value(schema: dict[str, Any], value: Any, path: str = "arguments") -> list[str]:
    """Validate the JSON-Schema subset used by the bundled MCP schemas."""
    expected = schema.get("type")
    type_ok = {
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "boolean": isinstance(value, bool),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "number": isinstance(value, (int, float)) and not isinstance(value, bool),
    }
    if expected and not type_ok.get(expected, True):
        return [f"{path} must be {expected}"]
    errors: list[str] = []
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path} must be one of {schema['enum']}")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path} must be >= {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path} must be <= {schema['maximum']}")
    if isinstance(value, dict):
        properties = schema.get("properties", {})
        errors.extend(f"{path}.{name} is required" for name in schema.get("required", []) if name not in value)
        if schema.get("additionalProperties") is False:
            errors.extend(f"{path}.{name} is not allowed" for name in sorted(set(value) - set(properties)))
        for name, item in value.items():
            if name in properties:
                errors.extend(validate_schema_value(properties[name], item, f"{path}.{name}"))
    return errors


def validate_tool_arguments(schema_map: dict[str, dict[str, Any]], tool_name: str, arguments: dict[str, Any]) -> list[str]:
    return validate_schema_value(schema_map[tool_name]["inputSchema"], arguments)


def request_key(request_id: Any) -> str:
    return json.dumps(request_id, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class CancellationRegistry:
    """Request-ID keyed cancellation events shared by long-running tools."""

    def __init__(self) -> None:
        self._active: dict[str, threading.Event] = {}
        self._early: set[str] = set()
        self._lock = threading.Lock()

    def register(self, request_id: Any) -> threading.Event:
        key = request_key(request_id)
        event = threading.Event()
        with self._lock:
            if key in self._early:
                self._early.remove(key)
                event.set()
            self._active[key] = event
        return event

    def cancel(self, request_id: Any) -> None:
        key = request_key(request_id)
        with self._lock:
            event = self._active.get(key)
            if event is None:
                self._early.add(key)
            else:
                event.set()

    def finish(self, request_id: Any) -> None:
        with self._lock:
            self._active.pop(request_key(request_id), None)


class AuditTrail:
    """Optional local JSONL audit trail; credentials are redacted before write."""

    def __init__(self, server_name: str, directory: str | Path | None = None) -> None:
        configured = directory or os.environ.get("MCP_AUDIT_LOG_DIR")
        self._path = Path(configured) / f"{server_name}-audit.jsonl" if configured else None
        self._lock = threading.Lock()

    def record(self, event: str, **fields: Any) -> None:
        if self._path is None:
            return
        entry = redact({"timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "event": event, **fields})
        try:
            with self._lock:
                self._path.parent.mkdir(parents=True, exist_ok=True)
                with self._path.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(entry, ensure_ascii=False, separators=(",", ":")) + "\n")
        except OSError:
            # Audit logging must never make a device-control call unavailable.
            return


class JsonMessageBuffer:
    """Accumulate fragmented or pretty-printed JSON-RPC messages safely."""

    def __init__(self) -> None:
        self._buffer = ""
        self._decoder = json.JSONDecoder()

    def feed(self, chunk: str, final: bool = False) -> Iterable[Any | dict[str, str]]:
        self._buffer += chunk
        messages: list[Any | dict[str, str]] = []
        while self._buffer.strip():
            leading = len(self._buffer) - len(self._buffer.lstrip())
            candidate = self._buffer[leading:]
            try:
                value, end = self._decoder.raw_decode(candidate)
            except json.JSONDecodeError:
                # Input may arrive line-by-line or in arbitrary pipe chunks.
                # Hold all incomplete data until EOF rather than rejecting a
                # pretty-printed or fragmented request midway through.
                if final:
                    messages.append({"_parse_error": "Parse error"})
                    self._buffer = ""
                break
            messages.append(value)
            self._buffer = candidate[end:]
        return messages


def serve_stdio(
    handle_request: Callable[[dict[str, Any]], dict[str, Any] | None],
    is_async_request: Callable[[dict[str, Any]], bool] | None = None,
) -> None:
    """Serve JSON-RPC with fragmented-input buffering and serialized output."""
    output_lock = threading.Lock()
    parser = JsonMessageBuffer()

    def write(response: Any) -> None:
        with output_lock:
            print(json.dumps(redact(response), ensure_ascii=False), flush=True)

    def dispatch(message: Any) -> None:
        if isinstance(message, dict) and "_parse_error" in message:
            write(jsonrpc_error(-32700, "Parse error"))
            return
        if isinstance(message, list):
            responses = [response for item in message if isinstance(item, dict) and "method" in item
                         if (response := handle_request(item)) is not None]
            if responses:
                write(responses)
            return
        if not isinstance(message, dict) or "method" not in message:
            write(jsonrpc_error(-32600, "Invalid request"))
            return
        if is_async_request and is_async_request(message):
            threading.Thread(target=lambda: _dispatch_async(message), daemon=True).start()
            return
        response = handle_request(message)
        if response is not None:
            write(response)

    def _dispatch_async(message: dict[str, Any]) -> None:
        response = handle_request(message)
        if response is not None:
            write(response)

    for chunk in sys.stdin:
        for message in parser.feed(chunk):
            dispatch(message)
    for message in parser.feed("", final=True):
        dispatch(message)
