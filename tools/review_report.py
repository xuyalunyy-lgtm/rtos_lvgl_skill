#!/usr/bin/env python3
"""Render a machine-readable ``run_review`` report as Markdown or HTML."""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any


def _findings(report: dict[str, Any]) -> list[dict[str, Any]]:
    return [issue for item in report.get("checkers", []) for issue in item.get("findings", [])]


def render_markdown(report: dict[str, Any]) -> str:
    context = report.get("review_context", {})
    lines = [
        "# Embedded Review Report",
        "",
        f"- Result: {'PASS' if report.get('exit_code') == 0 else 'FINDINGS'}",
        f"- Platform: `{context.get('platform', 'unknown')}`",
        f"- Files checked: {report.get('files_checked', 0)}",
        f"- Issues: {report.get('total_issues', 0)}",
        "",
        "## Checker Summary",
        "",
        "| Checker | Constraints | Files | Issues | Result |",
        "|---|---|---:|---:|---|",
    ]
    for item in report.get("checkers", []):
        result = "skipped" if item.get("skipped") else "pass" if item.get("issues", 0) == 0 else "findings"
        lines.append(
            f"| `{item.get('checker', 'unknown')}` | {', '.join(item.get('domains', []))} | "
            f"{item.get('files_checked', 0)} | {item.get('issues', 0)} | {result} |"
        )

    lines.extend(["", "## Findings", ""])
    findings = _findings(report)
    if not findings:
        lines.append("No checker findings.")
    else:
        for issue in findings:
            lines.append(
                f"- **{issue.get('id', '?')} / {issue.get('severity', '?')}** "
                f"`{issue.get('file', '?')}` - {issue.get('issue', '')}"
            )
    history = report.get("history")
    if history:
        lines.extend([
            "", "## Trend", "",
            f"- {history.get('trend', 'unknown')}: "
            f"{history.get('previous_total_issues')} -> {history.get('current_total_issues')}",
        ])
    return "\n".join(lines) + "\n"


def render_html(report: dict[str, Any]) -> str:
    context = report.get("review_context", {})

    def esc(value: Any) -> str:
        return html.escape(str(value))

    rows = []
    for item in report.get("checkers", []):
        result = "skipped" if item.get("skipped") else "pass" if item.get("issues", 0) == 0 else "findings"
        rows.append(
            "<tr>"
            f"<td>{esc(item.get('checker', 'unknown'))}</td>"
            f"<td>{esc(', '.join(item.get('domains', [])))}</td>"
            f"<td>{esc(item.get('files_checked', 0))}</td><td>{esc(item.get('issues', 0))}</td>"
            f"<td class=\"{result}\">{result}</td></tr>"
        )
    finding_rows = "".join(
        f"<li><strong>{esc(issue.get('id', '?'))} / {esc(issue.get('severity', '?'))}</strong> "
        f"<code>{esc(issue.get('file', '?'))}</code> - {esc(issue.get('issue', ''))}</li>"
        for issue in _findings(report)
    ) or "<li>No checker findings.</li>"
    result = "PASS" if report.get("exit_code") == 0 else "FINDINGS"
    return f"""<!doctype html>
<html lang=\"en\"><head><meta charset=\"utf-8\"><title>Embedded Review Report</title>
<style>body{{font-family:system-ui,sans-serif;max-width:1100px;margin:2rem auto;padding:0 1rem;color:#1f2937}}table{{border-collapse:collapse;width:100%}}th,td{{border:1px solid #d1d5db;padding:.45rem;text-align:left}}th{{background:#f3f4f6}}.pass{{color:#047857}}.findings{{color:#b45309;font-weight:600}}.skipped{{color:#6b7280}}code{{white-space:pre-wrap}}</style>
</head><body><h1>Embedded Review Report</h1><p><strong>{result}</strong> | platform <code>{esc(context.get('platform', 'unknown'))}</code> | files {esc(report.get('files_checked', 0))} | issues {esc(report.get('total_issues', 0))}</p>
<h2>Checker Summary</h2><table><thead><tr><th>Checker</th><th>Constraints</th><th>Files</th><th>Issues</th><th>Result</th></tr></thead><tbody>{''.join(rows)}</tbody></table>
<h2>Findings</h2><ul>{finding_rows}</ul></body></html>
"""


def write_report(report: dict[str, Any], path: str | Path, format_name: str) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    rendered = render_markdown(report) if format_name == "markdown" else render_html(report)
    destination.write_text(rendered, encoding="utf-8")
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--format", choices=("markdown", "html"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = json.loads(args.report.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        parser.error(f"cannot read review JSON: {exc}")
    write_report(report, args.output, args.format)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
