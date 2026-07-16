#!/usr/bin/env python3
"""Verify that shipped installers and the runtime exclusion policy agree."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "references"))
from runtime_excludes import (
    RUNTIME_EXCLUDE_DIRS,
    RUNTIME_EXCLUDE_NAME_PATTERNS,
    RUNTIME_EXCLUDE_ROOT_FILES,
)


def main() -> int:
    errors: list[str] = []
    required = {"SKILL.md", "agents/openai.yaml", "tools/run_review.py", "tools/project_doctor.py", "mcp/serial_server.py", "workflows/README.md"}
    for relative in sorted(required):
        if not (ROOT / relative).is_file():
            errors.append(f"missing runtime file: {relative}")
    installers = (ROOT / "scripts" / "install_skill.sh", ROOT / "scripts" / "install_skill.ps1")
    tokens = sorted(RUNTIME_EXCLUDE_DIRS | RUNTIME_EXCLUDE_ROOT_FILES | set(RUNTIME_EXCLUDE_NAME_PATTERNS))
    for installer in installers:
        if not installer.is_file():
            errors.append(f"missing installer: {installer.relative_to(ROOT)}")
            continue
        text = installer.read_text(encoding="utf-8").replace("\\", "/")
        for token in tokens:
            if token not in text:
                errors.append(f"{installer.relative_to(ROOT)} does not exclude {token}")
    if errors:
        print("[runtime-dist] FAILED")
        for error in errors:
            print(f"  - {error}")
        return 1
    print("[runtime-dist] distribution boundary OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
