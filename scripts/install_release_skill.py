#!/usr/bin/env python3
"""
安装版 Skill 发布脚本 — 从仓库安装到 Codex skill 目录。

排除 .git、缓存、测试输出、非运行时文件。

用法:
    python scripts/install_release_skill.py
    python scripts/install_release_skill.py --dry-run
    python scripts/install_release_skill.py --self-test
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INSTALL_DIR = Path(os.environ.get("USERPROFILE", "")) / ".codex" / "skills" / "freertos-embedded-architect"

# 安装时排除的目录/文件
EXCLUDE_DIRS = {
    ".git", "__pycache__", ".mypy_cache", ".pytest_cache",
    "node_modules", ".codex", "forward_tests",
    "freertos-skill-lite",  # Lite 是独立分发包
    ".skill_metrics", ".skill_evidence",  # 运行时产物
}

EXCLUDE_FILES = {
    ".gitignore", ".gitattributes",
    "CLAUDE.md", "INSTALL.md",  # 开发文档
}

# 安装时排除的文件模式
EXCLUDE_PATTERNS = [
    "*.pyc", "*.pyo", "__pycache__",
    ".DS_Store", "Thumbs.db",
    "*.log", "*.tmp",
    "test_evidence*", "tmp_*",
]


def _should_exclude(path: Path, rel: str) -> bool:
    """判断文件是否应排除。"""
    parts = path.parts

    # 目录排除
    for part in parts:
        if part in EXCLUDE_DIRS:
            return True

    # 文件名排除
    if path.name in EXCLUDE_FILES:
        return True

    # 模式排除
    for pattern in EXCLUDE_PATTERNS:
        if path.match(pattern):
            return True

    return False


def collect_files(src_dir: Path) -> list[Path]:
    """收集要安装的文件列表。"""
    files = []
    for f in sorted(src_dir.rglob("*")):
        if not f.is_file():
            continue
        rel = str(f.relative_to(src_dir))
        if not _should_exclude(f, rel):
            files.append(f)
    return files


def install(src_dir: Path, dst_dir: Path, dry_run: bool = False) -> dict:
    """安装 skill 到目标目录。"""
    files = collect_files(src_dir)
    installed = 0
    skipped = 0

    if not dry_run:
        dst_dir.mkdir(parents=True, exist_ok=True)

    for f in files:
        rel = f.relative_to(src_dir)
        dst = dst_dir / rel

        if dry_run:
            installed += 1
            continue

        dst.parent.mkdir(parents=True, exist_ok=True)

        # 文本文件需要 patch（类似 sync_lite）
        if f.suffix in (".md", ".txt", ".json", ".yaml", ".yml", ".py", ".sh"):
            try:
                content = f.read_text(encoding="utf-8")
                dst.write_text(content, encoding="utf-8")
                installed += 1
            except Exception:
                skipped += 1
        else:
            try:
                shutil.copy2(f, dst)
                installed += 1
            except Exception:
                skipped += 1

    return {
        "ok": True,
        "src": str(src_dir),
        "dst": str(dst_dir),
        "installed": installed,
        "skipped": skipped,
        "total_files": len(files),
        "dry_run": dry_run,
    }


def run_self_test() -> int:
    passed = 0
    failed = 0

    # 1. collect_files 不包含 .git
    files = collect_files(ROOT)
    git_files = [f for f in files if ".git" in f.parts]
    assert len(git_files) == 0, f"Found {len(git_files)} .git files"
    print(f"[PASS] collect_files: {len(files)} files, no .git")
    passed += 1

    # 2. 不包含 __pycache__
    pyc_files = [f for f in files if "__pycache__" in f.parts]
    assert len(pyc_files) == 0
    print("[PASS] no __pycache__")
    passed += 1

    # 3. 不包含 forward_tests
    ft_files = [f for f in files if "forward_tests" in f.parts]
    assert len(ft_files) == 0
    print("[PASS] no forward_tests")
    passed += 1

    # 4. 包含关键运行时文件
    rel_paths = {f.relative_to(ROOT) for f in files}
    required = [Path("SKILL.md"), Path("references/core_rules.md"), Path("tools/run_review.py")]
    for r in required:
        assert r in rel_paths, f"Missing required: {r}"
    print(f"[PASS] required files present")
    passed += 1

    # 5. dry-run
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        result = install(ROOT, Path(tmp) / "test_skill", dry_run=True)
        assert result["ok"] is True
        assert result["installed"] > 0
        assert result["dry_run"] is True
        print(f"[PASS] dry-run: {result['installed']} files")
        passed += 1

    print(f"\nSelf-test: {passed} passed, {failed} failed")
    return 1 if failed > 0 else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="安装版 Skill 发布")
    parser.add_argument("--src", default=str(ROOT), help="源目录")
    parser.add_argument("--dst", default=str(DEFAULT_INSTALL_DIR), help="目标目录")
    parser.add_argument("--dry-run", action="store_true", help="只列出文件，不安装")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    src = Path(args.src)
    dst = Path(args.dst)

    result = install(src, dst, dry_run=args.dry_run)

    if args.dry_run:
        print(f"[DRY-RUN] 将安装 {result['installed']} 个文件到 {dst}")
    else:
        print(f"[OK] 已安装 {result['installed']} 个文件到 {dst}")
        if result["skipped"] > 0:
            print(f"  跳过 {result['skipped']} 个文件")

    return 0


if __name__ == "__main__":
    sys.exit(main())
