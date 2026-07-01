#!/usr/bin/env python3
"""
效率度量工具 — 量化 20x 提效目标。

功能：
  1. 扫描项目目录，统计文件数/函数数/队列数/任务数
  2. 对照 checker 输出计算 review 时间节省
  3. 输出结构化度量报告

用法:
    python tools/efficiency_scorecard.py --project ./my_firmware
    python tools/efficiency_scorecard.py --project ./my_firmware --json
    python tools/efficiency_scorecard.py --project ./my_firmware --report report.md
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from datetime import datetime

# Force UTF-8 output on Windows
if sys.platform == "win32":
    os.environ.setdefault("PYTHONUTF8", "1")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")


def count_c_files(project_dir: Path) -> int:
    """统计 C 源文件数"""
    return len(list(project_dir.rglob("*.c")))


def count_functions(project_dir: Path) -> int:
    """统计函数数"""
    count = 0
    func_pattern = re.compile(
        r'^(?:static\s+)?(?:void|int|esp_err_t|bool|float|double|char|uint\w+|int\w+|size_t|BaseType_t)\s+\w+\s*\(',
        re.MULTILINE
    )
    for c_file in project_dir.rglob("*.c"):
        try:
            text = c_file.read_text(encoding="utf-8", errors="replace")
            count += len(func_pattern.findall(text))
        except OSError:
            continue
    return count


def count_queues(project_dir: Path) -> int:
    """统计 Queue 创建数"""
    count = 0
    for c_file in project_dir.rglob("*.c"):
        try:
            text = c_file.read_text(encoding="utf-8", errors="replace")
            count += len(re.findall(r'xQueueCreate\s*\(', text))
        except OSError:
            continue
    return count


def count_tasks(project_dir: Path) -> int:
    """统计任务创建数"""
    count = 0
    for c_file in project_dir.rglob("*.c"):
        try:
            text = c_file.read_text(encoding="utf-8", errors="replace")
            count += len(re.findall(r'xTaskCreate\s*\(', text))
        except OSError:
            continue
    return count


def count_lines(project_dir: Path) -> int:
    """统计代码行数"""
    total = 0
    for c_file in project_dir.rglob("*.c"):
        try:
            total += sum(1 for _ in c_file.open(encoding="utf-8", errors="replace"))
        except OSError:
            continue
    return total


def run_checkers(project_dir: Path) -> dict:
    """运行所有 checker 并统计违规数"""
    import subprocess

    checker_results = {}
    tools_dir = Path(__file__).parent

    checkers = [
        ("cjson_leak_checker.py", "C3"),
        ("isr_safety_checker.py", "C4"),
        ("lvgl_thread_checker.py", "C1"),
        ("queue_ownership_checker.py", "C2"),
        ("blocking_wait_checker.py", "C31"),
        ("ota_safety_checker.py", "C22"),
    ]

    for checker, domain in checkers:
        checker_path = tools_dir / checker
        if not checker_path.exists():
            continue

        try:
            env = os.environ.copy()
            env["PYTHONUTF8"] = "1"
            result = subprocess.run(
                [sys.executable, str(checker_path), "--dir", str(project_dir)],
                capture_output=True, text=True, timeout=60, env=env, encoding="utf-8", errors="replace"
            )
            # Parse output for violation count
            output = result.stdout + result.stderr
            violations = 0
            match = re.search(r'(\d+)\s+(?:个|C\d+)', output)
            if match:
                violations = int(match.group(1))

            checker_results[domain] = {
                "checker": checker,
                "violations": violations,
                "exit_code": result.returncode,
            }
        except (subprocess.TimeoutExpired, Exception) as e:
            checker_results[domain] = {
                "checker": checker,
                "violations": -1,
                "error": str(e),
            }

    return checker_results


def calculate_efficiency(project_stats: dict, checker_results: dict) -> dict:
    """计算效率指标"""
    # 基线估算（人工 review 时间）
    c_files = project_stats.get("c_files", 0)
    functions = project_stats.get("functions", 0)
    lines = project_stats.get("lines", 0)

    # 人工 review 估算：每文件 15 分钟，每函数 2 分钟
    manual_review_hours = (c_files * 15 + functions * 2) / 60

    # checker 自动化 review 时间：每文件 0.1 秒
    auto_review_seconds = c_files * 0.1
    auto_review_hours = auto_review_seconds / 3600

    # 效率提升
    if auto_review_hours > 0:
        review_ratio = manual_review_hours / auto_review_hours
    else:
        review_ratio = float('inf')

    # 违规统计
    total_violations = sum(
        r.get("violations", 0)
        for r in checker_results.values()
        if r.get("violations", 0) > 0
    )

    return {
        "manual_review_hours": round(manual_review_hours, 1),
        "auto_review_hours": round(auto_review_hours, 3),
        "review_efficiency_ratio": round(review_ratio, 0),
        "total_violations": total_violations,
        "checker_coverage": f"{len(checker_results)} domains",
    }


def generate_report(project_stats: dict, checker_results: dict, efficiency: dict) -> str:
    """生成 Markdown 报告"""
    report = []
    report.append("# FreeRTOS Skill 效率度量报告\n")
    report.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    report.append("## 项目统计\n")
    report.append(f"| 指标 | 数值 |")
    report.append(f"|------|------|")
    report.append(f"| C 源文件数 | {project_stats.get('c_files', 0)} |")
    report.append(f"| 函数数 | {project_stats.get('functions', 0)} |")
    report.append(f"| 代码行数 | {project_stats.get('lines', 0)} |")
    report.append(f"| Queue 创建数 | {project_stats.get('queues', 0)} |")
    report.append(f"| 任务创建数 | {project_stats.get('tasks', 0)} |")

    report.append("\n## Checker 覆盖\n")
    report.append(f"| 约束域 | Checker | 违规数 |")
    report.append(f"|--------|---------|--------|")
    for domain, result in sorted(checker_results.items()):
        violations = result.get("violations", 0)
        status = f"{violations}" if violations >= 0 else "error"
        report.append(f"| {domain} | {result.get('checker', '-')} | {status} |")

    report.append("\n## 效率指标\n")
    report.append(f"| 维度 | 人工 | 自动化 | 提效倍数 |")
    report.append(f"|------|------|--------|----------|")
    report.append(f"| Code Review | {efficiency['manual_review_hours']}h | {efficiency['auto_review_hours']}h | {efficiency['review_efficiency_ratio']}x |")
    report.append(f"| 违规检测 | 人工逐行 | {efficiency['checker_coverage']} | - |")
    report.append(f"| 总违规数 | - | {efficiency['total_violations']} | - |")

    report.append("\n## 20x 目标进度\n")
    ratio = efficiency['review_efficiency_ratio']
    if ratio >= 20:
        report.append(f"**Code Review 提效 {ratio}x — 已达到 20x 目标!**")
    else:
        progress = (ratio / 20) * 100
        report.append(f"**Code Review 提效 {ratio}x — 进度 {progress:.0f}%**")
        report.append(f"\n建议：增加 checker 覆盖率以提升自动化比例。")

    return "\n".join(report)


def main() -> int:
    parser = argparse.ArgumentParser(description="效率度量工具")
    parser.add_argument("--project", "-p", required=True, help="项目目录")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    parser.add_argument("--report", "-r", help="生成 Markdown 报告文件")
    args = parser.parse_args()

    project_dir = Path(args.project)
    if not project_dir.is_dir():
        print(f"Error: {project_dir} is not a directory")
        return 1

    print(f"[efficiency_scorecard] Scanning {project_dir}...")

    # 收集项目统计
    project_stats = {
        "c_files": count_c_files(project_dir),
        "functions": count_functions(project_dir),
        "lines": count_lines(project_dir),
        "queues": count_queues(project_dir),
        "tasks": count_tasks(project_dir),
    }

    # 运行 checkers
    print(f"[efficiency_scorecard] Running checkers...")
    checker_results = run_checkers(project_dir)

    # 计算效率
    efficiency = calculate_efficiency(project_stats, checker_results)

    if args.json:
        output = {
            "project_stats": project_stats,
            "checker_results": checker_results,
            "efficiency": efficiency,
        }
        print(json.dumps(output, indent=2, ensure_ascii=False))
    elif args.report:
        report = generate_report(project_stats, checker_results, efficiency)
        Path(args.report).write_text(report, encoding="utf-8")
        print(f"[efficiency_scorecard] Report saved to {args.report}")
    else:
        print(f"\n=== 项目统计 ===")
        for key, value in project_stats.items():
            print(f"  {key}: {value}")

        print(f"\n=== Checker 覆盖 ===")
        for domain, result in sorted(checker_results.items()):
            violations = result.get("violations", 0)
            print(f"  {domain}: {result.get('checker', '-')} -> {violations} violations")

        print(f"\n=== 效率指标 ===")
        print(f"  人工 Review: {efficiency['manual_review_hours']}h")
        print(f"  自动 Review: {efficiency['auto_review_hours']}h")
        print(f"  提效倍数: {efficiency['review_efficiency_ratio']}x")
        print(f"  总违规数: {efficiency['total_violations']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
