#!/usr/bin/env python3
"""
全链路度量仪表盘 — 生成 HTML 报告，展示项目健康度。

功能：
  1. 度量数据持久化到 .skill_metrics/ 目录
  2. 项目健康度评分（0-100）
  3. 生成单页 HTML 仪表盘

用法:
    python tools/metrics_dashboard.py --project ./my_firmware
    python tools/metrics_dashboard.py --project ./my_firmware --output report.html
    python tools/metrics_dashboard.py --self-test
"""

from __future__ import annotations

import argparse
import html
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Force UTF-8 output on Windows
if sys.platform == "win32":
    os.environ.setdefault("PYTHONUTF8", "1")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")


def collect_metrics(project_dir: Path, suite: str = "default") -> dict:
    """收集项目度量数据，从 checker_registry 读取 checker 列表。"""
    from checker_registry import get_suite

    tools_dir = Path(__file__).parent

    # Count files
    c_files = list(project_dir.rglob("*.c"))
    h_files = list(project_dir.rglob("*.h"))

    # Run checkers from registry
    checker_results = {}
    specs = get_suite(suite)

    total_violations = 0
    for spec in specs:
        checker_path = tools_dir / spec.script
        if not checker_path.exists():
            continue

        try:
            env = os.environ.copy()
            env["PYTHONUTF8"] = "1"
            result = subprocess.run(
                [sys.executable, str(checker_path), "--dir", str(project_dir)],
                capture_output=True, text=True, timeout=60, env=env,
                encoding="utf-8", errors="replace"
            )
            output = result.stdout + result.stderr
            violations = 0
            for line in output.splitlines():
                if line.strip().startswith("[P") and "]" in line:
                    violations += 1

            checker_results[spec.name] = {
                "checker": spec.script,
                "domains": list(spec.domains),
                "violations": violations,
            }
            total_violations += violations
        except Exception:
            checker_results[spec.name] = {
                "checker": spec.script,
                "domains": list(spec.domains),
                "violations": -1,
            }

    return {
        "timestamp": datetime.now().isoformat(),
        "project": str(project_dir),
        "suite": suite,
        "files": {
            "c_files": len(c_files),
            "h_files": len(h_files),
            "total": len(c_files) + len(h_files),
        },
        "checkers": checker_results,
        "total_violations": total_violations,
    }


def calculate_health_score(metrics: dict) -> dict:
    """计算项目健康度评分（0-100）"""
    score = 100
    issues = []

    # Deduct for violations
    violations = metrics.get("total_violations", 0)
    if violations > 0:
        deduction = min(violations * 2, 50)  # Max 50 points deducted
        score -= deduction
        issues.append(f"{violations} violations (-{deduction})")

    # Deduct for checker failures
    failed_checkers = sum(
        1 for v in metrics.get("checkers", {}).values()
        if v.get("violations", 0) < 0
    )
    if failed_checkers > 0:
        deduction = failed_checkers * 5
        score -= deduction
        issues.append(f"{failed_checkers} checker errors (-{deduction})")

    # Bonus for having files (project not empty)
    if metrics.get("files", {}).get("total", 0) == 0:
        score = 0
        issues.append("Empty project")

    score = max(0, min(100, score))

    # Determine grade
    if score >= 90:
        grade = "A"
    elif score >= 80:
        grade = "B"
    elif score >= 70:
        grade = "C"
    elif score >= 60:
        grade = "D"
    else:
        grade = "F"

    return {
        "score": score,
        "grade": grade,
        "issues": issues,
    }


def generate_html_dashboard(metrics: dict, health: dict) -> str:
    """生成 HTML 仪表盘"""
    checker_rows = ""
    for domain, result in sorted(metrics.get("checkers", {}).items()):
        violations = result.get("violations", 0)
        status = "PASS" if violations == 0 else f"FAIL ({violations})"
        color = "#4CAF50" if violations == 0 else "#f44336"
        esc_domain = html.escape(str(domain))
        esc_checker = html.escape(str(result.get("checker", "-")))
        checker_rows += f'<tr><td>{esc_domain}</td><td>{esc_checker}</td><td style="color:{color}">{status}</td></tr>\n'

    issues_html = ""
    for issue in health.get("issues", []):
        issues_html += f'<li>{html.escape(str(issue))}</li>\n'

    score = health.get("score", 0)
    grade = health.get("grade", "F")
    score_color = "#4CAF50" if score >= 80 else "#FF9800" if score >= 60 else "#f44336"

    html_str = f'''<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>FreeRTOS Skill Metrics Dashboard</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
.card {{ background: white; border-radius: 8px; padding: 20px; margin: 10px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
.score {{ font-size: 48px; font-weight: bold; color: {score_color}; }}
.grade {{ font-size: 36px; color: {score_color}; }}
table {{ width: 100%; border-collapse: collapse; }}
th, td {{ padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }}
th {{ background: #f0f0f0; }}
h1 {{ color: #333; }}
h2 {{ color: #663; }}
</style>
</head>
<body>
<h1>FreeRTOS Skill Metrics Dashboard</h1>
<p>Generated: {html.escape(str(metrics.get("timestamp", "N/A")))}</p>
<p>Project: {html.escape(str(metrics.get("project", "N/A")))} · Suite: {html.escape(str(metrics.get("suite", "default")))}</p>

<div class="card">
<h2>Health Score</h2>
<span class="score">{score}</span> / 100
<span class="grade">Grade: {grade}</span>
<ul>{issues_html}</ul>
</div>

<div class="card">
<h2>Project Statistics</h2>
<p>C Files: {metrics.get("files", {}).get("c_files", 0)}</p>
<p>H Files: {metrics.get("files", {}).get("h_files", 0)}</p>
<p>Total Violations: {metrics.get("total_violations", 0)}</p>
</div>

<div class="card">
<h2>Checker Results</h2>
<table>
<tr><th>Domain</th><th>Checker</th><th>Status</th></tr>
{checker_rows}
</table>
</div>
</body>
</html>'''
    return html_str


