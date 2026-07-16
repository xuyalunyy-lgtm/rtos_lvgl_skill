#!/usr/bin/env python3
"""Audit the semantic workflow routing table in SKILL.md.

The intent labels are deliberately human-authored: keyword tables are too brittle for
multi-turn or composite requests. This check keeps workflow coverage synchronized with
the active files and with the deterministic context router.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TABLE_RE = re.compile(
    r"^\| 用户意图 \| 主工作流 \|\s*$\n"
    r"^\|[-| ]+\|\s*$\n"
    r"(?P<rows>(?:^\|.*\|\s*$\n?)+)",
    re.MULTILINE,
)
LINK_RE = re.compile(r"\]\(workflows/([a-z0-9_]+\.md)\)")

# context_router.py route IDs must remain representable by the semantic table.
ROUTER_WORKFLOW_FILES = {
    "debug_crash.md",
    "l2_code_review.md",
    "l2_memory_analysis.md",
    "l2_project_review.md",
    "hw_sw_cocodebug.md",
    "l3_lvgl_page.md",
    "l3_new_module.md",
    "l3_bring_up.md",
    "l3_sdk_trim.md",
}


def active_workflow_files() -> set[str]:
    return {
        path.name
        for path in (ROOT / "workflows").glob("*.md")
        if path.name != "README.md"
    }


def parse_skill_routes() -> tuple[list[str], list[str]]:
    text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    match = TABLE_RE.search(text)
    if not match:
        return [], ["SKILL.md missing semantic routing table"]

    rows = [line for line in match.group("rows").splitlines() if line.strip()]
    routes: list[str] = []
    errors: list[str] = []
    for row_no, row in enumerate(rows, start=1):
        links = LINK_RE.findall(row)
        if len(links) != 1:
            errors.append(f"routing row {row_no} must contain exactly one workflows/*.md link")
            continue
        routes.append(links[0])
    return routes, errors


def check_in_sync() -> bool:
    routes, errors = parse_skill_routes()
    active = active_workflow_files()
    routed = set(routes)

    duplicates = sorted(name for name in routed if routes.count(name) > 1)
    missing = sorted(active - routed)
    stale = sorted(routed - active)
    router_missing = sorted(ROUTER_WORKFLOW_FILES - routed)

    if duplicates:
        errors.append(f"duplicate workflow routes: {', '.join(duplicates)}")
    if missing:
        errors.append(f"active workflows missing from SKILL.md: {', '.join(missing)}")
    if stale:
        errors.append(f"SKILL.md routes missing files: {', '.join(stale)}")
    if router_missing:
        errors.append(f"context-router workflows missing from SKILL.md: {', '.join(router_missing)}")

    if errors:
        print("[skill-routing] FAILED")
        for error in errors:
            print(f"  - {error}")
        return False

    print(f"[skill-routing] semantic routing covers all {len(active)} active workflows")
    return True


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1:] != ["--check"]:
        print("usage: sync_skill_routing.py [--check]", file=sys.stderr)
        return 2
    return 0 if check_in_sync() else 1


if __name__ == "__main__":
    raise SystemExit(main())
