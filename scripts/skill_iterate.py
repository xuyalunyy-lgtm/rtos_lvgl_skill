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
SKILL = ROOT / "SKILL.md"
LITE_SKILL = ROOT / "freertos-skill-lite" / "SKILL.md"
CHANGELOG = ROOT / "CHANGELOG.md"
ITERATION_LOG = ROOT / "references" / "iteration_log.md"


def checker_env() -> dict[str, str]:
    env = os.environ.copy()
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Skill 自我迭代验证")
    parser.add_argument("--check", action="store_true", help="运行验证闭环（默认）")
    parser.add_argument("--sync", action="store_true", help="验证通过后执行 sync_lite.py")
    parser.add_argument("--skip-self-test", action="store_true")
    args = parser.parse_args()
    if not args.check and not args.sync:
        args.check = True

    errors: list[str] = []
    print("=" * 60)
    print("Skill 自我迭代验证")
    print("=" * 60)

    if not args.skip_self_test:
        print("\n[1/6] tools/run_review.py --self-test")
        rc = run([sys.executable, str(ROOT / "tools" / "run_review.py"), "--self-test"], ROOT)
        if rc != 0:
            errors.append("run_review --self-test 失败")

    print("\n[2/6] tools/run_review.py --validate-examples")
    rc = run(
        [sys.executable, str(ROOT / "tools" / "run_review.py"), "--validate-examples"],
        ROOT,
    )
    if rc != 0:
        errors.append("run_review --validate-examples 失败（铁律范例约束）")

    print("\n[3/6] SKILL.md version")
    full_ver = read_version(SKILL)
    lite_ver = read_version(LITE_SKILL)
    if not full_ver:
        errors.append("SKILL.md 缺少 metadata.version 字段")
    else:
        print(f"  完整版: {full_ver}")
    if lite_ver:
        print(f"  Lite:   {lite_ver}")
        if full_ver and lite_ver != full_ver:
            errors.append(f"版本不一致: 完整版 {full_ver} vs Lite {lite_ver}（请运行 sync_lite.py）")
    else:
        errors.append("freertos-skill-lite/SKILL.md 缺失或无 version")

    print("\n[4/6] CHANGELOG / iteration_log")
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

    print("\n[5/6] sync_lite --dry-run")
    rc = run([sys.executable, str(ROOT / "scripts" / "sync_lite.py"), "--dry-run"], ROOT)
    if rc != 0:
        errors.append("sync_lite.py --dry-run 失败")

    print("\n[6/6] 可选 sync_lite")
    if args.sync and not errors:
        rc = run([sys.executable, str(ROOT / "scripts" / "sync_lite.py")], ROOT)
        if rc != 0:
            errors.append("sync_lite.py 失败")
        else:
            lite_ver2 = read_version(LITE_SKILL)
            if full_ver and lite_ver2 != full_ver:
                errors.append("sync 后 Lite 版本仍与完整版不一致")
    elif args.sync:
        print("  跳过 sync（存在前置错误）")

    print("\n" + "=" * 60)
    if errors:
        print("迭代验证失败:")
        for e in errors:
            print(f"  - {e}")
        print("=" * 60)
        return 1

    print("迭代验证通过。请确认 iteration_log.md 已记录本次变更。")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
