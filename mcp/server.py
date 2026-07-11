#!/usr/bin/env python3
"""Lightweight MCP adapter for the FreeRTOS Embedded Architect skill.

This server is intentionally thin: it exposes stable tool entrypoints and
executes the existing repository scripts without duplicating checker logic.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

# Ensure mcp/ directory is on sys.path so lvgl_ui imports regardless of cwd
_MCP_DIR = str(Path(__file__).resolve().parent)
if _MCP_DIR not in sys.path:
    sys.path.insert(0, _MCP_DIR)

from lvgl_ui import LVGL_TOOL_SCHEMAS, LVGL_TOOLS, RESOURCE_SCHEMAS, RESOURCE_URIS, get_resource_content

ROOT = Path(__file__).resolve().parent.parent
PYTHON = sys.executable

# Codex clients may negotiate any of these MCP revisions.  The server must
# reply with the version selected for this connection, rather than always
# advertising the newest version it knows about.
SUPPORTED_MCP_PROTOCOL_VERSIONS = {
    "2024-11-05",
    "2025-03-26",
    "2025-06-18",
    "2025-11-25",
    "2026-07-28",
}
DEFAULT_MCP_PROTOCOL_VERSION = "2025-11-25"
TRACE_ENV = "FREERTOS_MCP_TRACE_PATH"

WORKFLOWS = {
    "code_review",
    "project_review",
    "crash_debug",
    "memory_analysis",
    "sdk_trim",
    "new_module",
    "bring_up",
    "lvgl_page",
    "hw_sw_debug",
}
PLATFORMS = {"esp32", "stm32", "jl", "bk", "zephyr"}
ROUTER_PLATFORMS = {"esp32", "stm32", "jl", "bk"}
RTOSES = {"freertos", "zephyr"}
BUDGETS = {"compact", "standard", "full"}
GATES = {"quick", "full"}


def _env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    return env


def _trace(event: str, **fields: Any) -> None:
    """Append minimal stdio lifecycle diagnostics when explicitly enabled.

    Trace data never enters MCP stdout and deliberately omits request arguments
    and response contents, which can include user paths or generated artifacts.
    """
    raw_path = os.getenv(TRACE_ENV)
    if not raw_path:
        return
    try:
        path = Path(raw_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {"event": event, **fields}
        with path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        # Tracing must never interfere with the stdio protocol.
        pass


def _jsonable_stdout(stdout: str) -> Any:
    text = stdout.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _run(argv: list[str], *, timeout: int = 180) -> dict[str, Any]:
    proc = subprocess.run(
        argv,
        cwd=ROOT,
        env=_env(),
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    parsed = _jsonable_stdout(proc.stdout)
    return {
        "ok": proc.returncode == 0,
        "command": argv,
        "exit_code": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "data": parsed,
        "artifacts": [],
    }


def _require_choice(name: str, value: str, allowed: set[str]) -> None:
    if value not in allowed:
        raise ValueError(f"{name} must be one of {sorted(allowed)}, got {value!r}")


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part for part in value.replace(",", " ").split() if part]
    if isinstance(value, list):
        return [str(item) for item in value]
    raise ValueError("constraints must be a list or string")


def list_capabilities(_: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "ok": True,
        "tools": sorted(HIGH_LEVEL_TOOLS.keys()),
        "resources": sorted(RESOURCE_URIS),
        "workflows": sorted(WORKFLOWS),
        "platforms": sorted(PLATFORMS),
        "router_platforms": sorted(ROUTER_PLATFORMS),
        "rtos": sorted(RTOSES),
        "gates": sorted(GATES),
    }


def route_context(args: dict[str, Any]) -> dict[str, Any]:
    workflow = str(args.get("workflow", "code_review"))
    platform = str(args.get("platform", "esp32"))
    rtos = str(args.get("rtos", "freertos"))
    budget = str(args.get("budget", "compact"))
    constraints = _as_list(args.get("constraints"))

    _require_choice("workflow", workflow, WORKFLOWS)
    _require_choice("platform", platform, ROUTER_PLATFORMS)
    _require_choice("rtos", rtos, RTOSES)
    _require_choice("budget", budget, BUDGETS)

    cmd = [
        PYTHON,
        "tools/context_router.py",
        "--workflow",
        workflow,
        "--platform",
        platform,
        "--rtos",
        rtos,
        "--budget",
        budget,
        "--json",
    ]
    if constraints:
        cmd.append("--constraints")
        cmd.extend(constraints)
    return _run(cmd, timeout=60)


def run_review(args: dict[str, Any]) -> dict[str, Any]:
    path = args.get("path")
    platform = str(args.get("platform", "freertos"))
    strict = bool(args.get("strict", False))
    suggest_fixes = bool(args.get("suggest_fixes", False))
    fix_detail = str(args.get("fix_detail", "summary"))

    _require_choice("platform", platform, PLATFORMS | {"freertos"})
    _require_choice("fix_detail", fix_detail, {"summary", "full"})
    if not path:
        raise ValueError("path is required")

    target = Path(str(path))
    cmd = [PYTHON, "tools/run_review.py", "--platform", platform, "--json"]
    if strict:
        cmd.append("--strict-field")
    if suggest_fixes:
        cmd.extend(["--suggest-fixes", "--fix-detail", fix_detail])
    if target.exists() and target.is_dir():
        cmd.extend(["--dir", str(target)])
    else:
        cmd.append(str(target))
    return _run(cmd, timeout=180)


def triage_log(args: dict[str, Any]) -> dict[str, Any]:
    log_path = args.get("log_path")
    platform = str(args.get("platform", ""))
    if not log_path:
        raise ValueError("log_path is required")

    cmd = [PYTHON, "tools/log_triage.py", "--log", str(log_path), "--json"]
    if platform:
        cmd.extend(["--platform", platform])
    result = _run(cmd, timeout=60)
    result["rtos"] = str(args.get("rtos", ""))
    return result


def lookup_sdk(args: dict[str, Any]) -> dict[str, Any]:
    platform = str(args.get("platform", "esp32"))
    query = str(args.get("query", "")).strip()
    mode = str(args.get("mode", "auto"))
    _require_choice("platform", platform, PLATFORMS)
    _require_choice("mode", mode, {"auto", "info", "category", "list", "regex", "all_ops", "all_categories"})

    base = [PYTHON, "tools/sdk_lookup.py", "--platform", platform]
    if mode == "all_ops":
        return _run(base + ["--all-ops"], timeout=60)
    if mode == "all_categories":
        return _run(base + ["--all-categories"], timeout=60)
    if not query:
        raise ValueError("query is required unless mode is all_ops or all_categories")
    if mode == "info":
        return _run(base + ["--info", query], timeout=60)
    if mode == "category":
        return _run(base + ["--category", query], timeout=60)
    if mode == "list":
        return _run(base + ["--list", query], timeout=60)
    if mode == "regex":
        return _run(base + ["--regex", query], timeout=60)

    result = _run(base + ["--info", query], timeout=60)
    if result["ok"]:
        result["lookup_mode"] = "info"
        return result
    fallback = _run(base + ["--category", query], timeout=60)
    fallback["lookup_mode"] = "category"
    fallback["info_attempt"] = result
    return fallback


def run_gate(args: dict[str, Any]) -> dict[str, Any]:
    level = str(args.get("level", "quick"))
    strict = bool(args.get("strict", False))
    _require_choice("level", level, GATES)
    if level == "quick":
        cmd = [PYTHON, "scripts/quick_gate.py"]
        if strict:
            cmd.append("--strict")
        return _run(cmd, timeout=240)
    return _run([PYTHON, "scripts/skill_iterate.py", "--check"], timeout=300)


# Internal tools (not exposed via tools/list, but callable)
INTERNAL_TOOLS = {
    "list_capabilities": list_capabilities,
    "route_context": route_context,
    "run_review": run_review,
    "triage_log": triage_log,
    "lookup_sdk": lookup_sdk,
    "run_gate": run_gate,
}

# Import high-level LVGL tools (6 tools - public surface)
try:
    from high_level_tools import HIGH_LEVEL_TOOLS
    from high_level_schemas import HIGH_LEVEL_SCHEMAS
except ImportError:
    from .high_level_tools import HIGH_LEVEL_TOOLS
    from .high_level_schemas import HIGH_LEVEL_SCHEMAS

# TOOLS = internal + high-level (all callable)
TOOLS = {**INTERNAL_TOOLS, **HIGH_LEVEL_TOOLS}

# TOOL_SCHEMAS = only high-level tools (exposed to model)
TOOL_SCHEMAS: list[dict[str, Any]] = HIGH_LEVEL_SCHEMAS
TOOL_SCHEMA_BY_NAME = {schema["name"]: schema.get("inputSchema", {}) for schema in TOOL_SCHEMAS}


def _mcp_result(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(payload, ensure_ascii=False, indent=2),
            }
        ],
        "isError": not bool(payload.get("ok", True)),
    }


def _negotiate_protocol_version(params: Any) -> str:
    """Select the MCP revision for one initialized stdio connection."""
    if isinstance(params, dict):
        requested = params.get("protocolVersion")
        if isinstance(requested, str) and requested in SUPPORTED_MCP_PROTOCOL_VERSIONS:
            return requested
    return DEFAULT_MCP_PROTOCOL_VERSION


def _tool_error(tool: str, code: str, message: str, *, details: list[str] | None = None) -> dict[str, Any]:
    error: dict[str, Any] = {
        "code": code,
        "message": message,
        "tool": tool,
    }
    if details:
        error["details"] = details
    return {"ok": False, "error": error, "artifacts": []}


def _schema_types(schema: dict[str, Any]) -> set[str]:
    raw = schema.get("type")
    if raw is None:
        return set()
    if isinstance(raw, list):
        return {str(item) for item in raw}
    return {str(raw)}


def _type_matches(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return True


def _validate_schema_value(path: str, value: Any, schema: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    expected = _schema_types(schema)
    if expected and not any(_type_matches(value, item) for item in expected):
        errors.append(f"{path} must be one of {sorted(expected)}, got {type(value).__name__}")
        return errors

    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path} must be one of {schema['enum']}, got {value!r}")

    if isinstance(value, dict):
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        for key in required:
            if key not in value:
                errors.append(f"{path}.{key} is required")
        if schema.get("additionalProperties") is False:
            extra = sorted(set(value) - set(properties))
            if extra:
                errors.append(f"{path} has unknown field(s): {', '.join(extra)}")
        for key, item in value.items():
            item_schema = properties.get(key)
            if isinstance(item_schema, dict):
                errors.extend(_validate_schema_value(f"{path}.{key}", item, item_schema))

    if isinstance(value, list):
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                errors.extend(_validate_schema_value(f"{path}[{index}]", item, item_schema))

    return errors


def _validate_tool_args(name: str, args: Any) -> list[str]:
    schema = TOOL_SCHEMA_BY_NAME.get(name, {"type": "object"})
    return _validate_schema_value("arguments", args, schema)


def _call_tool(name: str, args: Any) -> dict[str, Any]:
    if name not in TOOLS:
        return _tool_error(str(name), "unknown_tool", f"unknown tool: {name}")
    if not isinstance(args, dict):
        return _tool_error(str(name), "invalid_arguments", "tool arguments must be an object")
    validation_errors = _validate_tool_args(str(name), args)
    if validation_errors:
        return _tool_error(str(name), "invalid_arguments", "tool arguments failed schema validation", details=validation_errors)
    try:
        payload = TOOLS[name](args)
    except Exception as exc:
        return _tool_error(str(name), "tool_exception", str(exc))
    if isinstance(payload, dict):
        return payload
    return {"ok": True, "data": payload, "artifacts": []}


def _handle_request(message: dict[str, Any]) -> dict[str, Any] | None:
    method = message.get("method")
    msg_id = message.get("id")
    _trace("request", method=str(method), has_id=msg_id is not None)
    try:
        if method == "initialize":
            result = {
                "protocolVersion": _negotiate_protocol_version(message.get("params")),
                "capabilities": {"tools": {}, "resources": {}},
                "serverInfo": {"name": "freertos-embedded-architect-mcp", "version": "0.2.1"},
            }
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            result = {"tools": TOOL_SCHEMAS}
        elif method == "resources/list":
            result = {"resources": RESOURCE_SCHEMAS}
        elif method == "resources/read":
            params = message.get("params") or {}
            uri = str(params.get("uri", ""))
            result = {"contents": [get_resource_content(uri)]}
        elif method == "tools/call":
            params = message.get("params") or {}
            name = params.get("name")
            args = params.get("arguments") or {}
            result = _mcp_result(_call_tool(str(name), args))
        elif method == "notifications/initialized":
            return None
        else:
            return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32601, "message": f"Method not found: {method}"}}
        return {"jsonrpc": "2.0", "id": msg_id, "result": result}
    except Exception as exc:  # MCP errors must still be JSON-RPC responses.
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {"code": -32000, "message": str(exc)},
        }


def serve_stdio() -> int:
    _trace("server_started", pid=os.getpid(), cwd=str(Path.cwd()))
    for line in sys.stdin:
        _trace("stdin_line", bytes=len(line.encode("utf-8", errors="replace")))
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError as exc:
            _trace("invalid_json")
            response = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": str(exc)}}
            print(json.dumps(response, ensure_ascii=False), flush=True)
            continue
        # Handle batch requests (JSON-RPC array)
        if isinstance(message, list):
            responses = []
            for msg in message:
                if not isinstance(msg, dict):
                    responses.append({"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "Invalid Request: batch item must be object"}})
                    continue
                resp = _handle_request(msg)
                if resp is not None:
                    responses.append(resp)
            if responses:
                _trace("response", batch=True, count=len(responses))
                print(json.dumps(responses, ensure_ascii=False), flush=True)
            continue
        if not isinstance(message, dict):
            response = {"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "Invalid Request: must be object or array"}}
            print(json.dumps(response, ensure_ascii=False), flush=True)
            continue
        response = _handle_request(message)
        if response is not None:
            _trace("response", batch=False, bytes=len(json.dumps(response, ensure_ascii=False).encode("utf-8")))
            print(json.dumps(response, ensure_ascii=False), flush=True)
    return 0


def run_self_test() -> int:
    """Self-test using only the6 high-level tools."""
    checks: list[tuple[str, bool, str]] = []

    # 1. list_capabilities
    caps = list_capabilities({})
    checks.append(("list_capabilities", caps.get("ok") is True, "list_capabilities failed"))
    tool_names = set(caps.get("tools", []))
    expected_tools = {"inspect_design", "generate_ui", "render_ui", "compare_ui", "refine_ui", "apply_patch"}
    checks.append(("high_level_tools_present", expected_tools.issubset(tool_names), f"missing tools: {expected_tools - tool_names}"))

    # 2. route_context
    route = route_context({"workflow": "code_review", "platform": "esp32", "rtos": "freertos"})
    route_data = route.get("data", {})
    checks.append(("route_context", route.get("ok") is True and isinstance(route_data.get("required_files"), list), "route_context failed"))

    # 3. Invalid route_context (argument validation)
    try:
        bad_route = route_context({"workflow": "not_a_workflow", "platform": "esp32"})
        checks.append(("route_context_invalid", bad_route.get("ok") is False or "error" in bad_route, "invalid workflow not rejected"))
    except ValueError:
        checks.append(("route_context_invalid", True, "ValueError raised for invalid workflow"))

    # 4. lookup_sdk
    sdk = lookup_sdk({"platform": "esp32", "query": "TASK_CREATE"})
    checks.append(("lookup_sdk", sdk.get("ok") is True and "xTaskCreate" in sdk.get("stdout", ""), "lookup_sdk failed"))

    # 5. Tool count (should be 6 high-level tools only)
    checks.append(("tool_count", len(tool_names) == 6, f"expected 6 tools, got {len(tool_names)}"))

    # 6. MCP initialize must use the client-requested compatible revision.
    initialize = _handle_request({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {"protocolVersion": "2025-06-18"},
    })
    negotiated = initialize.get("result", {}).get("protocolVersion") if isinstance(initialize, dict) else None
    checks.append(("protocol_version_negotiation", negotiated == "2025-06-18", f"negotiated {negotiated!r}"))

    failed = [item for item in checks if not item[1]]
    for name, ok, detail in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f": {detail}" if not ok else ""))
    if failed:
        return 1
    print("[mcp:self-test] all fixtures passed")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="FreeRTOS Embedded Architect MCP adapter")
    parser.add_argument("--self-test", action="store_true", help="run wrapper self-tests")
    args = parser.parse_args()
    if args.self_test:
        return run_self_test()
    return serve_stdio()


if __name__ == "__main__":
    raise SystemExit(main())
