#!/usr/bin/env python3
"""
Skill 自我迭代验证闭环。

用法（仓库根目录）:
    python scripts/skill_iterate.py --check
    python scripts/skill_iterate.py --check --sync
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = ROOT / "tools"
SKILL = ROOT / "SKILL.md"
LITE_ROOT = ROOT / "freertos-skill-lite"
LITE_SKILL = LITE_ROOT / "SKILL.md"
CHANGELOG = ROOT / "CHANGELOG.md"
ITERATION_LOG = ROOT / "references" / "iteration_log.md"


def checker_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    return env


def read_version(path: Path) -> str | None:
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    m = re.search(r"^version:\s*([^\s#]+)", text, re.MULTILINE)
    if m:
        return m.group(1).strip()
    m = re.search(
        r"^metadata:\s*\n(?:[ \t]+[^\n]*\n)*?[ \t]+version:\s*([^\s#]+)",
        text,
        re.MULTILINE,
    )
    return m.group(1).strip() if m else None


def run(cmd: list[str], cwd: Path) -> int:
    print(" ", " ".join(cmd))
    return subprocess.run(cmd, cwd=cwd, env=checker_env()).returncode


def check_checker_registry() -> list[str]:
    sys.path.insert(0, str(TOOLS_DIR))
    try:
        from checker_registry import DEFAULT_CHECKERS, SELF_TEST_CASES, VALIDATE_EXAMPLE_CASES
    except Exception as exc:  # pragma: no cover - defensive validation path
        return [f"checker_registry.py 导入失败: {exc}"]

    errors: list[str] = []
    skip_args: set[str] = set()
    names: set[str] = set()
    valid_modes = {"per-file", "batch"}

    for spec in DEFAULT_CHECKERS:
        script_path = TOOLS_DIR / spec.script
        if not script_path.is_file():
            errors.append(f"checker 脚本不存在: {spec.script}")
        if spec.skip_arg in skip_args:
            errors.append(f"checker skip 参数重复: --skip-{spec.skip_arg}")
        skip_args.add(spec.skip_arg)
        if spec.name in names:
            errors.append(f"checker name 重复: {spec.name}")
        names.add(spec.name)
        if spec.mode not in valid_modes:
            errors.append(f"checker mode 非法: {spec.name} mode={spec.mode}")

    groups = (
        ("self-test", TOOLS_DIR, SELF_TEST_CASES),
        ("validate-examples", ROOT, VALIDATE_EXAMPLE_CASES),
    )
    for group_name, base_dir, cases in groups:
        for case in cases:
            if not (TOOLS_DIR / case.script).is_file():
                errors.append(f"{group_name} 引用不存在的 checker: {case.script}")
            if not (base_dir / case.path).is_file():
                errors.append(f"{group_name} 引用不存在的样例: {case.path}")
            if case.expected not in (0, 1):
                errors.append(f"{group_name} 期望退出码非法: {case.label} expected={case.expected}")

    if not errors:
        print("  checker_registry.py OK")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Skill 自我迭代验证")
    parser.add_argument("--check", action="store_true", help="仓库内快速门禁（默认）")
    parser.add_argument("--release", action="store_true", help="完整发布门禁（含安装版同步）")
    parser.add_argument("--install", action="store_true", help="--release 时先 clean install")
    parser.add_argument("--install-dir", help="安装目录（默认 Codex skill 目录）")
    parser.add_argument("--forward", action="store_true", help="--release 时运行 forward eval")
    parser.add_argument("--sync", action="store_true", help="验证通过后执行 sync_lite.py")
    parser.add_argument("--skip-self-test", action="store_true")
    args = parser.parse_args()
    if not args.check and not args.sync and not args.release:
        args.check = True

    errors: list[str] = []
    mode = "Release" if args.release else "Check"
    print("=" * 60)
    print(f"Skill {mode} Gate")
    print("=" * 60)

    step = 0
    total = 21 if args.release else 17

    def _step(label: str):
        nonlocal step
        step += 1
        print(f"\n[{step}/{total}] {label}")

    # ── 1. run_review self-test ──
    if not args.skip_self_test:
        _step("tools/run_review.py --self-test")
        rc = run([sys.executable, str(ROOT / "tools" / "run_review.py"), "--self-test"], ROOT)
        if rc != 0:
            errors.append("run_review --self-test 失败")

    # ── 2. validate-examples ──
    _step("tools/run_review.py --validate-examples")
    rc = run([sys.executable, str(ROOT / "tools" / "run_review.py"), "--validate-examples"], ROOT)
    if rc != 0:
        errors.append("run_review --validate-examples 失败")

    # ── 3. checker registry ──
    _step("checker registry")
    errors.extend(check_checker_registry())

    # ── 4. runtime distribution ──
    _step("runtime distribution boundary")
    rc = run([sys.executable, str(ROOT / "scripts" / "check_runtime_distribution.py")], ROOT)
    if rc != 0:
        errors.append("check_runtime_distribution.py failed")

    # ── 5. skill metadata ──
    _step("skill metadata contract")
    rc = run([sys.executable, str(ROOT / "scripts" / "check_skill_metadata.py")], ROOT)
    if rc != 0:
        errors.append("check_skill_metadata.py failed")

    # -- 6. MCP adapter --
    _step("mcp/server.py --self-test")
    rc = run([sys.executable, str(ROOT / "mcp" / "server.py"), "--self-test"], ROOT)
    if rc != 0:
        errors.append("mcp/server.py --self-test failed")

    # ── 7. SKILL.md version ──
    _step("SKILL.md version")
    full_ver = read_version(SKILL)
    lite_ver = read_version(LITE_SKILL) if LITE_ROOT.is_dir() else None
    if not full_ver:
        errors.append("SKILL.md 缺少 metadata.version 字段")
    else:
        print(f"  完整版: {full_ver}")
    if LITE_ROOT.is_dir():
        if lite_ver:
            print(f"  Lite:   {lite_ver}")
            if full_ver and lite_ver != full_ver:
                errors.append(f"版本不一致: 完整版 {full_ver} vs Lite {lite_ver}")
        else:
            errors.append("freertos-skill-lite/SKILL.md 缺失或无 version")
    else:
        print("  Lite:   skipped (freertos-skill-lite/ is not source-tracked)")

    # -- 8. CHANGELOG / iteration_log --
    _step("CHANGELOG / iteration_log")
    if not CHANGELOG.is_file():
        errors.append("缺少 CHANGELOG.md")
    elif full_ver and full_ver not in CHANGELOG.read_text(encoding="utf-8")[:800]:
        errors.append(f"CHANGELOG.md 未提及当前版本 {full_ver}")
    else:
        print("  CHANGELOG.md OK")
    if not ITERATION_LOG.is_file():
        errors.append("缺少 references/iteration_log.md")
    else:
        print("  iteration_log.md OK")

    # -- 9. commit audit self-test --
    _step("commit_audit --self-test")
    rc = run([sys.executable, str(ROOT / "scripts" / "commit_audit.py"), "--self-test"], ROOT)
    if rc != 0:
        errors.append("commit_audit.py --self-test failed")

    # -- 10. strategy entry mapping --
    _step("strategy entry mapping")
    rc = run(
        [
            sys.executable,
            str(ROOT / "tools" / "strategy_entry_audit.py"),
            "--prompt",
            str(ROOT / "prompts" / "lcd_display_driver.txt"),
            "--section",
            "19.2",
        ],
        ROOT,
    )
    if rc != 0:
        errors.append("strategy_entry_audit.py failed")

    # -- 11. commit audit --
    _step("commit_audit --strict-release")
    rc = run([sys.executable, str(ROOT / "scripts" / "commit_audit.py"), "--max-log", "8", "--strict-release"], ROOT)
    if rc != 0:
        errors.append("commit_audit.py --strict-release failed")

    # -- 12. sync_lite dry-run --
    _step("sync_lite --dry-run")
    if LITE_ROOT.is_dir():
        rc = run([sys.executable, str(ROOT / "scripts" / "sync_lite.py"), "--dry-run"], ROOT)
        if rc != 0:
            errors.append("sync_lite.py --dry-run 失败")
    else:
        print("  skipped (freertos-skill-lite/ absent)")

    # -- 13. evidence_schema --
    _step("evidence_schema --self-test")
    evidence_schema = ROOT / "tools" / "evidence_schema.py"
    if evidence_schema.is_file():
        rc = run([sys.executable, str(evidence_schema), "--self-test"], ROOT)
        if rc != 0:
            errors.append("evidence_schema.py --self-test 失败")
    else:
        print("  skipped (archived tool not present)")

    # -- 14. log_triage --
    _step("log_triage --self-test")
    rc = run([sys.executable, str(ROOT / "tools" / "log_triage.py"), "--self-test"], ROOT)
    if rc != 0:
        errors.append("log_triage.py --self-test 失败")

    # -- 15. log triage matrix --
    _step("check_log_triage_matrix")
    rc = run([sys.executable, str(ROOT / "scripts" / "check_log_triage_matrix.py")], ROOT)
    if rc != 0:
        errors.append("check_log_triage_matrix.py 失败")

    # -- 16. codegen matrix --
    _step("check_codegen_matrix")
    rc = run([sys.executable, str(ROOT / "scripts" / "check_codegen_matrix.py")], ROOT)
    if rc != 0:
        errors.append("check_codegen_matrix.py 失败")

    # -- 17. sync_lite --
    _step("sync_lite")
    if args.sync and not errors and LITE_ROOT.is_dir():
        rc = run([sys.executable, str(ROOT / "scripts" / "sync_lite.py")], ROOT)
        if rc != 0:
            errors.append("sync_lite.py 失败")
        else:
            lite_ver2 = read_version(LITE_SKILL)
            if full_ver and lite_ver2 != full_ver:
                errors.append("sync 后 Lite 版本仍与完整版不一致")
    elif args.sync and not LITE_ROOT.is_dir():
        print("  skipped (freertos-skill-lite/ absent)")
    elif args.sync:
        print("  跳过 sync（存在前置错误）")
    else:
        print("  跳过（未指定 --sync）")

    # -- 18. Release-only: install --
    if args.release and args.install:
        _step("install_release_skill (clean install)")
        install_cmd = [sys.executable, str(ROOT / "scripts" / "install_release_skill.py")]
        if args.install_dir:
            install_cmd.extend(["--dst", args.install_dir])
        rc = run(install_cmd, ROOT)
        if rc != 0:
            errors.append("安装失败")

    # -- 19. Release-only: version sync --
    if args.release:
        _step("check_installed_skill_sync --strict")
        sync_cmd = [sys.executable, str(ROOT / "scripts" / "check_installed_skill_sync.py"), "--strict"]
        if args.install_dir:
            sync_cmd.extend(["--install-dir", args.install_dir])
        rc = run(sync_cmd, ROOT)
        if rc != 0:
            errors.append("安装版版本同步失败")

    # -- 20. Release-only: runtime audit --
    if args.release:
        _step("check_installed_runtime --strict")
        runtime_cmd = [sys.executable, str(ROOT / "scripts" / "check_installed_runtime.py"), "--strict"]
        if args.install_dir:
            runtime_cmd.extend(["--install-dir", args.install_dir])
        rc = run(runtime_cmd, ROOT)
        if rc != 0:
            errors.append("安装目录 runtime 审计失败（payload drift）")

    # -- 21. Release-only: forward eval --
    if args.release and args.forward:
        _step("skill_forward_eval --self-test")
        rc = run([sys.executable, str(ROOT / "scripts" / "skill_forward_eval.py"), "--self-test"], ROOT)
        if rc != 0:
            errors.append("forward eval 失败")

    # ── 汇总 ──
    print("\n" + "=" * 60)
    if errors:
        print(f"{mode} Gate 失败 ({len(errors)} 项):")
        for e in errors:
            print(f"  - {e}")
        print("=" * 60)
        return 1

    print(f"{mode} Gate 通过。")
    if not args.release:
        print("提示: 使用 --release 跑完整发布门禁（含安装版同步）。")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
