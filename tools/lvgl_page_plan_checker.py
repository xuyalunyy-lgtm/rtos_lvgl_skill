#!/usr/bin/env python3
"""Validate auditable LVGL page-planning contracts before page implementation."""
from __future__ import annotations

import json
from pathlib import Path

from checker_io import make_issue, run_checker


PAGE_PLAN_KIND = "lvgl_page_plan"
UPDATE_BOUNDARIES = {"queue", "presenter", "async"}
CACHE_POLICIES = {"resident", "lazy", "prefetch", "external"}


def _string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _mapping(value: object) -> dict:
    return value if isinstance(value, dict) else {}


def _list(value: object) -> list:
    return value if isinstance(value, list) else []


def check_file(path: Path) -> list[dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [make_issue(path, 1, "C29", "P0", f"invalid LVGL page plan JSON: {exc}")]
    if not isinstance(data, dict) or data.get("kind") != PAGE_PLAN_KIND:
        return []

    issues: list[dict] = []
    if data.get("schema_version") != "1.0":
        issues.append(make_issue(path, 1, "C29", "P1", "LVGL page plan must declare schema_version 1.0"))

    display = _mapping(data.get("display"))
    width, height = display.get("width"), display.get("height")
    if not isinstance(width, int) or width <= 0 or not isinstance(height, int) or height <= 0:
        issues.append(make_issue(path, 1, "C23.6", "P0", "display must declare positive width and height"))
    if not _string(display.get("lvgl_version")):
        issues.append(make_issue(path, 1, "C23.6", "P1", "display must declare the target LVGL version"))
    budget = display.get("frame_budget_ms")
    flush_budget = display.get("max_flush_ms")
    if not isinstance(budget, int) or budget <= 0 or not isinstance(flush_budget, int) or flush_budget <= 0:
        issues.append(make_issue(path, 1, "C23.3", "P1", "display must declare positive frame_budget_ms and max_flush_ms"))
    elif flush_budget > budget:
        issues.append(make_issue(path, 1, "C23.3", "P1", "max_flush_ms must not exceed frame_budget_ms"))

    ui_owner = _mapping(data.get("ui_owner"))
    if not _string(ui_owner.get("task")):
        issues.append(make_issue(path, 1, "C1.2", "P0", "page plan must name the sole LVGL UI owner task"))
    if ui_owner.get("update_boundary") not in UPDATE_BOUNDARIES:
        issues.append(make_issue(path, 1, "C1.2", "P0", "ui_owner.update_boundary must be queue, presenter, or async"))

    pages = _list(data.get("pages"))
    if not pages:
        return issues + [make_issue(path, 1, "C29", "P0", "page plan must contain at least one page")]

    page_ids: set[str] = set()
    transitions: list[tuple[int, str, dict]] = []
    for index, page_value in enumerate(pages, start=1):
        page = _mapping(page_value)
        page_id = page.get("id")
        if not _string(page_id) or page_id in page_ids:
            issues.append(make_issue(path, index, "C29", "P0", "each page needs a unique non-empty id"))
        elif isinstance(page_id, str):
            page_ids.add(page_id)
        if not _list(page.get("states")):
            issues.append(make_issue(path, index, "C33.1", "P1", "each page must declare visible states"))

        resources = _mapping(page.get("resources"))
        if resources.get("cache_policy") not in CACHE_POLICIES:
            issues.append(make_issue(path, index, "C23.3", "P1", "page resources need cache_policy: resident, lazy, prefetch, or external"))
        refresh = _mapping(page.get("refresh"))
        if not isinstance(refresh.get("dynamic_regions"), list):
            issues.append(make_issue(path, index, "C23.3", "P1", "page refresh plan must list dynamic_regions"))
        if not isinstance(refresh.get("full_screen_invalidate"), bool):
            issues.append(make_issue(path, index, "C23.3", "P1", "page refresh plan must state full_screen_invalidate"))

        for transition in _list(page.get("transitions")):
            transitions.append((index, str(page_id or "?"), _mapping(transition)))

    initial_page = data.get("initial_page")
    if not _string(initial_page) or initial_page not in page_ids:
        issues.append(make_issue(path, 1, "C33.1", "P0", "initial_page must reference a declared page"))
    for index, source, transition in transitions:
        if not _string(transition.get("event")) or not _string(transition.get("to")):
            issues.append(make_issue(path, index, "C33.1", "P1", f"page {source} transition needs event and to"))
        elif transition["to"] not in page_ids:
            issues.append(make_issue(path, index, "C33.1", "P0", f"page {source} transition targets unknown page {transition['to']}"))
        if not _string(transition.get("guard")):
            issues.append(make_issue(path, index, "C33.1", "P1", f"page {source} transition needs a reentry guard"))
    return issues


if __name__ == "__main__":
    raise SystemExit(run_checker(
        check_file,
        "LVGL page planning contract checker",
        ("C1", "C23", "C29", "C33"),
        suffixes={".json"},
    ))
