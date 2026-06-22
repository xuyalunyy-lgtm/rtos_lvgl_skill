#!/usr/bin/env python3
"""
多 IDE 安装脚本：一条命令安装 skill 到任意 AI IDE。

支持: Cursor / Claude Code / Codex / Windsurf / GitHub Copilot / Cline

用法:
    python scripts/install_multi_ide.py --all
    python scripts/install_multi_ide.py --ide cursor --ide windsurf
    python scripts/install_multi_ide.py --list
"""
from __future__ import annotations

import argparse
import fnmatch
import os
import shutil
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
RUNTIME_EXCLUDE_NAMES = {
    ".git",
    ".github",
    ".vscode",
    "__pycache__",
    ".pytest_cache",
    "node_modules",
    "fw-AC79_AIoT_SDK",
    "bk_idk-release-v2.2.1",
    "freertos-skill-lite",
}
RUNTIME_EXCLUDE_FILE_PATTERNS = (
    "*.pyc",
)
ROOT_ONLY_EXCLUDE_FILES = {
    "README.md",
    "INSTALL.md",
    "CHANGELOG.md",
}


def runtime_ignore(directory: str, names: list[str]) -> set[str]:
    """Ignore maintenance assets while preserving nested runtime indexes."""
    ignored = {name for name in names if name in RUNTIME_EXCLUDE_NAMES}
    ignored.update(
        name
        for name in names
        if any(fnmatch.fnmatch(name, pattern) for pattern in RUNTIME_EXCLUDE_FILE_PATTERNS)
    )
    if Path(directory).resolve() == SKILL_ROOT.resolve():
        ignored.update(name for name in names if name in ROOT_ONLY_EXCLUDE_FILES)
    return ignored

WINDSURF_HEADER = """# FreeRTOS Embedded Architect Rules

本规则在编辑 .c/.h 文件时自动加载。

## 核心规则
- 非 View 禁止 lv_obj_*（C1.1）
- cJSON 树不得跨 Queue 传递（C2.1/C3.3）
- ISR 仅 FromISR API（C4.1）
- 先量后改（C7.1）
- 配置文件独立：禁止直接复用原项目配置

## 完整约束
-> references/constraint_index.md（C1-C28，带屏音视频优先）

## Workflow
-> SKILL.md 快速路由表
"""

COPILOT_HEADER = """# FreeRTOS Embedded Architect Instructions

遵循 FreeRTOS IoT 固件约束体系（C1-C28）。

## 关键规则
- UI 仅在 LVGL Task 或 lv_async_call 回调中更新（C1）
- Queue payload：Model alloc -> Presenter free（C2）
- cJSON goto cleanup 模板（C3）
- ISR 禁止阻塞 API / malloc / printf（C4）
- A/V sync、codec 格式、jitter buffer、DMA/cache buffer 生命周期（C25-C28）
- 配置文件独立：新项目只能参考格式，严格按用户输入编写

## 平台专档
-> platforms/esp32.md | stm32.md | jl.md | bk.md
"""


def install_cursor(project_root: str | None = None) -> bool:
    dest = Path.home() / ".cursor" / "skills" / "freertos-embedded-architect"
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(SKILL_ROOT, dest, ignore=runtime_ignore)
    print(f"  Skill -> {dest}")
    if project_root:
        rule_src = SKILL_ROOT / "templates" / "cursor-rule.embedded.mdc"
        rule_dest = Path(project_root) / ".cursor" / "rules" / "freertos-embedded.mdc"
        rule_dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(rule_src, rule_dest)
        print(f"  Rule -> {rule_dest}")
    return True


def install_claude(project_root: str | None = None) -> bool:
    dest = Path.home() / ".claude" / "skills" / "freertos-embedded-architect"
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(SKILL_ROOT, dest, ignore=runtime_ignore)
    print(f"  Skill -> {dest}")
    if project_root:
        template = SKILL_ROOT / "templates" / "CLAUDE.embedded.md"
        if template.exists():
            dest_claude = Path(project_root) / "CLAUDE.md"
            shutil.copy2(template, dest_claude)
            print(f"  CLAUDE.md -> {dest_claude}")
    return True


def install_codex(project_root: str | None = None) -> bool:
    codex_home = os.environ.get("CODEX_HOME")
    root = Path(codex_home) if codex_home else Path.home() / ".codex"
    dest = root / "skills" / "freertos-embedded-architect"
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(SKILL_ROOT, dest, ignore=runtime_ignore)
    print(f"  Skill -> {dest}")
    return True


def install_windsurf(project_root: str | None = None) -> bool:
    if not project_root:
        print("  Error: Windsurf requires --project-root")
        return False
    rules_path = Path(project_root) / ".windsurf" / "rules.md"
    rules_path.parent.mkdir(parents=True, exist_ok=True)
    rules_path.write_text(WINDSURF_HEADER, encoding="utf-8")
    print(f"  Rules -> {rules_path}")
    return True


def install_copilot(project_root: str | None = None) -> bool:
    if not project_root:
        print("  Error: Copilot requires --project-root")
        return False
    instructions_path = Path(project_root) / ".github" / "copilot-instructions.md"
    instructions_path.parent.mkdir(parents=True, exist_ok=True)
    instructions_path.write_text(COPILOT_HEADER, encoding="utf-8")
    print(f"  Instructions -> {instructions_path}")
    return True


def install_cline() -> bool:
    print(f"  Cline uses SKILL.md directly")
    print(f"  Path: {SKILL_ROOT / 'SKILL.md'}")
    return True


INSTALLERS = {
    "cursor": install_cursor,
    "claude": install_claude,
    "codex": install_codex,
    "windsurf": install_windsurf,
    "copilot": install_copilot,
    "cline": install_cline,
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Multi-IDE install script")
    parser.add_argument("--ide", action="append", choices=list(INSTALLERS.keys()),
                       help="Install to specific IDE (repeatable)")
    parser.add_argument("--all", action="store_true", help="Install to all IDEs")
    parser.add_argument("--project-root", help="Project root (for project-level rules)")
    parser.add_argument("--list", action="store_true", help="List supported IDEs")
    args = parser.parse_args()

    if args.list:
        print("Supported IDEs:")
        for ide in INSTALLERS:
            print(f"  {ide}")
        return 0

    ides = list(INSTALLERS.keys()) if args.all else (args.ide or [])
    if not ides:
        parser.print_help()
        return 1

    print("=" * 60)
    print("Multi-IDE Install")
    print("=" * 60)

    success = 0
    for ide in ides:
        print(f"\n[{ide}]")
        kwargs = {}
        if ide in ("cursor", "claude", "codex", "windsurf", "copilot"):
            kwargs["project_root"] = args.project_root
        if INSTALLERS[ide](**kwargs):
            success += 1
            print(f"  OK")
        else:
            print(f"  FAILED")

    print(f"\n{'=' * 60}")
    print(f"Done: {success}/{len(ides)} IDEs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
