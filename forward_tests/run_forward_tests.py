#!/usr/bin/env python3
"""
Skill 前向测试运行器 — 验证 skill 触发、懒加载、输出质量。

用法:
    python forward_tests/run_forward_tests.py
    python forward_tests/run_forward_tests.py --test code_review
    python forward_tests/run_forward_tests.py --json
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
OUT_DIR = Path(__file__).resolve().parent / "out"

# Force UTF-8
if sys.platform == "win32":
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")


def _env() -> dict:
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def _run(cmd: str, timeout: int = 120) -> dict:
    """运行命令，返回 {exit_code, stdout, stderr, error}。"""
    try:
        proc = subprocess.run(
            cmd, shell=True, capture_output=True,
            encoding="utf-8", errors="replace",
            timeout=timeout, cwd=str(ROOT), env=_env(),
        )
        return {
            "exit_code": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }
    except subprocess.TimeoutExpired:
        return {"exit_code": -1, "error": "timeout"}
    except Exception as e:
        return {"exit_code": -1, "error": str(e)}


# ============================================================================
# 测试用例
# ============================================================================

def test_code_review() -> dict:
    """测试代码审查：run_review.py --dir examples --json --evidence"""
    evidence_file = OUT_DIR / "review_evidence.json"
    cmd = f'{sys.executable} "{TOOLS / "run_review.py"}" --dir examples --json --evidence "{evidence_file}"'
    result = _run(cmd, timeout=300)

    checks = []
    # 1. 正常退出
    checks.append(("exit_code_ok", result["exit_code"] in (0, 1)))
    # 2. JSON 输出包含 checkers
    if result["exit_code"] >= 0:
        try:
            data = json.loads(result["stdout"])
            checks.append(("has_checkers", "checkers" in data))
            checks.append(("has_total_issues", "total_issues" in data))
        except json.JSONDecodeError:
            checks.append(("json_parse", False))
    # 3. Evidence 文件
    if evidence_file.exists():
        try:
            ev = json.loads(evidence_file.read_text(encoding="utf-8"))
            checks.append(("evidence_source", ev.get("source_tool") == "run_review"))
            checks.append(("evidence_has_issues", "issues" in ev))
        except Exception:
            checks.append(("evidence_parse", False))
    else:
        checks.append(("evidence_file_exists", False))
    # 4. 无 traceback
    checks.append(("no_traceback", "Traceback" not in result.get("stderr", "")))

    return {"test": "code_review", "checks": checks}


def test_crash_analysis() -> dict:
    """测试 crash 分析：repro_bundle.py --workflow debug_crash"""
    output_file = OUT_DIR / "crash_bundle.json"
    cmd = f'{sys.executable} "{TOOLS / "repro_bundle.py"}" --workflow debug_crash --dir examples --platform esp32 --output "{output_file}"'
    result = _run(cmd)

    checks = []
    checks.append(("exit_code_ok", result["exit_code"] == 0))
    if output_file.exists():
        try:
            data = json.loads(output_file.read_text(encoding="utf-8"))
            checks.append(("workflow", data.get("workflow") == "debug_crash"))
            checks.append(("has_environment", "environment" in data))
            checks.append(("has_platform_profile", "platform_profile" in data))
            checks.append(("has_checker_json", "checker_json" in data))
        except Exception:
            checks.append(("json_parse", False))
    else:
        checks.append(("output_file_exists", False))
    checks.append(("no_traceback", "Traceback" not in result.get("stderr", "")))

    return {"test": "crash_analysis", "checks": checks}


def test_generate_module() -> dict:
    """测试生成模块：module_contract_gen.py --modules"""
    outdir = OUT_DIR / "modules"
    # 清理旧输出
    if outdir.exists():
        shutil.rmtree(outdir)

    cmd = f'{sys.executable} "{TOOLS / "module_contract_gen.py"}" --modules audio_player display_mgr --outdir "{outdir}"'
    result = _run(cmd)

    checks = []
    checks.append(("exit_code_ok", result["exit_code"] == 0))
    checks.append(("audio_contract", (outdir / "audio_player_contract.h").exists()))
    checks.append(("audio_fsm", (outdir / "audio_player_fsm.c").exists()))
    checks.append(("display_contract", (outdir / "display_mgr_contract.h").exists()))
    checks.append(("display_fsm", (outdir / "display_mgr_fsm.c").exists()))
    checks.append(("modules_init", (outdir / "modules_init.c").exists()))

    init_file = outdir / "modules_init.c"
    if init_file.exists():
        content = init_file.read_text(encoding="utf-8")
        checks.append(("init_has_audio", "audio_player_init" in content))
        checks.append(("init_has_display", "display_mgr_init" in content))

    checks.append(("no_traceback", "Traceback" not in result.get("stderr", "")))
    return {"test": "generate_module", "checks": checks}


def test_generate_project() -> dict:
    """测试生成项目：project_scaffold.py --preset voice-screen"""
    outdir = OUT_DIR / "project"
    evidence_file = OUT_DIR / "project_evidence.json"
    # 清理旧输出
    if outdir.exists():
        shutil.rmtree(outdir)

    cmd = (f'{sys.executable} "{TOOLS / "project_scaffold.py"}" '
           f'--name test_voice --preset voice-screen --platform esp32 '
           f'--outdir "{outdir}" --evidence "{evidence_file}"')
    result = _run(cmd)

    checks = []
    checks.append(("exit_code_ok", result["exit_code"] == 0))
    proj_dir = outdir / "test_voice"
    checks.append(("cmake", (proj_dir / "CMakeLists.txt").exists()))
    checks.append(("main_c", (proj_dir / "main" / "main.c").exists()))
    checks.append(("app_mvp_h", (proj_dir / "main" / "app_mvp.h").exists()))
    checks.append(("task_topology", (proj_dir / "main" / "task_topology.h").exists()))
    checks.append(("constraint_manifest", (proj_dir / "constraint_manifest.json").exists()))

    main_c = proj_dir / "main" / "main.c"
    if main_c.exists():
        content = main_c.read_text(encoding="utf-8")
        checks.append(("main_has_tasks", "TaskHandle" in content or "task" in content.lower()))

    manifest = proj_dir / "constraint_manifest.json"
    if manifest.exists():
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
            checks.append(("manifest_has_constraints", "required_constraints" in data))
        except Exception:
            checks.append(("manifest_parse", False))

    if evidence_file.exists():
        try:
            ev = json.loads(evidence_file.read_text(encoding="utf-8"))
            checks.append(("evidence_has_files", len(ev.get("generated_files", [])) > 0))
        except Exception:
            checks.append(("evidence_parse", False))

    checks.append(("no_traceback", "Traceback" not in result.get("stderr", "")))
    return {"test": "generate_project", "checks": checks}


def test_auto_fix_plan() -> dict:
    """测试自动修复计划：auto_fix_engine.py --plan"""
    evidence_file = OUT_DIR / "fixplan_evidence.json"
    cmd = (f'{sys.executable} "{TOOLS / "auto_fix_engine.py"}" '
           f'examples/bad_cjson_leak.c --checker cjson --plan --json '
           f'--evidence "{evidence_file}"')
    result = _run(cmd)

    checks = []
    checks.append(("exit_code_ok", result["exit_code"] == 0))

    if result["exit_code"] == 0:
        try:
            data = json.loads(result["stdout"])
            checks.append(("has_actions", "actions" in data and len(data["actions"]) > 0))
            checks.append(("has_total_risk", "total_risk" in data))
            checks.append(("has_pre_flight", "pre_flight" in data))

            if data.get("actions"):
                action = data["actions"][0]
                checks.append(("action_has_risk", "risk_level" in action))
                checks.append(("action_has_confidence", "confidence" in action))
                checks.append(("action_has_pre_checks", "pre_checks" in action))
                checks.append(("action_has_post_checkers", "post_checkers" in action))
        except json.JSONDecodeError:
            checks.append(("json_parse", False))

    if evidence_file.exists():
        try:
            ev = json.loads(evidence_file.read_text(encoding="utf-8"))
            checks.append(("evidence_has_fixes", len(ev.get("fix_suggestions", [])) > 0))
        except Exception:
            checks.append(("evidence_parse", False))

    checks.append(("no_traceback", "Traceback" not in result.get("stderr", "")))
    return {"test": "auto_fix_plan", "checks": checks}


# ============================================================================
# 运行器
# ============================================================================

ALL_TESTS = {
    "code_review": test_code_review,
    "crash_analysis": test_crash_analysis,
    "generate_module": test_generate_module,
    "generate_project": test_generate_project,
    "auto_fix_plan": test_auto_fix_plan,
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Skill 前向测试运行器")
    parser.add_argument("--test", choices=list(ALL_TESTS.keys()), help="运行单个测试")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    parser.add_argument("--clean", action="store_true", help="清理输出目录")
    args = parser.parse_args()

    # 准备输出目录
    if args.clean and OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(exist_ok=True)

    # 运行测试
    tests_to_run = {args.test: ALL_TESTS[args.test]} if args.test else ALL_TESTS
    results = []

    for name, test_fn in tests_to_run.items():
        if not args.json:
            print(f"\n{'=' * 50}")
            print(f"测试: {name}")
            print(f"{'=' * 50}")

        result = test_fn()
        results.append(result)

        if not args.json:
            passed = sum(1 for _, ok in result["checks"] if ok)
            total = len(result["checks"])
            status = "PASS" if passed == total else "FAIL"
            print(f"[{status}] {passed}/{total} checks")
            for check_name, ok in result["checks"]:
                icon = "[OK]" if ok else "[X]"
                print(f"  {icon} {check_name}")

    # 汇总
    total_checks = sum(len(r["checks"]) for r in results)
    passed_checks = sum(sum(1 for _, ok in r["checks"] if ok) for r in results)
    failed_tests = sum(1 for r in results if not all(ok for _, ok in r["checks"]))

    if args.json:
        output = {
            "total_tests": len(results),
            "total_checks": total_checks,
            "passed_checks": passed_checks,
            "failed_tests": failed_tests,
            "results": results,
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print(f"\n{'=' * 50}")
        print(f"汇总: {passed_checks}/{total_checks} checks 通过, {failed_tests} 个测试失败")
        print(f"{'=' * 50}")

    return 1 if failed_tests > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
