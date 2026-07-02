#!/usr/bin/env python3
"""
Pattern Miner v11.0.4 — 从 evidence store 挖掘经验模式。

从已入库的 evidence 中挖掘高频失败、重复修复、误报热点、长期未修问题，
输出三类候选：新增 checker、checker 精度优化、preset 补强。

用法:
    python tools/pattern_miner.py --store .codex/evidence/store.jsonl
    python tools/pattern_miner.py --store .codex/evidence/store.jsonl --report report.md
    python tools/pattern_miner.py --self-test
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def mine_patterns(entries: list[dict]) -> list[dict]:
    """从 evidence 记录中挖掘模式，返回候选列表。"""
    candidates = []

    # 1. 高频失败 checker
    failed_checkers: Counter = Counter()
    for e in entries:
        if e.get("_type") == "supervisor_report" and e.get("status") in ("failed", "aborted"):
            for vr in e.get("verification_results", []):
                for c in vr.get("checks", []):
                    if not c.get("passed"):
                        failed_checkers[c.get("name", "unknown")] += 1

    for checker, count in failed_checkers.most_common(10):
        if count >= 2:
            candidates.append({
                "type": "checker_precision",
                "title": f"checker '{checker}' 频繁失败 ({count} 次)",
                "description": f"在 {count} 次托管运行中验证失败，建议检查误报或漏报",
                "frequency": count,
                "severity": "P1" if count >= 5 else "P2",
                "confidence": min(0.9, 0.3 + count * 0.1),
                "proposed_action": {
                    "target": "checker",
                    "target_id": checker,
                    "action": "modify",
                    "detail": f"优化 {checker} 的检测精度",
                },
            })

    # 2. 重复修复模式
    fix_types: Counter = Counter()
    for e in entries:
        if e.get("_type") == "supervisor_report":
            plan = e.get("plan", {})
            for fix in plan.get("fix_suggestions", []):
                fix_types[fix.get("fix_type", "unknown")] += 1

    for fix_type, count in fix_types.most_common(5):
        if count >= 3:
            candidates.append({
                "type": "new_checker",
                "title": f"重复修复模式: {fix_type} ({count} 次)",
                "description": f"fix_type '{fix_type}' 在 {count} 次运行中重复出现，建议新增对应 checker",
                "frequency": count,
                "severity": "P1",
                "confidence": min(0.8, 0.2 + count * 0.08),
                "proposed_action": {
                    "target": "checker",
                    "target_id": f"auto_{fix_type}",
                    "action": "add",
                    "detail": f"新增 checker 覆盖 {fix_type} 模式",
                },
            })

    # 3. 风险分布
    high_risk_count = 0
    total_count = 0
    for e in entries:
        if e.get("_type") == "supervisor_report":
            total_count += 1
            plan = e.get("plan", {})
            if plan.get("risk_level") in ("high", "critical"):
                high_risk_count += 1

    if total_count > 0 and high_risk_count / total_count > 0.3:
        candidates.append({
            "type": "workflow_optimization",
            "title": f"高风险任务比例过高 ({high_risk_count}/{total_count})",
            "description": "建议拆分大任务为小任务，降低单次运行风险",
            "frequency": high_risk_count,
            "severity": "P2",
            "confidence": 0.6,
            "proposed_action": {
                "target": "workflow",
                "target_id": "task_decomposition",
                "action": "add",
                "detail": "在 workflow 中增加任务拆分步骤",
            },
        })

    # 4. 门禁拒绝分析
    gate_rejects: Counter = Counter()
    for e in entries:
        if e.get("_type") == "supervisor_report":
            for gate in e.get("gate_decisions", []):
                if gate.get("decision") == "reject":
                    for v in gate.get("violations", []):
                        # 提取门禁类型
                        if "保护路径" in v:
                            gate_rejects["protected_path"] += 1
                        elif "危险命令" in v:
                            gate_rejects["dangerous_command"] += 1
                        elif "critical" in v.lower():
                            gate_rejects["critical_risk"] += 1
                        else:
                            gate_rejects["other"] += 1

    for reason, count in gate_rejects.most_common(5):
        if count >= 2:
            candidates.append({
                "type": "preset_enhancement",
                "title": f"门禁频繁拒绝: {reason} ({count} 次)",
                "description": f"门禁因 '{reason}' 拒绝 {count} 次，建议在 preset/job 中预设更精确的路径/命令约束",
                "frequency": count,
                "severity": "P2",
                "confidence": 0.5,
                "proposed_action": {
                    "target": "preset",
                    "target_id": "auto",
                    "action": "modify",
                    "detail": f"优化 preset 的 allowed_paths/blocked_commands",
                },
            })

    # 按 confidence × frequency 排序
    candidates.sort(key=lambda c: -(c.get("confidence", 0) * c.get("frequency", 0)))

    # 添加 candidate_id
    for i, c in enumerate(candidates):
        c["candidate_id"] = f"LP-{i+1:03d}"
        c["created_at"] = datetime.now(timezone.utc).isoformat()
        c["status"] = "proposed"
        c["evidence_refs"] = []

    return candidates


def format_report(candidates: list[dict]) -> str:
    """格式化 Markdown 报告。"""
    lines = [
        "# Pattern Mining 报告",
        "",
        f"> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"> 候选数: {len(candidates)}",
        "",
    ]

    if not candidates:
        lines.append("未发现可挖掘的模式。evidence store 数据量不足或质量良好。")
        return "\n".join(lines)

    lines.append("## 候选列表")
    lines.append("")
    lines.append("| ID | 类型 | 标题 | 频率 | 严重度 | 置信度 |")
    lines.append("|-----|------|------|------|--------|--------|")

    for c in candidates:
        lines.append(
            f"| {c['candidate_id']} | {c['type']} | {c['title'][:40]} | "
            f"{c.get('frequency', 0)} | {c.get('severity', 'P2')} | "
            f"{c.get('confidence', 0):.0%} |"
        )

    lines.append("")
    lines.append("## 详情")
    lines.append("")

    for c in candidates:
        lines.extend([
            f"### {c['candidate_id']} — {c['title']}",
            "",
            f"- 类型: {c['type']}",
            f"- 频率: {c.get('frequency', 0)}",
            f"- 严重度: {c.get('severity', 'P2')}",
            f"- 置信度: {c.get('confidence', 0):.0%}",
            "",
            f"**描述:** {c.get('description', '')}",
            "",
        ])
        pa = c.get("proposed_action", {})
        if pa:
            lines.extend([
                f"**建议操作:** {pa.get('action', '')} {pa.get('target', '')}/{pa.get('target_id', '')}",
                f"**详情:** {pa.get('detail', '')}",
                "",
            ])

    lines.append("---")
    lines.append("⚠️ 以上为候选提案，需人工确认后才能修改 skill 本体。")
    return "\n".join(lines)


def run_self_test() -> int:
    passed = 0
    failed = 0

    # 构造测试数据
    entries = [
        {"_type": "supervisor_report", "status": "failed",
         "verification_results": [{"checks": [{"name": "run_review_self_test", "passed": False}]}],
         "plan": {"risk_level": "high", "fix_suggestions": [{"fix_type": "goto_cleanup"}]},
         "gate_decisions": []},
        {"_type": "supervisor_report", "status": "failed",
         "verification_results": [{"checks": [{"name": "run_review_self_test", "passed": False}]}],
         "plan": {"risk_level": "low", "fix_suggestions": [{"fix_type": "goto_cleanup"}]},
         "gate_decisions": [{"decision": "reject", "violations": ["保护路径: .git/config"]}]},
        {"_type": "supervisor_report", "status": "failed",
         "verification_results": [{"checks": [{"name": "run_review_self_test", "passed": False}]}],
         "plan": {"risk_level": "low", "fix_suggestions": [{"fix_type": "goto_cleanup"}, {"fix_type": "add_timeout"}]},
         "gate_decisions": []},
        {"_type": "supervisor_report", "status": "success",
         "verification_results": [{"checks": [{"name": "skill_iterate", "passed": True}]}],
         "plan": {"risk_level": "low", "fix_suggestions": [{"fix_type": "add_timeout"}]},
         "gate_decisions": []},
    ]

    candidates = mine_patterns(entries)
    assert len(candidates) > 0, f"Expected candidates, got {len(candidates)}"
    print(f"[PASS] mined {len(candidates)} candidates")
    passed += 1

    # 检查高频失败
    failed_candidates = [c for c in candidates if c["type"] == "checker_precision"]
    assert len(failed_candidates) > 0
    print(f"[PASS] found checker_precision candidate")
    passed += 1

    # 检查重复修复
    fix_candidates = [c for c in candidates if c["type"] == "new_checker"]
    assert len(fix_candidates) > 0
    print(f"[PASS] found new_checker candidate")
    passed += 1

    # 报告生成
    report = format_report(candidates)
    assert "Pattern Mining" in report
    assert "LP-" in report
    print("[PASS] report generation")
    passed += 1

    print(f"\nSelf-test: {passed} passed, {failed} failed")
    return 1 if failed > 0 else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Pattern Miner v11.0.4")
    parser.add_argument("--store", default=str(ROOT / ".codex" / "evidence" / "store.jsonl"))
    parser.add_argument("--report", help="输出 Markdown 报告")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    store_path = Path(args.store)
    if not store_path.exists():
        print(f"Store 不存在: {store_path}", file=sys.stderr)
        return 1

    entries = []
    for line in store_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                pass

    candidates = mine_patterns(entries)

    if args.json:
        print(json.dumps(candidates, indent=2, ensure_ascii=False))
    else:
        report = format_report(candidates)
        if args.report:
            Path(args.report).write_text(report, encoding="utf-8")
            print(f"报告已保存: {args.report}")
        else:
            print(report)

    return 0


if __name__ == "__main__":
    sys.exit(main())
