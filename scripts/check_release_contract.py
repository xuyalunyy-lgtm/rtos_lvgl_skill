#!/usr/bin/env python3
"""Detect stale release/CI references before they become false-green gates."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STALE_REFERENCES = ("mcp/server.py", "mcp/lvgl_", "golden_pages/", "check_lvgl_regression.py", "test_manifest_v2.py", "test_app_codegen.py", "test_app_validator.py", "test_mvp_integration.py", "your-org/freertos-skill")


def main() -> int:
    errors: list[str] = []
    for path in [*(ROOT / ".github" / "workflows").glob("*.yml"), ROOT / "README.md", ROOT / "references" / "tool_api_reference.md"]:
        text = path.read_text(encoding="utf-8")
        for stale in STALE_REFERENCES:
            if stale in text:
                errors.append(f"{path.relative_to(ROOT)} references removed or placeholder target: {stale}")
    quick_gate = (ROOT / "scripts" / "quick_gate.py").read_text(encoding="utf-8")
    for stale in STALE_REFERENCES[0:8]:
        if stale in quick_gate:
            errors.append(f"scripts/quick_gate.py references removed target: {stale}")
    ci = (ROOT / ".github" / "workflows" / "skill-tools.yml").read_text(encoding="utf-8")
    for command in ("python scripts/quick_gate.py --strict", "python mcp/mqtt_server.py --self-test", "python mcp/ota_server.py --self-test", "python mcp/serial_server.py --self-test"):
        if command not in ci:
            errors.append(f".github/workflows/skill-tools.yml misses release command: {command}")
    if errors:
        print("[release-contract] FAILED")
        for error in errors:
            print(f"  - {error}")
        return 1
    print("[release-contract] release and CI references are current")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
