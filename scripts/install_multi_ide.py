#!/usr/bin/env python3
"""
Multi-IDE install script: install skill to any AI IDE with a single command.

Supported: Cursor / Claude Code / Codex / Windsurf / GitHub Copilot / Cline

Usage:
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
    "archive",
    "artifacts",
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


def install_mcp_environment() -> bool:
    """MCP server uses only Python stdlib — no external dependencies to install."""
    print("  MCP environment OK (stdlib only, no external deps)")
    return True

WINDSURF_HEADER = """# FreeRTOS Embedded Architect Rules

Auto-loaded when editing .c/.h files.

## Core Rules
- lv_obj_* forbidden outside View (C1.1)
- cJSON tree must not cross Queue boundary (C2.1/C3.3)
- ISR must use FromISR API only (C4.1)
- Measure first, then modify (C7.1)
- Config files must be independent: direct reuse of original project configs is forbidden

## Full Constraints
-> references/constraint_index.md (C1-C45, audio/video with screen and runtime efficiency prioritized)

## Workflow
-> SKILL.md quick routing table
"""

COPILOT_HEADER = """# FreeRTOS Embedded Architect Instructions

Follow the FreeRTOS IoT firmware constraint system (C1-C45).

## Key Rules
- UI must only be updated in LVGL Task or lv_async_call callback (C1)
- Queue payload: Model alloc -> Presenter free (C2)
- cJSON goto cleanup template (C3)
- ISR must not use blocking API / malloc / printf (C4)
- A/V sync, codec format, jitter buffer, DMA/cache buffer lifecycle (C25-C28)
- Module contract, task topology, timeout budget, observability, lifecycle, hot-path prohibition, critical-path budget, data-copy budget, backpressure degradation, fault recovery, config matrix, one-click repro, regression samples, board-level resource contract, lock budget & priority inversion protection, critical-section/interrupt-off budget, sensor integration contract (C29-C45)
- Config files must be independent: new projects may only reference the format, and must be written strictly per user input

## Platform Docs
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
    import json
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
    # Configure MCP server in Claude Code settings
    claude_dir = Path.home() / ".claude"
    settings_file = claude_dir / "settings.json"
    mcp_config = {
        "command": sys.executable,
        "args": ["mcp/server.py"],
        "cwd": str(dest),
        "env": {"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"},
    }
    try:
        if settings_file.exists():
            settings = json.loads(settings_file.read_text(encoding="utf-8"))
            if "mcpServers" not in settings:
                settings["mcpServers"] = {}
            settings["mcpServers"]["freertos-embedded-architect"] = mcp_config
        else:
            settings = {"mcpServers": {"freertos-embedded-architect": mcp_config}}
        settings_file.write_text(json.dumps(settings, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  MCP -> {settings_file}")
    except Exception as exc:
        print(f"  Warning: MCP config failed: {exc}")
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
    parser.add_argument("--skip-env-install", action="store_true", help="Skip MCP Python dependency installation")
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

    if not args.skip_env_install:
        print("\n[environment]")
        if not install_mcp_environment():
            return 1

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
