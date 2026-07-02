#!/usr/bin/env python3
"""
Installed Runtime 审计 — 校验安装目录与仓库 payload 一致性。

检查文件清单、必需文件、禁止目录、文件 hash。

用法:
    python scripts/check_installed_runtime.py --strict
    python scripts/check_installed_runtime.py --self-test
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INSTALL_DIR = Path(os.environ.get("USERPROFILE", "")) / ".codex" / "skills" / "freertos-embedded-architect"

# 必需文件（安装后必须存在）
REQUIRED_FILES = [
    "SKILL.md",
    "references/core_rules.md",
    "references/constraint_index.md",
    "references/constraint_detail.md",
    "references/skill_structure.md",
    "references/log_symptom_routes.json",
    "tools/run_review.py",
    "tools/log_triage.py",
    "tools/codegen_gate.py",
    "tools/evidence_schema.py",
]

# 禁止出现在安装目录的路径
FORBIDDEN_PATTERNS = [
    ".git", "__pycache__", ".mypy_cache", ".pytest_cache",
    "node_modules", "forward_tests",
    ".skill_metrics", ".skill_evidence",
    "*.pyc", "*.pyo", "*.tmp", "*.log",
    "test_evidence*", "tmp_*",
]

# 安装时应排除的目录
EXCLUDE_DIRS = {
    ".git", ".github", "__pycache__", ".mypy_cache", ".pytest_cache",
    "node_modules", "forward_tests", "freertos-skill-lite",
    ".skill_metrics", ".skill_evidence", ".codex",
}


def _file_hash(path: Path) -> str:
    """计算文件 SHA256。"""
    h = hashlib.sha256()
    try:
        h.update(path.read_bytes())
    except Exception:
        return "error"
    return h.hexdigest()[:16]


def _should_exclude(path: Path) -> bool:
    for part in path.parts:
        if part in EXCLUDE_DIRS:
            return True
    # 文件名匹配
    if path.name.startswith(".git"):
        return True
    return False


def collect_payload(src_dir: Path) -> dict[str, str]:
    """收集仓库 payload 文件清单和 hash。"""
    payload = {}
    for f in sorted(src_dir.rglob("*")):
        if not f.is_file():
            continue
        if _should_exclude(f):
            continue
        rel = str(f.relative_to(src_dir))
        payload[rel] = _file_hash(f)
    return payload


def check_installed(install_dir: Path, src_dir: Path, strict: bool = False) -> dict:
    """检查安装目录。"""
    result = {
        "install_dir": str(install_dir),
        "install_exists": install_dir.exists(),
        "passed": True,
        "issues": [],
        "file_count": 0,
        "forbidden_found": [],
        "missing_required": [],
        "hash_mismatches": [],
    }

    if not install_dir.exists():
        msg = f"安装目录不存在: {install_dir}"
        if strict:
            result["passed"] = False
            result["issues"].append(msg)
        else:
            result["issues"].append(f"[warning] {msg}")
        return result

    # 收集安装目录文件
    installed_files = set()
    for f in install_dir.rglob("*"):
        if f.is_file():
            rel = str(f.relative_to(install_dir))
            installed_files.add(rel)

    result["file_count"] = len(installed_files)

    # 检查禁止文件
    for f in installed_files:
        fpath = Path(f)
        for part in fpath.parts:
            if part in {".git", "__pycache__", ".mypy_cache", "node_modules", "forward_tests"}:
                result["forbidden_found"].append(f)
                break

    if result["forbidden_found"]:
        result["passed"] = False
        result["issues"].append(f"发现禁止文件: {result['forbidden_found'][:5]}")

    # 检查必需文件
    for rf in REQUIRED_FILES:
        if rf not in installed_files:
            result["missing_required"].append(rf)

    if result["missing_required"]:
        result["passed"] = False
        result["issues"].append(f"缺少必需文件: {result['missing_required'][:5]}")

    # Hash 比较（只比较 REQUIRED_FILES）
    if src_dir.exists():
        for rf in REQUIRED_FILES:
            src_file = src_dir / rf
            dst_file = install_dir / rf
            if src_file.exists() and dst_file.exists():
                src_hash = _file_hash(src_file)
                dst_hash = _file_hash(dst_file)
                if src_hash != dst_hash:
                    result["hash_mismatches"].append({"file": rf, "src": src_hash, "dst": dst_hash})

        if result["hash_mismatches"]:
            result["passed"] = False
            result["issues"].append(f"文件 hash 不一致: {len(result['hash_mismatches'])} 个")

    return result


def generate_manifest(src_dir: Path) -> dict:
    """生成 release manifest。"""
    payload = collect_payload(src_dir)
    version = ""

    skill_md = src_dir / "SKILL.md"
    if skill_md.exists():
        import re
        text = skill_md.read_text(encoding="utf-8")
        m = re.search(r"version:\s*(\S+)", text)
        if m:
            version = m.group(1)

    # 整体 payload hash
    all_hashes = "".join(sorted(payload.values()))
    payload_hash = hashlib.sha256(all_hashes.encode()).hexdigest()[:32]

    return {
        "skill_name": "freertos-embedded-architect",
        "version": version,
        "file_count": len(payload),
        "hash_algorithm": "sha256-16",
        "payload_hash": payload_hash,
        "source_dir": str(src_dir),
        "generated_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
    }


def run_self_test() -> int:
    passed = 0
    failed = 0

    # 1. collect_payload 不包含 .git
    payload = collect_payload(ROOT)
    git_files = [f for f in payload if ".git" in f]
    assert len(git_files) == 0, f"Found {len(git_files)} .git files"
    print(f"[PASS] collect_payload: {len(payload)} files, no .git")
    passed += 1

    # 2. 必需文件存在
    for rf in REQUIRED_FILES:
        assert (ROOT / rf).exists(), f"Missing: {rf}"
    print(f"[PASS] {len(REQUIRED_FILES)} required files exist in repo")
    passed += 1

    # 3. check_installed 不存在目录
    r = check_installed(Path("/nonexistent"), ROOT, strict=False)
    assert r["passed"] is True
    print("[PASS] missing install dir (non-strict) → warning")
    passed += 1

    # 4. check_installed strict
    r = check_installed(Path("/nonexistent"), ROOT, strict=True)
    assert r["passed"] is False
    print("[PASS] missing install dir (strict) → fail")
    passed += 1

    # 5. generate_manifest
    manifest = generate_manifest(ROOT)
    assert manifest["file_count"] > 0
    assert manifest["payload_hash"]
    assert manifest["version"]
    print(f"[PASS] manifest: {manifest['file_count']} files, version={manifest['version']}, hash={manifest['payload_hash'][:16]}...")
    passed += 1

    # 6. check_installed 真实安装目录
    if DEFAULT_INSTALL_DIR.exists():
        r = check_installed(DEFAULT_INSTALL_DIR, ROOT, strict=True)
        print(f"[PASS] installed runtime: {r['file_count']} files, passed={r['passed']}")
        if r["issues"]:
            for i in r["issues"][:3]:
                print(f"  {i}")
        passed += 1
    else:
        print("[SKIP] installed dir not found")
        passed += 1

    print(f"\nSelf-test: {passed} passed, {failed} failed")
    return 1 if failed > 0 else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Installed Runtime 审计")
    parser.add_argument("--install-dir", default=str(DEFAULT_INSTALL_DIR))
    parser.add_argument("--src", default=str(ROOT))
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--manifest", action="store_true", help="输出 release manifest")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    if args.manifest:
        manifest = generate_manifest(Path(args.src))
        if args.json:
            print(json.dumps(manifest, indent=2, ensure_ascii=False))
        else:
            print(f"Skill: {manifest['skill_name']}")
            print(f"Version: {manifest['version']}")
            print(f"Files: {manifest['file_count']}")
            print(f"Hash: {manifest['payload_hash']}")
        return 0

    r = check_installed(Path(args.install_dir), Path(args.src), strict=args.strict)

    if args.json:
        print(json.dumps(r, indent=2, ensure_ascii=False))
    else:
        print(f"Installed: {r['install_exists']}")
        print(f"Files: {r['file_count']}")
        print(f"Passed: {r['passed']}")
        for i in r["issues"]:
            print(f"  - {i}")

    return 0 if r["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
