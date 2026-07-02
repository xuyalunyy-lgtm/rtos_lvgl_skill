#!/usr/bin/env python3
"""
安装版同步检查 — 比较 repo skill 与 Codex 安装目录版本一致性。

用法:
    python scripts/check_installed_skill_sync.py
    python scripts/check_installed_skill_sync.py --strict
    python scripts/check_installed_skill_sync.py --self-test
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INSTALL_DIR = Path(os.environ.get("USERPROFILE", "")) / ".codex" / "skills" / "freertos-embedded-architect"


def get_version(path: Path) -> str | None:
    """从 SKILL.md 提取版本号。"""
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    m = re.search(r"^version:\s*(\S+)", text, re.MULTILINE)
    if m:
        return m.group(1)
    m = re.search(r"metadata:\s*\n(?:[ \t]+[^\n]*\n)*?[ \t]+version:\s*(\S+)", text, re.MULTILINE)
    return m.group(1) if m else None


def check_sync(install_dir: Path, strict: bool = False) -> dict:
    """检查安装版与仓库版同步状态。"""
    repo_version = get_version(ROOT / "SKILL.md")
    install_version = get_version(install_dir / "SKILL.md")

    result = {
        "repo_version": repo_version,
        "install_dir": str(install_dir),
        "install_exists": install_dir.exists(),
        "install_version": install_version,
        "passed": True,
        "issues": [],
    }

    if not install_dir.exists():
        msg = f"安装目录不存在: {install_dir}"
        if strict:
            result["passed"] = False
            result["issues"].append(msg)
        else:
            result["issues"].append(f"[warning] {msg}")
        return result

    if not install_version:
        result["passed"] = False
        result["issues"].append(f"安装版 SKILL.md 缺少版本号")
        return result

    if repo_version and install_version != repo_version:
        msg = f"版本不一致: repo={repo_version}, installed={install_version}"
        if strict:
            result["passed"] = False
            result["issues"].append(msg)
        else:
            result["issues"].append(f"[warning] {msg}")

    return result


def run_self_test() -> int:
    passed = 0
    failed = 0

    import tempfile

    # 1. 不存在的安装目录（非 strict）
    r = check_sync(Path("/nonexistent/path"), strict=False)
    assert r["passed"] is True
    assert any("不存在" in i for i in r["issues"])
    print("[PASS] missing install dir (non-strict) → warning")
    passed += 1

    # 2. 不存在的安装目录（strict）
    r = check_sync(Path("/nonexistent/path"), strict=True)
    assert r["passed"] is False
    print("[PASS] missing install dir (strict) → fail")
    passed += 1

    # 3. 版本一致
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        skill_content = "---\nmetadata:\n  version: 1.0.0\n---\n# Test\n"
        (tmp / "SKILL.md").write_text(skill_content, encoding="utf-8")
        r = check_sync(tmp, strict=True)
        # repo version is 21.0.8, install is 1.0.0 → mismatch
        assert r["passed"] is False
        assert any("不一致" in i for i in r["issues"])
        print("[PASS] version mismatch → fail")
        passed += 1

    print(f"\nSelf-test: {passed} passed, {failed} failed")
    return 1 if failed > 0 else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="安装版同步检查")
    parser.add_argument("--install-dir", default=str(DEFAULT_INSTALL_DIR), help="安装目录")
    parser.add_argument("--strict", action="store_true", help="严格模式（未安装也 fail）")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    r = check_sync(Path(args.install_dir), strict=args.strict)

    if args.json:
        import json
        print(json.dumps(r, indent=2, ensure_ascii=False))
    else:
        print(f"Repo:     {r['repo_version']}")
        print(f"Installed: {r['install_version'] or '(未安装)'}")
        print(f"Passed:   {r['passed']}")
        for i in r["issues"]:
            print(f"  - {i}")

    return 0 if r["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
