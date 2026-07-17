#!/usr/bin/env python3
"""Render a reviewable navigation report from an LVGL page plan."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from checker_io import configure_stdout, output_json
from lvgl_page_plan_checker import PAGE_PLAN_KIND, check_file


def _mapping(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: object, fallback: str = "—") -> str:
    return value.strip() if isinstance(value, str) and value.strip() else fallback


def _cell(value: object) -> str:
    return _text(value).replace("|", "\\|").replace("\n", " ")


def build_report(plan: dict[str, Any], diagnostics: list[dict[str, str]]) -> dict[str, Any]:
    navigation = _mapping(plan.get("navigation"))
    pages = [_mapping(page) for page in _list(plan.get("pages"))]
    page_rows: list[dict[str, str]] = []
    transition_rows: list[dict[str, str]] = []
    interrupt_rows: list[dict[str, str]] = []

    for page in pages:
        lifecycle = _mapping(page.get("lifecycle"))
        page_rows.append({
            "id": _text(page.get("id")),
            "parent": _text(page.get("parent")),
            "states": ", ".join(str(state) for state in _list(page.get("states"))) or "—",
            "create": _text(lifecycle.get("create_policy"), "legacy"),
            "exit": _text(lifecycle.get("exit_policy"), "legacy"),
            "fallback": _text(lifecycle.get("fallback_target")),
            "cache": _text(_mapping(page.get("resources")).get("cache_policy")),
        })
        for transition in _list(page.get("transitions")):
            item = _mapping(transition)
            row = {
                "from": _text(page.get("id")),
                "event": _text(item.get("event")),
                "to": _text(item.get("to")),
                "kind": _text(item.get("kind"), "legacy"),
                "action": _text(item.get("stack_action"), "legacy"),
                "direction": _text(item.get("direction"), "legacy"),
                "guard": _text(item.get("guard")),
            }
            transition_rows.append(row)
            if item.get("kind") == "interrupt":
                interrupt_rows.append({
                    **row,
                    "priority": str(item.get("priority", "—")),
                    "resume": _text(item.get("resume")),
                    "fallback": _text(item.get("fallback_target")),
                })

    return {
        "kind": "lvgl_navigation_report",
        "source_kind": plan.get("kind"),
        "schema_version": plan.get("schema_version"),
        "initial_page": plan.get("initial_page"),
        "navigation": {
            "router_owner": navigation.get("router_owner"),
            "root_page": navigation.get("root_page"),
            "back_stack": navigation.get("back_stack"),
            "interrupt_resume": navigation.get("interrupt_resume"),
        },
        "pages": page_rows,
        "transitions": transition_rows,
        "interrupts": interrupt_rows,
        "diagnostics": diagnostics,
    }


def _markdown_table(headers: list[str], rows: list[list[str]]) -> list[str]:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    lines.extend("| " + " | ".join(_cell(cell) for cell in row) + " |" for row in rows)
    return lines


def render_markdown(report: dict[str, Any], source: Path) -> str:
    navigation = _mapping(report.get("navigation"))
    lines = [
        "# LVGL 页面导航审计报告",
        "",
        f"- 来源：`{source.as_posix()}`",
        f"- 规划版本：`{_text(report.get('schema_version'))}`",
        f"- 初始页：`{_text(report.get('initial_page'))}`",
        f"- 根页：`{_text(navigation.get('root_page'))}`",
        f"- 路由器 owner：`{_text(navigation.get('router_owner'))}`",
        f"- 返回栈：`{_text(navigation.get('back_stack'))}`",
        f"- 中断恢复：`{_text(navigation.get('interrupt_resume'))}`",
        "",
        "## 页面树与生命周期",
        "",
    ]
    page_rows = _list(report.get("pages"))
    lines.extend(_markdown_table(
        ["页面", "父级", "状态", "创建", "离开", "回退", "资源缓存"],
        [[row["id"], row["parent"], row["states"], row["create"], row["exit"], row["fallback"], row["cache"]] for row in page_rows],
    ))
    lines.extend(["", "## 跳转边", ""])
    transition_rows = _list(report.get("transitions"))
    lines.extend(_markdown_table(
        ["来源", "事件", "目标", "类型", "栈操作", "方向", "Guard"],
        [[row["from"], row["event"], row["to"], row["kind"], row["action"], row["direction"], row["guard"]] for row in transition_rows],
    ))
    lines.extend(["", "## 中断路由", ""])
    interrupt_rows = _list(report.get("interrupts"))
    if interrupt_rows:
        lines.extend(_markdown_table(
            ["来源", "事件", "目标", "优先级", "恢复", "回退"],
            [[row["from"], row["event"], row["to"], row["priority"], row["resume"], row["fallback"]] for row in interrupt_rows],
        ))
    else:
        lines.append("无。")

    diagnostics = _list(report.get("diagnostics"))
    lines.extend(["", "## 校验诊断", ""])
    if diagnostics:
        for issue in diagnostics:
            item = _mapping(issue)
            lines.append(f"- [{_text(item.get('severity'))}] {_text(item.get('id'))}：{_text(item.get('issue'))}")
    else:
        lines.append("规划校验通过。")
    return "\n".join(lines) + "\n"


def main() -> int:
    configure_stdout()
    parser = argparse.ArgumentParser(description="Render an LVGL page-plan navigation audit report")
    parser.add_argument("plan", type=Path, help="Path to lvgl_page_plan.json")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    parser.add_argument("--output", type=Path, help="Write report to a file instead of stdout")
    args = parser.parse_args()

    try:
        plan = json.loads(args.plan.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        parser.error(f"cannot read LVGL page plan: {exc}")
    if not isinstance(plan, dict) or plan.get("kind") != PAGE_PLAN_KIND:
        parser.error("plan must be a JSON object with kind lvgl_page_plan")

    report = build_report(plan, check_file(args.plan))
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n" if args.format == "json" else render_markdown(report, args.plan)
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    elif args.format == "json":
        output_json(report)
    else:
        print(rendered, end="")
    return 1 if report["diagnostics"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
