#!/usr/bin/env python3
"""Practical one-command project gate for firmware review.

This wraps run_review.py with profile presets, log triage, evidence output, and
a compact Markdown summary intended for day-to-day project use.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parent
SKILL_ROOT = TOOLS_DIR.parent


PROFILE_SKIPS = {
    "default": [],
    "media": [],
    "iot": ["--skip-av", "--skip-media-format", "--skip-av-clock", "--skip-av-dma"],
    "ui": ["--skip-av", "--skip-media-format", "--skip-av-clock", "--skip-av-dma"],
    "minimal": [
        "--skip-av",
        "--skip-media-format",
        "--skip-av-clock",
        "--skip-av-dma",
        "--skip-voice",
        "--skip-sensor-integration",
    ],
}


def run_json(cmd: list[str]) -> tuple[int, dict]:
    proc = subprocess.run(
        cmd,
        cwd=SKILL_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
    )
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        data = {"parse_error": True, "stdout": proc.stdout[-2000:], "stderr": proc.stderr[-2000:]}
    return proc.returncode, data


def issue_summary(data: dict) -> dict:
    results = data.get("checkers") or data.get("checker_results") or []
    p0_like = [r for r in results if r.get("exit_code", 0) != 0]
    total_issues = sum(int(r.get("issues", 0) or 0) for r in results)
    files_checked = max([int(r.get("files_checked", 0) or 0) for r in results] or [0])
    return {
        "files_checked": files_checked,
        "total_issues": total_issues,
        "failed_checkers": len(p0_like),
        "failed_checker_names": [r.get("checker", "") for r in p0_like],
    }


def render_report(
    *,
    target_dir: str,
    platform: str,
    profile: str,
    review_exit: int,
    review_data: dict,
    log_rows: list[dict],
) -> str:
    summary = issue_summary(review_data)
    lines = [
        "# Project Gate Report",
        "",
        f"- Target: `{target_dir}`",
        f"- Platform: `{platform}`",
        f"- Profile: `{profile}`",
        f"- Review exit: `{review_exit}`",
        f"- Files checked: {summary['files_checked']}",
        f"- Total checker issues: {summary['total_issues']}",
        f"- Failed checkers: {summary['failed_checkers']}",
        "",
        "## Blocking Checkers",
        "",
    ]
    if summary["failed_checker_names"]:
        for name in summary["failed_checker_names"]:
            lines.append(f"- `{name}`")
    else:
        lines.append("- None")

    lines.extend(["", "## Log Triage", ""])
    if log_rows:
        lines.extend([
            "| Severity | File | Summary | Symptoms | Constraints |",
            "| --- | --- | --- | --- | --- |",
        ])
        for row in log_rows:
            symptoms = ", ".join(f"`{sid}`" for sid in row.get("symptom_ids", [])) or "-"
            constraints = ", ".join(f"`{c}`" for c in row.get("constraints", [])) or "-"
            lines.append(
                f"| {row.get('max_severity', '-')} | `{row.get('file', '')}` | "
                f"{row.get('summary', '')} | {symptoms} | {constraints} |"
            )
    else:
        lines.append("- No logs were provided.")

    lines.extend(["", "## Suggested Follow-Up", ""])
    if summary["failed_checker_names"]:
        lines.append("- Fix failed checker groups before treating the project as release-ready.")
    if any(row.get("max_severity") == "P0" for row in log_rows):
        lines.append("- Resolve P0 log triage findings before patching symptoms blindly.")
    if not summary["failed_checker_names"] and not any(row.get("has_symptoms") for row in log_rows):
        lines.append("- Gate is clean for the selected profile.")

    return "\n".join(lines) + "\n"


def run_self_test() -> int:
    assert "iot" in PROFILE_SKIPS
    summary = issue_summary({"checkers": [{"checker": "x", "issues": 2, "files_checked": 3, "exit_code": 1}]})
    assert summary["total_issues"] == 2
    assert summary["files_checked"] == 3
    assert summary["failed_checker_names"] == ["x"]
    report = render_report(
        target_dir="src",
        platform="esp32",
        profile="iot",
        review_exit=0,
        review_data={"checker_results": []},
        log_rows=[],
    )
    assert "Project Gate Report" in report
    assert "Gate is clean" in report
    print("project_gate self-test passed")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="One-command firmware project gate")
    parser.add_argument("--dir", "-d", required=False, help="project/source directory")
    parser.add_argument("--platform", "-p", default="freertos", help="target platform")
    parser.add_argument("--profile", choices=sorted(PROFILE_SKIPS), default="default")
    parser.add_argument("--log", action="append", default=[], help="log file, directory, or glob; may repeat")
    parser.add_argument("--output", default="project_gate_report.md", help="Markdown report path")
    parser.add_argument("--evidence", help="optional run_review evidence JSON path")
    parser.add_argument("--repro-output", help="optional repro bundle JSON path")
    parser.add_argument("--strict-logs", action="store_true", help="fail when logs contain P0 findings")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()
    if not args.dir:
        parser.print_help()
        return 2

    review_cmd = [
        sys.executable,
        str(TOOLS_DIR / "run_review.py"),
        "--dir",
        args.dir,
        "--platform",
        args.platform,
        "--json",
        *PROFILE_SKIPS[args.profile],
    ]
    if args.evidence:
        review_cmd.extend(["--evidence", args.evidence])
    if args.repro_output:
        review_cmd.extend(["--repro-output", args.repro_output])

    review_exit, review_data = run_json(review_cmd)

    log_rows: list[dict] = []
    if args.log:
        from log_triage_batch import analyze_file, expand_inputs

        log_rows = [analyze_file(path, args.platform) for path in expand_inputs(args.log)]

    report = render_report(
        target_dir=args.dir,
        platform=args.platform,
        profile=args.profile,
        review_exit=review_exit,
        review_data=review_data,
        log_rows=log_rows,
    )
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report, encoding="utf-8")
    print(f"Project gate report written: {out}")

    if args.strict_logs and any(row.get("max_severity") == "P0" for row in log_rows):
        return max(review_exit, 1)
    return review_exit


if __name__ == "__main__":
    raise SystemExit(main())
