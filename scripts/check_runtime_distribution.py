#!/usr/bin/env python3
"""
Audit the runtime distribution boundary for this skill repo.

Source repos may keep maintenance docs and release artifacts. Installed
Cursor/Claude/Codex packages must keep only runtime files.
"""
from __future__ import annotations

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
LITE = ROOT / "freertos-skill-lite"
sys.path.insert(0, str(SCRIPTS))

try:
    import install_multi_ide
except Exception as exc:  # pragma: no cover - defensive checker path
    print(f"[runtime-dist] failed to import install_multi_ide.py: {exc}")
    sys.exit(1)


ROOT_ONLY_FORBIDDEN = {
    "README.md",
    "INSTALL.md",
    "CHANGELOG.md",
}

FORBIDDEN_RUNTIME_DIRS = {
    ".git",
    ".github",
    ".vscode",
    "__pycache__",
    ".pytest_cache",
    "node_modules",
    "freertos-skill-lite",
    "fw-AC79_AIoT_SDK",
    "bk_idk-release-v2.2.1",
}

REQUIRED_RUNTIME_PATHS = {
    "SKILL.md",
    "agents/openai.yaml",
    "workflows/README.md",
    "references/core_rules.md",
    "references/constraint_index.md",
    "references/skill_structure.md",
    "prompts/lvgl_thread_safety.txt",
    "platforms/esp32.md",
    "tools/checker_registry.py",
    "examples/README.md",
}

LITE_REQUIRED_PATHS = {
    "SKILL.md",
    "agents/openai.yaml",
    "workflows/l2_code_review_lite.md",
    "references/lite_manual_checklist.md",
    "references/constraint_index.md",
    "prompts/lvgl_thread_safety.txt",
    "platforms/esp32.md",
}

LITE_FORBIDDEN_PATHS = {
    "tools",
    "examples",
}

SH_INSTALLERS = (
    SCRIPTS / "install_skill.sh",
    SCRIPTS / "install_claude_code.sh",
)

PS_INSTALLERS = (
    SCRIPTS / "install_skill.ps1",
    SCRIPTS / "install_claude_code.ps1",
)


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def collect_runtime_payload() -> set[str]:
    """Return paths that install_multi_ide.py would copy into a full runtime package."""
    included: set[str] = set()

    def walk(directory: Path) -> None:
        try:
            children = sorted(directory.iterdir(), key=lambda p: p.name)
        except OSError as exc:
            raise RuntimeError(f"cannot read {directory}: {exc}") from exc

        ignored = install_multi_ide.runtime_ignore(
            str(directory),
            [child.name for child in children],
        )
        for child in children:
            if child.name in ignored:
                continue
            included.add(rel(child))
            if child.is_dir():
                walk(child)

    walk(ROOT)
    return included


def path_has_forbidden_dir(path: str) -> bool:
    parts = Path(path).parts
    return any(part in FORBIDDEN_RUNTIME_DIRS for part in parts)


def check_python_runtime_ignore(errors: list[str]) -> None:
    payload = collect_runtime_payload()

    for name in sorted(ROOT_ONLY_FORBIDDEN):
        if name in payload:
            errors.append(f"install_multi_ide runtime payload includes root {name}")

    for path in sorted(payload):
        if path_has_forbidden_dir(path):
            errors.append(f"install_multi_ide runtime payload includes forbidden path {path}")

    for path in sorted(REQUIRED_RUNTIME_PATHS):
        if path not in payload:
            errors.append(f"install_multi_ide runtime payload misses required path {path}")


def check_shell_installers(errors: list[str]) -> None:
    required = (
        ".github",
        ".vscode",
        "freertos-skill-lite",
        "/README.md",
        "/INSTALL.md",
        "/CHANGELOG.md",
    )
    for script in SH_INSTALLERS:
        text = script.read_text(encoding="utf-8")
        for token in required:
            if token not in text:
                errors.append(f"{rel(script)} missing rsync exclude token {token}")


def check_powershell_installers(errors: list[str]) -> None:
    for script in PS_INSTALLERS:
        text = script.read_text(encoding="utf-8")
        for token in (".github", ".vscode", "freertos-skill-lite", "$RootOnlyExcludeFiles"):
            if token not in text:
                errors.append(f"{rel(script)} missing install boundary token {token}")
        for root_file in sorted(ROOT_ONLY_FORBIDDEN):
            if root_file not in text:
                errors.append(f"{rel(script)} missing root-only removal for {root_file}")


def check_lite_shape(errors: list[str]) -> None:
    if not LITE.is_dir():
        # Lite directory is optional — no longer maintained as a separate copy
        return

    for path in sorted(LITE_REQUIRED_PATHS):
        if not (LITE / path).exists():
            errors.append(f"Lite package misses required runtime path {path}")

    for path in sorted(LITE_FORBIDDEN_PATHS):
        if (LITE / path).exists():
            errors.append(f"Lite package must not include {path}/")


def main() -> int:
    errors: list[str] = []
    check_python_runtime_ignore(errors)
    check_shell_installers(errors)
    check_powershell_installers(errors)
    check_lite_shape(errors)

    if errors:
        print("[runtime-dist] distribution boundary check failed:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print("[runtime-dist] distribution boundary OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
