#!/usr/bin/env python3
"""Detect stale release/CI references before they become false-green gates."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXPECTED_MCP_SERVERS = {
    "mqtt-mcp": "mcp/mqtt_server.py",
    "ota-mcp": "mcp/ota_server.py",
    "serial-mcp": "mcp/serial_server.py",
}
REQUIRED_CI_COMMANDS = (
    "python scripts/quick_gate.py --strict",
    *(f"python {path} --self-test" for path in EXPECTED_MCP_SERVERS.values()),
)


def validate_contract(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    config_path = root / ".mcp.json"
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f".mcp.json is unreadable or invalid JSON: {exc}"]

    servers = config.get("mcpServers")
    if not isinstance(servers, dict):
        return [".mcp.json missing mcpServers object"]
    for name, relative_path in EXPECTED_MCP_SERVERS.items():
        server = servers.get(name)
        if not isinstance(server, dict):
            errors.append(f".mcp.json missing {name} configuration")
            continue
        if server.get("command") != "python" or relative_path not in server.get("args", []):
            errors.append(f".mcp.json {name} must invoke python {relative_path}")
        if not (root / relative_path).is_file():
            errors.append(f"missing MCP server implementation: {relative_path}")

    ci_path = root / ".github" / "workflows" / "skill-tools.yml"
    try:
        ci = ci_path.read_text(encoding="utf-8")
    except OSError as exc:
        return [*errors, f"CI workflow unreadable: {exc}"]
    for command in REQUIRED_CI_COMMANDS:
        if command not in ci:
            errors.append(f".github/workflows/skill-tools.yml misses release command: {command}")
    return errors


def main() -> int:
    errors = validate_contract()
    if errors:
        print("[release-contract] FAILED")
        for error in errors:
            print(f"  - {error}")
        return 1
    print("[release-contract] release and CI references are current")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
