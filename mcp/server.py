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

ROOT = Path(__file__).resolve().parent.parent
PYTHON = sys.executable

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
        "tools": sorted(TOOLS),
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


TOOLS = {
    "list_capabilities": list_capabilities,
    "route_context": route_context,
    "run_review": run_review,
    "triage_log": triage_log,
    "lookup_sdk": lookup_sdk,
    "run_gate": run_gate,
}

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "list_capabilities",
        "description": "List supported workflows, platforms, RTOS choices, gates, and MCP tools.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "route_context",
        "description": "Build the minimal context load plan using tools/context_router.py.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "workflow": {"type": "string", "enum": sorted(WORKFLOWS)},
                "platform": {"type": "string", "enum": sorted(ROUTER_PLATFORMS)},
                "rtos": {"type": "string", "enum": sorted(RTOSES), "default": "freertos"},
                "constraints": {"type": "array", "items": {"type": "string"}},
                "budget": {"type": "string", "enum": sorted(BUDGETS), "default": "compact"},
            },
            "required": ["workflow", "platform"],
            "additionalProperties": False,
        },
    },
    {
        "name": "run_review",
        "description": "Run the static review pipeline against a file or directory using tools/run_review.py.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "platform": {"type": "string", "enum": sorted(PLATFORMS | {"freertos"}), "default": "freertos"},
                "strict": {"type": "boolean", "default": False},
                "suggest_fixes": {"type": "boolean", "default": False},
                "fix_detail": {"type": "string", "enum": ["summary", "full"], "default": "summary"},
            },
            "required": ["path"],
            "additionalProperties": False,
        },
    },
    {
        "name": "triage_log",
        "description": "Classify a firmware log using tools/log_triage.py.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "log_path": {"type": "string"},
                "platform": {"type": "string", "default": ""},
                "rtos": {"type": "string", "default": ""},
            },
            "required": ["log_path"],
            "additionalProperties": False,
        },
    },
    {
        "name": "lookup_sdk",
        "description": "Query normalized SDK operation mappings using tools/sdk_lookup.py.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "platform": {"type": "string", "enum": sorted(PLATFORMS)},
                "query": {"type": "string"},
                "mode": {"type": "string", "enum": ["auto", "info", "category", "list", "regex", "all_ops", "all_categories"], "default": "auto"},
            },
            "required": ["platform"],
            "additionalProperties": False,
        },
    },
    {
        "name": "run_gate",
        "description": "Run the quick or full skill validation gate.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "level": {"type": "string", "enum": sorted(GATES), "default": "quick"},
                "strict": {"type": "boolean", "default": False},
            },
            "additionalProperties": False,
        },
    },
]


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


def _handle_request(message: dict[str, Any]) -> dict[str, Any] | None:
    method = message.get("method")
    msg_id = message.get("id")
    try:
        if method == "initialize":
            result = {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "freertos-embedded-architect-mcp", "version": "0.1.0"},
            }
        elif method == "tools/list":
            result = {"tools": TOOL_SCHEMAS}
        elif method == "tools/call":
            params = message.get("params") or {}
            name = params.get("name")
            args = params.get("arguments") or {}
            if name not in TOOLS:
                raise ValueError(f"unknown tool: {name}")
            result = _mcp_result(TOOLS[name](args))
        elif method == "notifications/initialized":
            return None
        else:
            raise ValueError(f"unsupported method: {method}")
        return {"jsonrpc": "2.0", "id": msg_id, "result": result}
    except Exception as exc:  # MCP errors must still be JSON-RPC responses.
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {"code": -32000, "message": str(exc)},
        }


def serve_stdio() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError as exc:
            response = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": str(exc)}}
        else:
            response = _handle_request(message)
        if response is not None:
            print(json.dumps(response, ensure_ascii=False), flush=True)
    return 0


def run_self_test() -> int:
    checks: list[tuple[str, bool, str]] = []

    caps = list_capabilities({})
    checks.append(("list_capabilities", caps.get("ok") is True and "route_context" in caps.get("tools", []), "missing route_context"))

    route = route_context({"workflow": "code_review", "platform": "esp32", "rtos": "freertos"})
    checks.append(("route_context", route["ok"] and isinstance(route.get("data"), dict), "route_context failed"))

    sdk = lookup_sdk({"platform": "esp32", "query": "TASK_CREATE"})
    checks.append(("lookup_sdk", sdk["ok"] and "xTaskCreate" in sdk.get("stdout", ""), "lookup_sdk failed"))

    gate = run_gate({"level": "quick"})
    checks.append(("run_gate quick", gate["ok"], "quick gate failed"))

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