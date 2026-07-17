#!/usr/bin/env python3
"""Validate auditable LVGL page-planning contracts before page implementation."""
from __future__ import annotations

import json
from pathlib import Path

from checker_io import make_issue, run_checker


PAGE_PLAN_KIND = "lvgl_page_plan"
UPDATE_BOUNDARIES = {"queue", "presenter", "async"}
CACHE_POLICIES = {"resident", "lazy", "prefetch", "external"}
SCHEMA_VERSIONS = {"1.0", "1.1"}
CREATE_POLICIES = {"resident", "lazy"}
EXIT_POLICIES = {"hide", "destroy"}
TRANSITION_KINDS = {"forward", "back", "return", "interrupt", "reset"}
STACK_ACTIONS = {"push", "pop", "replace", "reset"}
DIRECTIONS = {"none", "up", "down", "left", "right"}
INTERRUPT_RESUMES = {"previous", "fallback"}


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
    schema_version = data.get("schema_version")
    if schema_version not in SCHEMA_VERSIONS:
        issues.append(make_issue(path, 1, "C29", "P1", "LVGL page plan must declare schema_version 1.0 or 1.1"))

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
    page_definitions: list[tuple[int, dict]] = []
    for index, page_value in enumerate(pages, start=1):
        page = _mapping(page_value)
        page_definitions.append((index, page))
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

    if schema_version != "1.1":
        return issues

    navigation = _mapping(data.get("navigation"))
    root_page = navigation.get("root_page")
    if not _string(root_page) or root_page not in page_ids:
        issues.append(make_issue(path, 1, "C33.1", "P0", "navigation.root_page must reference a declared page"))
    if navigation.get("router_owner") != ui_owner.get("task"):
        issues.append(make_issue(path, 1, "C1.2", "P0", "navigation.router_owner must match ui_owner.task"))
    if navigation.get("back_stack") != "explicit":
        issues.append(make_issue(path, 1, "C33.1", "P1", "navigation.back_stack must be explicit"))
    if navigation.get("interrupt_resume") != "previous_or_fallback":
        issues.append(make_issue(path, 1, "C33.1", "P1", "navigation.interrupt_resume must be previous_or_fallback"))

    for index, page in page_definitions:
        page_id = page.get("id")
        parent = page.get("parent")
        if page_id == root_page:
            if parent is not None:
                issues.append(make_issue(path, index, "C33.1", "P1", "navigation root page must declare parent as null"))
        elif not _string(parent) or parent not in page_ids:
            issues.append(make_issue(path, index, "C33.1", "P0", f"page {page_id or '?'} must reference a declared parent"))

        lifecycle = _mapping(page.get("lifecycle"))
        if lifecycle.get("create_policy") not in CREATE_POLICIES:
            issues.append(make_issue(path, index, "C23.3", "P1", "page lifecycle needs create_policy: resident or lazy"))
        if lifecycle.get("exit_policy") not in EXIT_POLICIES:
            issues.append(make_issue(path, index, "C23.3", "P1", "page lifecycle needs exit_policy: hide or destroy"))
        fallback_target = lifecycle.get("fallback_target")
        if not _string(fallback_target) or fallback_target not in page_ids:
            issues.append(make_issue(path, index, "C33.1", "P1", "page lifecycle needs fallback_target referencing a declared page"))

    for index, source, transition in transitions:
        kind = transition.get("kind")
        action = transition.get("stack_action")
        direction = transition.get("direction")
        if kind not in TRANSITION_KINDS:
            issues.append(make_issue(path, index, "C33.1", "P1", f"page {source} transition needs kind: forward, back, return, interrupt, or reset"))
        if action not in STACK_ACTIONS:
            issues.append(make_issue(path, index, "C33.1", "P1", f"page {source} transition needs stack_action: push, pop, replace, or reset"))
        if direction not in DIRECTIONS:
            issues.append(make_issue(path, index, "C33.1", "P1", f"page {source} transition needs direction: none, up, down, left, or right"))
        if kind in {"back", "return"} and action != "pop":
            issues.append(make_issue(path, index, "C33.1", "P1", f"page {source} {kind} transition must pop the explicit back stack"))
        if kind == "forward" and action not in {"push", "replace"}:
            issues.append(make_issue(path, index, "C33.1", "P1", f"page {source} forward transition must push or replace"))
        if kind == "interrupt" and action not in {"push", "replace"}:
            issues.append(make_issue(path, index, "C33.1", "P1", f"page {source} interrupt transition must push or replace"))
        if kind == "reset" and action != "reset":
            issues.append(make_issue(path, index, "C33.1", "P1", f"page {source} reset transition must reset the back stack"))
        if kind == "reset" and transition.get("to") != root_page:
            issues.append(make_issue(path, index, "C33.1", "P1", f"page {source} reset transition must target navigation.root_page"))
        if kind == "forward" and action == "push" and transition.get("to") == source:
            issues.append(make_issue(path, index, "C33.1", "P0", f"page {source} must not push itself onto the back stack"))
        if kind == "interrupt":
            if not isinstance(transition.get("priority"), int) or transition["priority"] <= 0:
                issues.append(make_issue(path, index, "C33.1", "P0", f"page {source} interrupt transition needs positive priority"))
            if transition.get("resume") not in INTERRUPT_RESUMES:
                issues.append(make_issue(path, index, "C33.1", "P1", f"page {source} interrupt transition needs resume: previous or fallback"))
        if kind in {"interrupt", "return"}:
            fallback_target = transition.get("fallback_target")
            if not _string(fallback_target) or fallback_target not in page_ids:
                issues.append(make_issue(path, index, "C33.1", "P1", f"page {source} {kind} transition needs fallback_target referencing a declared page"))
            if transition.get("resume") not in INTERRUPT_RESUMES:
                issues.append(make_issue(path, index, "C33.1", "P1", f"page {source} {kind} transition needs resume: previous or fallback"))

    pages_by_id = {
        page["id"]: page
        for _, page in page_definitions
        if _string(page.get("id")) and page["id"] in page_ids
    }
    transitions_by_source: dict[str, list[dict]] = {page_id: [] for page_id in pages_by_id}
    for _, source, transition in transitions:
        if source in transitions_by_source and _string(transition.get("to")) and transition["to"] in page_ids:
            transitions_by_source[source].append(transition)

    if _string(initial_page) and initial_page in page_ids:
        reachable: set[str] = set()
        pending = [initial_page]
        while pending:
            current = pending.pop()
            if current in reachable:
                continue
            reachable.add(current)
            pending.extend(
                transition["to"]
                for transition in transitions_by_source.get(current, [])
                if transition["to"] not in reachable
            )
        for page_id in sorted(page_ids - reachable):
            issues.append(make_issue(path, 1, "C33.1", "P1", f"page {page_id} is unreachable from initial_page"))

    for index, page in page_definitions:
        page_id = page.get("id")
        if not _string(page_id) or page_id == root_page or page_id not in pages_by_id:
            continue
        page_transitions = transitions_by_source.get(page_id, [])
        if not any(transition.get("kind") in {"back", "return", "reset"} for transition in page_transitions):
            issues.append(make_issue(path, index, "C33.1", "P1", f"page {page_id} needs an explicit back, return, or reset exit route"))
        parent = page.get("parent")
        for transition in page_transitions:
            if transition.get("kind") == "back" and transition.get("to") != parent:
                issues.append(make_issue(path, index, "C33.1", "P1", f"page {page_id} back transition must target its declared parent"))
    return issues


if __name__ == "__main__":
    raise SystemExit(run_checker(
        check_file,
        "LVGL page planning contract checker",
        ("C1", "C23", "C29", "C33"),
        suffixes={".json"},
    ))
