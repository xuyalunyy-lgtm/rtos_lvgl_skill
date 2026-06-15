#!/usr/bin/env python3
"""
同步完整版 → freertos-skill-lite（prompts/、platforms/、workflows/、references/）。

Lite 专档中 ../examples/ 链接会 patch 为「完整版 `examples/...`」。

用法（仓库根目录）:
    python scripts/sync_lite.py
    python scripts/sync_lite.py --dry-run
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LITE = ROOT / "freertos-skill-lite"
SYNC_DIRS = ("prompts", "platforms", "workflows", "references")

# Lite 包内无 examples/，将 markdown 链接改为文字引用
EXAMPLE_LINK_RE = re.compile(r"\[([^\]]+)\]\(\.\./examples/([^)]+)\)")


def patch_lite_examples(content: str) -> str:
    return EXAMPLE_LINK_RE.sub(r"完整版 `examples/\2`", content)


def sync_tree(src_dir: Path, dst_dir: Path, dry_run: bool) -> list[str]:
    actions: list[str] = []
    if not src_dir.is_dir():
        raise FileNotFoundError(f"源目录不存在: {src_dir}")

    dst_dir.mkdir(parents=True, exist_ok=True)

    for src in sorted(src_dir.rglob("*")):
        if not src.is_file():
            continue
        rel = src.relative_to(src_dir)
        dst = dst_dir / rel

        if src.suffix.lower() in (".md", ".txt"):
            text = src.read_text(encoding="utf-8")
            patched = patch_lite_examples(text)
            actions.append(f"PATCH+COPY {rel}")
            if not dry_run:
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_text(patched, encoding="utf-8", newline="\n")
        else:
            actions.append(f"COPY {rel}")
            if not dry_run:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)

    stale = set(p.relative_to(dst_dir) for p in dst_dir.rglob("*") if p.is_file())
    fresh = set(p.relative_to(src_dir) for p in src_dir.rglob("*") if p.is_file())
    for rel in sorted(stale - fresh):
        actions.append(f"DELETE stale {rel}")
        if not dry_run:
            (dst_dir / rel).unlink(missing_ok=True)

    return actions


def main() -> int:
    parser = argparse.ArgumentParser(description="同步完整版 → Lite（prompts/platforms/workflows/references）")
    parser.add_argument("--dry-run", action="store_true", help="仅打印将执行的操作")
    args = parser.parse_args()

    if not LITE.is_dir():
        print(f"错误: Lite 目录不存在: {LITE}", file=sys.stderr)
        return 1

    total = 0
    for name in SYNC_DIRS:
        src = ROOT / name
        dst = LITE / name
        print(f"\n=== {name}/ → freertos-skill-lite/{name}/ ===")
        try:
            actions = sync_tree(src, dst, args.dry_run)
        except FileNotFoundError as e:
            print(f"  跳过: {e}")
            continue
        for line in actions:
            print(f"  {line}")
        total += len(actions)

    mode = "（dry-run）" if args.dry_run else ""
    print(f"\n完成{mode}，共 {total} 项。Lite SKILL.md / INSTALL.md 未改动（需手工维护 Lite 差异）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
