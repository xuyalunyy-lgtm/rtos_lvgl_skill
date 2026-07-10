#!/usr/bin/env python3
"""
安装版 Skill 发布脚本 — clean install。

默认先复制到临时目录，生成 manifest，验证通过后替换目标目录。
旧安装目录中的过期文件会被清除。

用法:
    python scripts/install_release_skill.py
    python scripts/install_release_skill.py --dry-run
    python scripts/install_release_skill.py --no-clean
    python scripts/install_release_skill.py --self-test
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from runtime_payload import (
    EXCLUDE_DIRS,
    collect_payload,
    generate_manifest,
    payload_hash,
    should_exclude,
)

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INSTALL_DIR = Path(os.environ.get("USERPROFILE", "")) / ".codex" / "skills" / "freertos-embedded-architect"


def _install_environment(src_dir: Path, *, dry_run: bool = False, install_env: bool = True) -> dict:
    """MCP server uses only Python stdlib — no external dependencies to install."""
    return {"ok": True, "skipped": True, "reason": "stdlib only"}


def _copy_payload(src_dir: Path, dst_dir: Path) -> int:
    """复制 payload 到目标目录。返回复制文件数。"""
    payload = collect_payload(src_dir)
    dst_dir.mkdir(parents=True, exist_ok=True)

    copied = 0
    for rel in sorted(payload.keys()):
        src_file = src_dir / rel
        dst_file = dst_dir / rel
        dst_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(src_file, dst_file)
            copied += 1
        except Exception:
            pass
    return copied


def _clean_install_dir(install_dir: Path) -> int:
    """清理安装目录。返回删除文件数。"""
    if not install_dir.exists():
        return 0

    removed = 0
    for f in sorted(install_dir.rglob("*"), reverse=True):
        if f.is_file():
            try:
                f.unlink()
                removed += 1
            except Exception:
                pass
        elif f.is_dir():
            try:
                f.rmdir()
            except Exception:
                pass
    return removed


def install(src_dir: Path, dst_dir: Path, dry_run: bool = False, clean: bool = True, install_env: bool = True) -> dict:
    """安装 skill 到目标目录。"""
    payload = collect_payload(src_dir)
    environment = _install_environment(src_dir, dry_run=dry_run, install_env=install_env)
    if not environment.get("ok", False):
        return {
            "ok": False,
            "src": str(src_dir),
            "dst": str(dst_dir),
            "dry_run": dry_run,
            "clean": clean,
            "environment": environment,
            "error": environment.get("error", "MCP environment install failed"),
        }

    manifest = generate_manifest(src_dir)

    if dry_run:
        return {
            "ok": True,
            "src": str(src_dir),
            "dst": str(dst_dir),
            "file_count": len(payload),
            "manifest": manifest,
            "dry_run": True,
            "clean": clean,
            "environment": environment,
        }

    # Clean install: 先复制到临时目录，验证后替换
    if clean:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp) / "skill"

            # 1. 复制到临时目录
            copied = _copy_payload(src_dir, tmp_dir)

            # 2. 写入 manifest
            manifest_path = tmp_dir / "release_manifest.json"
            manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

            # 3. 验证临时目录
            tmp_payload = collect_payload(tmp_dir)
            if len(tmp_payload) != len(payload):
                return {
                    "ok": False,
                    "error": f"payload 验证失败: {len(tmp_payload)} != {len(payload)}",
                    "dry_run": False,
                }

            # 4. 清理旧安装
            removed = _clean_install_dir(dst_dir)

            # 5. 移动到目标
            dst_dir.mkdir(parents=True, exist_ok=True)
            for f in tmp_dir.rglob("*"):
                if f.is_file():
                    rel = f.relative_to(tmp_dir)
                    dst = dst_dir / rel
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(f, dst)

            return {
                "ok": True,
                "src": str(src_dir),
                "dst": str(dst_dir),
                "file_count": len(payload),
                "files_copied": copied,
                "files_removed": removed,
                "manifest": manifest,
                "dry_run": False,
                "clean": True,
                "environment": environment,
            }
    else:
        # No-clean: 直接复制（调试用）
        copied = _copy_payload(src_dir, dst_dir)
        manifest_path = dst_dir / "release_manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

        return {
            "ok": True,
            "src": str(src_dir),
            "dst": str(dst_dir),
            "file_count": len(payload),
            "files_copied": copied,
            "manifest": manifest,
            "dry_run": False,
            "clean": False,
            "environment": environment,
        }


def run_self_test() -> int:
    import tempfile

    passed = 0
    failed = 0

    # 1. dry-run
    with tempfile.TemporaryDirectory() as tmp:
        r = install(ROOT, Path(tmp) / "test", dry_run=True)
        assert r["ok"] is True
        assert r["file_count"] > 0
        assert r["dry_run"] is True
        print(f"[PASS] dry-run: {r['file_count']} files")
        passed += 1

    # 2. clean install
    with tempfile.TemporaryDirectory() as tmp:
        dst = Path(tmp) / "skill"
        # 预放旧文件
        dst.mkdir()
        (dst / "old_file.txt").write_text("old")
        (dst / "forward_tests").mkdir()
        (dst / "forward_tests" / "stale.json").write_text("{}")

        r = install(ROOT, dst, clean=True)
        assert r["ok"] is True
        assert r["clean"] is True
        assert r["files_removed"] >= 2  # old_file.txt + forward_tests/stale.json
        assert not (dst / "old_file.txt").exists()
        assert not (dst / "forward_tests").exists()
        print(f"[PASS] clean install: {r['file_count']} files, {r['files_removed']} removed")
        passed += 1

    # 3. manifest 写入
    with tempfile.TemporaryDirectory() as tmp:
        dst = Path(tmp) / "skill"
        r = install(ROOT, dst, clean=True)
        manifest_path = dst / "release_manifest.json"
        assert manifest_path.exists()
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest["version"]
        assert manifest["payload_hash"]
        print(f"[PASS] manifest written: version={manifest['version']}")
        passed += 1

    # 4. no-clean 模式
    with tempfile.TemporaryDirectory() as tmp:
        dst = Path(tmp) / "skill"
        dst.mkdir()
        (dst / "keep.txt").write_text("keep")
        r = install(ROOT, dst, clean=False)
        assert r["ok"] is True
        assert r["clean"] is False
        assert (dst / "keep.txt").exists()
        print(f"[PASS] no-clean: old files preserved")
        passed += 1

    print(f"\nSelf-test: {passed} passed, {failed} failed")
    return 1 if failed > 0 else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="安装版 Skill 发布 (clean install)")
    parser.add_argument("--src", default=str(ROOT))
    parser.add_argument("--dst", default=str(DEFAULT_INSTALL_DIR))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-clean", action="store_true", help="不清理旧文件（调试用）")
    parser.add_argument("--skip-env-install", action="store_true", help="skip MCP Python dependency installation")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    src = Path(args.src)
    dst = Path(args.dst)
    clean = not args.no_clean

    r = install(src, dst, dry_run=args.dry_run, clean=clean, install_env=not args.skip_env_install)

    if not r["ok"]:
        print(f"[ERROR] {r.get('error', 'install failed')}")
        env = r.get("environment") or {}
        if env.get("stderr"):
            print(env["stderr"].strip()[-2000:])
        return 1

    if args.dry_run:
        print(f"[DRY-RUN] 将安装 {r['file_count']} 个文件到 {dst}")
    else:
        print(f"[OK] 已安装 {r['file_count']} 个文件到 {dst}")
        if r.get("files_removed"):
            print(f"  清理旧文件: {r['files_removed']} 个")
        print(f"  Manifest: version={r['manifest']['version']}, hash={r['manifest']['payload_hash'][:16]}...")

    return 0 if r["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
