#!/usr/bin/env python3
"""Validate a C40 one-command reproduction contract manifest."""
from __future__ import annotations

import json
from pathlib import Path

from checker_io import make_issue, run_checker


def _non_empty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def check_file(path: Path) -> list[dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [make_issue(path, 1, "C40", "P0", f"invalid reproduction manifest: {exc}")]
    if not isinstance(data, dict):
        return [make_issue(path, 1, "C40", "P0", "reproduction manifest must be a JSON object")]

    issues: list[dict] = []
    commands = data.get("commands")
    if not isinstance(commands, dict) or not all(_non_empty_string(commands.get(key)) for key in ("build", "flash", "monitor")):
        issues.append(make_issue(path, 1, "C40.1", "P0", "commands must include reproducible build, flash, and monitor commands"))
    decode = data.get("crash_decode")
    if not isinstance(decode, dict) or not all(_non_empty_string(decode.get(key)) for key in ("symbol_path", "command", "input_log")):
        issues.append(make_issue(path, 1, "C40.2", "P0", "crash_decode must declare symbol_path, command, and input_log"))
    if not all(_non_empty_string(data.get(key)) for key in ("minimal_config", "test_entry", "expected_output", "sdk_version")):
        issues.append(make_issue(path, 1, "C40.3", "P1", "manifest must declare minimal_config, test_entry, expected_output, and sdk_version"))
    logs = data.get("failure_logs")
    if not isinstance(logs, dict) or not _non_empty_string(logs.get("path")) or not _non_empty_string(logs.get("redaction")) or not isinstance(logs.get("retention_days"), int):
        issues.append(make_issue(path, 1, "C40.4", "P1", "failure_logs must declare path, redaction, and integer retention_days"))
    return issues


if __name__ == "__main__":
    raise SystemExit(run_checker(check_file, "C40 reproduction contract checker", ("C40",), suffixes={".json"}))
