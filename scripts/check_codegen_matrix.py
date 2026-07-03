#!/usr/bin/env python3
"""
Codegen Matrix 检查 — 五 preset 生成后逐个跑 codegen_gate --strict。

用法:
    python scripts/check_codegen_matrix.py
    python scripts/check_codegen_matrix.py --self-test
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"

PRESETS = ["voice_screen", "audio_video", "low_power_sensor", "ota_network", "pure_controller"]

# 风险预算（每个 preset 允许的 P1/P2 上限）
RISK_BUDGET = {
    "voice_screen": {"p1": 10, "p2": 15},
    "audio_video": {"p1": 10, "p2": 15},
    "low_power_sensor": {"p1": 5, "p2": 10},
    "ota_network": {"p1": 8, "p2": 12},
    "pure_controller": {"p1": 5, "p2": 10},
}

def run_cmd(cmd: str, timeout: int = 120) -> dict:
    try:
        proc = subprocess.run(
            cmd, shell=True, capture_output=True, encoding="utf-8", errors="replace",
            timeout=timeout, cwd=str(ROOT), env={**os.environ, "PYTHONUTF8": "1"},
        )
        return {"exit_code": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}
    except subprocess.TimeoutExpired:
        return {"exit_code": -1, "error": "timeout"}
    except Exception as e:
        return {"exit_code": -1, "error": str(e)}


def check_preset(preset: str, tmpdir: Path) -> dict:
    """检查单个 preset。"""
    project_name = f"matrix_{preset}"
    project_dir = tmpdir / project_name / project_name
    manifest_path = project_dir / "generation_manifest.json"

    # 1. Generate
    r = run_cmd(f'{sys.executable} "{TOOLS / "project_scaffold.py"}" --name {project_name} --preset {preset} --platform esp32 --outdir "{tmpdir / project_name}"')
    if r["exit_code"] != 0:
        return {"preset": preset, "passed": False, "errors": [f"scaffold 失败: {r.get('error', r.get('stderr', '')[:200])}"]}

    # 2. Check manifest exists
    if not manifest_path.exists():
        return {"preset": preset, "passed": False, "errors": ["generation_manifest.json 不存在"]}

    # 3. Check generated_files includes README/config/Kconfig
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    gen_files = {f["path"] for f in manifest.get("generated_files", [])}
    missing_files = []
    if "README.md" not in gen_files:
        missing_files.append("README.md")
    if not any(k in gen_files for k in ["sdkconfig.defaults", "prj.conf", "FreeRTOSConfig.h"]):
        missing_files.append("config file")
    if "Kconfig.projbuild" not in gen_files and manifest.get("platform") == "esp32":
        missing_files.append("Kconfig.projbuild")

    # 4. Check verification_commands includes active user gates
    vcmds = " ".join(manifest.get("verification_commands", []))
    missing_cmds = []
    for a in ["codegen_gate.py", "run_review.py"]:
        if a not in vcmds:
            missing_cmds.append(a)

    # 5. Run codegen_gate --strict --json
    r = run_cmd(f'{sys.executable} "{TOOLS / "codegen_gate.py"}" --dir "{project_dir}" --manifest "{manifest_path}" --platform esp32 --strict --json')
    if r["exit_code"] != 0 and r["exit_code"] != 1:
        return {"preset": preset, "passed": False, "errors": [f"gate 异常: exit={r['exit_code']}"]}

    try:
        gate = json.loads(r["stdout"])
    except json.JSONDecodeError:
        return {"preset": preset, "passed": False, "errors": [f"gate JSON 解析失败"]}

    # 6. Track optional archived analyzer presence for diagnostics only.
    analyzer_reports = gate.get("analyzer_reports", {})
    missing_analyzers = set(gate.get("missing_analyzers", []))

    # 7. Check risk budget
    risks = gate.get("risk_summary", {})
    budget = RISK_BUDGET.get(preset, {"p1": 10, "p2": 15})
    budget_exceeded = []
    if risks.get("p1", 0) > budget["p1"]:
        budget_exceeded.append(f"P1={risks['p1']} > budget={budget['p1']}")
    if risks.get("p2", 0) > budget["p2"]:
        budget_exceeded.append(f"P2={risks['p2']} > budget={budget['p2']}")

    # Collect errors
    errors = []
    if missing_files:
        errors.append(f"generated_files 缺少: {missing_files}")
    if missing_cmds:
        errors.append(f"verification_commands 缺少用户验证命令: {missing_cmds}")
    if not gate.get("passed"):
        errors.append(f"gate failed: {gate.get('errors', [])[:3]}")
    if budget_exceeded:
        errors.append(f"风险预算超限: {budget_exceeded}")

    return {
        "preset": preset,
        "passed": len(errors) == 0,
        "errors": errors,
        "gate_passed": gate.get("passed"),
        "p0": risks.get("p0", 0),
        "p1": risks.get("p1", 0),
        "p2": risks.get("p2", 0),
        "analyzers": sorted(analyzer_reports.keys()),
        "missing_analyzers": sorted(missing_analyzers),
        "budget_exceeded": budget_exceeded,
    }


def check_all() -> dict:
    """检查全部 preset。"""
    results = []
    all_passed = True

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        for preset in PRESETS:
            r = check_preset(preset, tmpdir)
            results.append(r)
            if not r["passed"]:
                all_passed = False

    return {
        "passed": all_passed,
        "total": len(results),
        "passed_count": sum(1 for r in results if r["passed"]),
        "results": results,
    }


def run_self_test() -> int:
    passed = 0
    failed = 1

    # 1. check_all 基本结构
    r = check_all()
    assert "passed" in r
    assert "results" in r
    assert r["total"] == 5
    print(f"[PASS] check_all: {r['passed_count']}/{r['total']} presets")
    passed += 1
    failed -= 1

    # 2. 每个 preset 结果结构
    for pr in r["results"]:
        assert "preset" in pr
        assert "passed" in pr
        assert "errors" in pr
    print("[PASS] result structure valid")
    passed += 1

    # 3. 风险预算检查
    for pr in r["results"]:
        if pr.get("budget_exceeded"):
            print(f"  [WARN] {pr['preset']}: budget exceeded {pr['budget_exceeded']}")
    print("[PASS] risk budget checked")
    passed += 1

    print(f"\nSelf-test: {passed} passed, {failed} failed")
    return 1 if failed > 0 else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Codegen Matrix 检查")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    r = check_all()

    if args.json:
        print(json.dumps(r, indent=2, ensure_ascii=False))
    else:
        print(f"Codegen Matrix: {r['passed_count']}/{r['total']} presets passed")
        for pr in r["results"]:
            icon = "[PASS]" if pr["passed"] else "[FAIL]"
            print(f"  {icon} {pr['preset']}: P0={pr.get('p0',0)} P1={pr.get('p1',0)} P2={pr.get('p2',0)}")
            if pr["errors"]:
                for e in pr["errors"][:3]:
                    print(f"    - {e}")

    return 0 if r["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
