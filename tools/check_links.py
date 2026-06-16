#!/usr/bin/env python3
"""
Markdown 链接一致性检查器。

扫描所有 .md 文件中的相对链接 [text](path)，验证目标文件存在。

用法:
    python tools/check_links.py                  # 扫描整个 skill 仓库
    python tools/check_links.py --dir prompts/   # 只扫指定目录
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent

# Match markdown links: [text](path) — skip http/https/mailto
LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")
SKIP_SCHEMES = ("http://", "https://", "mailto:", "#", "mailto:")


def scan_file(path: Path) -> list[dict]:
    """Scan a .md file for broken relative links."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    issues: list[dict] = []
    for i, line in enumerate(text.splitlines(), 1):
        for match in LINK_RE.finditer(line):
            target = match.group(2).strip()
            # Skip anchors and external URLs
            if any(target.startswith(s) for s in SKIP_SCHEMES):
                continue
            # Strip anchor part
            target_file = target.split("#")[0]
            if not target_file:
                continue
            # Resolve relative to the file's directory
            resolved = (path.parent / target_file).resolve()
            if not resolved.exists():
                issues.append({
                    "file": str(path.relative_to(SKILL_ROOT)),
                    "line": i,
                    "target": target,
                    "resolved": str(resolved),
                })
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="Markdown 链接一致性检查")
    parser.add_argument("--dir", "-d", help="扫描指定目录（默认全仓库）")
    args = parser.parse_args()

    scan_root = Path(args.dir) if args.dir else SKILL_ROOT
    if not scan_root.is_absolute():
        scan_root = SKILL_ROOT / scan_root

    md_files = sorted(scan_root.rglob("*.md"))
    if not md_files:
        print(f"[check_links] 未找到 .md 文件: {scan_root}")
        return 0

    # Exclude .git, node_modules, and template/generated directories
    EXCLUDE_DIRS = {".git", "node_modules", "scripts", "freertos-skill-lite"}
    md_files = [f for f in md_files if not any(d in EXCLUDE_DIRS for d in f.parts)]

    all_issues: list[dict] = []
    for f in md_files:
        all_issues.extend(scan_file(f))

    if not all_issues:
        print(f"[check_links] 已扫描 {len(md_files)} 个 .md 文件，链接全部有效")
        return 0

    print(f"[check_links] 已扫描 {len(md_files)} 个 .md 文件，发现 {len(all_issues)} 个断链:\n")
    for issue in all_issues:
        print(f"  {issue['file']}:{issue['line']} — [{issue['target']}] → 文件不存在")

    print(f"\nSummary: {len(all_issues)} broken links")
    return 1


if __name__ == "__main__":
    sys.exit(main())