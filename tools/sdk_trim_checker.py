#!/usr/bin/env python3
"""Validate an auditable C6 SDK-trimming decision manifest."""
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
        return [make_issue(path, 1, "C6", "P0", f"invalid SDK trim manifest: {exc}")]
    if not isinstance(data, dict):
        return [make_issue(path, 1, "C6", "P0", "SDK trim manifest must be a JSON object")]

    issues: list[dict] = []
    sdk = data.get("sdk")
    if not isinstance(sdk, dict) or not _non_empty_string(sdk.get("name")) or not _non_empty_string(sdk.get("version")):
        issues.append(make_issue(path, 1, "C6.2", "P1", "manifest must record SDK name and version"))
    if not isinstance(data.get("questionnaire"), list) or not data["questionnaire"]:
        issues.append(make_issue(path, 1, "C6.1", "P0", "manifest must include a non-empty product questionnaire"))

    decisions = data.get("decisions")
    if not isinstance(decisions, list) or not decisions:
        issues.append(make_issue(path, 1, "C6.3", "P1", "manifest must include at least one component decision"))
    else:
        for index, decision in enumerate(decisions, start=1):
            if not isinstance(decision, dict) or not all(
                _non_empty_string(decision.get(field))
                for field in ("component", "feature", "rationale", "rollback")
            ):
                issues.append(make_issue(path, index, "C6.3", "P1", "each decision needs component, feature, rationale, and rollback"))
            elif decision.get("action") not in {"keep", "remove"}:
                issues.append(make_issue(path, index, "C6.3", "P1", "decision action must be keep or remove"))
    return issues


if __name__ == "__main__":
    raise SystemExit(run_checker(check_file, "C6 SDK trim manifest checker", ("C6",), suffixes={".json"}))