def run_self_test() -> int:
    """自测"""
    passed = 0
    failed = 0

    # Test 1: Health score calculation
    metrics = {"total_violations": 0, "checkers": {}, "files": {"total": 10}}
    health = calculate_health_score(metrics)
    assert health["score"] == 100, f"Expected 100, got {health['score']}"
    assert health["grade"] == "A"
    print("[PASS] health score: no violations = 100")
    passed += 1

    # Test 2: Health score with violations
    metrics = {"total_violations": 5, "checkers": {}, "files": {"total": 10}}
    health = calculate_health_score(metrics)
    assert health["score"] < 100, f"Expected <100, got {health['score']}"
    print(f"[PASS] health score: 5 violations = {health['score']}")
    passed += 1

    # Test 3: HTML generation
    html = generate_html_dashboard(metrics, health)
    assert "Health Score" in html
    assert "Checker Results" in html
    print("[PASS] HTML generation")
    passed += 1

    # Test 4: Empty project
    metrics = {"total_violations": 0, "checkers": {}, "files": {"total": 0}}
    health = calculate_health_score(metrics)
    assert health["score"] == 0
    print("[PASS] empty project = 0")
    passed += 1

    print(f"\nSelf-test: {passed} passed, {failed} failed")
    return 1 if failed > 0 else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="全链路度量仪表盘")
    parser.add_argument("--project", "-p", help="项目目录")
    parser.add_argument("--output", "-o", help="HTML 输出文件")
    parser.add_argument("--suite", default="default",
                        choices=["default", "all", "security", "media", "platform", "realtime", "enhanced"],
                        help="checker suite (default: default)")
    parser.add_argument("--evidence", metavar="FILE", help="输出交付证据包到指定文件")
    parser.add_argument("--evidence-dir", metavar="DIR", help="读取证据包目录做趋势分析")
    parser.add_argument("--self-test", action="store_true", help="运行自测")
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    if not args.project:
        parser.print_help()
        return 1

    project_dir = Path(args.project)
    if not project_dir.is_dir():
        print(f"Error: {project_dir} is not a directory")
        return 1

    # Collect metrics
    print(f"[metrics_dashboard] Collecting metrics from {project_dir} (suite={args.suite})...")
    metrics = collect_metrics(project_dir, suite=args.suite)

    # Calculate health
    health = calculate_health_score(metrics)
    metrics["health"] = health

    # Save metrics
    metrics_dir = project_dir / ".skill_metrics"
    metrics_dir.mkdir(exist_ok=True)
    metrics_file = metrics_dir / f"metrics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    metrics_file.write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[metrics_dashboard] Metrics saved to {metrics_file}")

    # Generate HTML
    html = generate_html_dashboard(metrics, health)
    output_file = Path(args.output) if args.output else metrics_dir / "dashboard.html"
    output_file.write_text(html, encoding="utf-8")
    print(f"[metrics_dashboard] Dashboard saved to {output_file}")

    # Print summary
    print(f"\n=== Health Score: {health['score']}/100 (Grade {health['grade']}) ===")
    for issue in health.get("issues", []):
        print(f"  - {issue}")

    # ── 交付证据包输出 ──
    if args.evidence:
        from evidence_schema import issue_entry, make_evidence, save_evidence

        ev_issues = []
        for checker_name, checker_data in metrics.get("checkers", {}).items():
            violations = checker_data.get("violations", 0)
            if violations > 0:
                ev_issues.append(issue_entry(
                    cid=checker_name, severity="P2",
                    file=str(project_dir),
                    message=f"{violations} 个违规",
                    checker=checker_name,
                ))

        ev = make_evidence(
            source_tool="metrics_dashboard",
            suite=args.suite,
            issues=ev_issues,
            metadata={
                "tool_version": "9.0.1",
                "health_score": health["score"],
                "health_grade": health["grade"],
                "total_violations": metrics.get("total_violations", 0),
                "files_total": metrics.get("files", {}).get("total", 0),
            },
        )
        save_evidence(ev, args.evidence)
        print(f"[evidence] 已保存交付证据包: {args.evidence}")

    # ── 证据目录趋势分析 ──
    if args.evidence_dir:
        from evidence_schema import load_evidence
        evidence_dir = Path(args.evidence_dir)
        if evidence_dir.is_dir():
            ev_files = sorted(evidence_dir.glob("*.json"))
            if ev_files:
                print(f"\n=== 证据趋势分析 ({len(ev_files)} 个证据包) ===")
                for ef in ev_files[-5:]:  # 最近 5 个
                    try:
                        ev = load_evidence(ef)
                        score = ev.metadata.get("health_score", "N/A")
                        issues = len(ev.issues)
                        print(f"  {ef.name}: score={score}, issues={issues}")
                    except Exception as exc:
                        print(f"  {ef.name}: 解析失败 ({exc})")
            else:
                print(f"[evidence-dir] 目录为空: {evidence_dir}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
