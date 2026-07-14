#!/usr/bin/env python3
"""
Sync the SKILL.md routing table from context_router.py ROUTE_KEYWORDS.

Single source of truth: context_router.py ROUTE_KEYWORDS
This script generates the markdown routing table in SKILL.md.

Usage:
    python scripts/sync_skill_routing.py --check   # verify in sync (CI mode)
    python scripts/sync_skill_routing.py            # update SKILL.md in place
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Import ROUTE_KEYWORDS from context_router
sys.path.insert(0, str(ROOT / "tools"))
from context_router import ROUTE_KEYWORDS

# ROUTE_KEYWORDS key → SKILL.md workflow name
WORKFLOW_DISPLAY = {
    "crash_debug": "debug_crash",
    "code_review": "l2_code_review",
    "memory_analysis": "l2_memory_analysis",
    "project_review": "l2_project_review",
    "hw_sw_debug": "hw_sw_cocodebug",
    "lvgl_page": "l3_lvgl_page",
    "app_manifest": "l3_lvgl_page (manifest sub-path)",
    "new_module": "l3_new_module",
    "bring_up": "l3_bring_up",
    "sdk_trim": "l3_sdk_trim",
}


def generate_routing_table() -> str:
    """Generate the markdown routing table from ROUTE_KEYWORDS."""
    # Sort by priority (ascending), then by key
    sorted_routes = sorted(
        ROUTE_KEYWORDS.items(),
        key=lambda x: (x[1]["priority"], x[0]),
    )

    lines = []
    lines.append("| Keywords | Exclude | Priority | Workflow |")
    lines.append("|----------|---------|----------|----------|")

    for wf_id, spec in sorted_routes:
        keywords = ", ".join(spec["keywords"])
        exclude = ", ".join(spec["exclude"]) if spec["exclude"] else "—"
        priority = str(spec["priority"])
        workflow = WORKFLOW_DISPLAY.get(wf_id, wf_id)
        lines.append(f"| {keywords} | {exclude} | {priority} | {workflow} |")

    return "\n".join(lines)


def update_skill_md(table: str) -> None:
    """Update SKILL.md routing table section in place."""
    skill_md = ROOT / "SKILL.md"
    content = skill_md.read_text(encoding="utf-8")

    # Find the routing table between the header row and the next paragraph
    pattern = re.compile(
        r"(\| Keywords \| Exclude \| Priority \| Workflow \|\n"
        r"\|[-|]+\|\n)"
        r"(.*?\n)"
        r"(Composite requests:)",
        re.DOTALL,
    )

    match = pattern.search(content)
    if not match:
        print("ERROR: Could not find routing table in SKILL.md", file=sys.stderr)
        sys.exit(1)

    new_content = content[:match.start(1)] + match.group(1) + table + "\n" + match.group(3) + content[match.end(3):]
    skill_md.write_text(new_content, encoding="utf-8")
    print(f"Updated {skill_md}")


def check_in_sync(table: str) -> bool:
    """Check if SKILL.md routing table matches the generated one."""
    skill_md = ROOT / "SKILL.md"
    content = skill_md.read_text(encoding="utf-8")

    pattern = re.compile(
        r"\| Keywords \| Exclude \| Priority \| Workflow \|\n"
        r"\|[-|]+\|\n"
        r"(.*?)\n"
        r"(Composite requests:)",
        re.DOTALL,
    )

    match = pattern.search(content)
    if not match:
        print("ERROR: Could not find routing table in SKILL.md", file=sys.stderr)
        return False

    current = match.group(1).strip()
    expected = table.strip()

    if current == expected:
        print("OK: SKILL.md routing table is in sync with context_router.py")
        return True

    print("MISMATCH: SKILL.md routing table differs from context_router.py ROUTE_KEYWORDS")
    print(f"\n--- Current (SKILL.md) ---\n{current}")
    print(f"\n--- Expected (context_router.py) ---\n{expected}")
    return False


def main() -> int:
    table = generate_routing_table()

    if "--check" in sys.argv:
        return 0 if check_in_sync(table) else 1
    else:
        update_skill_md(table)
        return 0


if __name__ == "__main__":
    sys.exit(main())
