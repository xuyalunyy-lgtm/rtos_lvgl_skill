#!/usr/bin/env python3
"""Bump version in SKILL.md and freertos-skill-lite/SKILL.md."""
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
new_ver = sys.argv[1] if len(sys.argv) > 1 else "2.25.0"

for f in [root / "SKILL.md", root / "freertos-skill-lite" / "SKILL.md"]:
    if f.is_file():
        text = f.read_text("utf-8")
        import re
        text = re.sub(r"version:\s*\d+\.\d+\.\d+", f"version: {new_ver}", text, count=1)
        f.write_text(text, "utf-8")
        print(f"Updated {f} -> {new_ver}")