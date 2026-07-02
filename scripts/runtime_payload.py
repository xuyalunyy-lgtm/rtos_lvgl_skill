#!/usr/bin/env python3
"""
Runtime Payload 规则 — 集中维护 include/exclude、required files、forbidden dirs、hash 规则。

install_release_skill.py 和 check_installed_runtime.py 都从这里取规则。

用法:
    python scripts/runtime_payload.py --list
    python scripts/runtime_payload.py --self-test
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ── 安装时排除的目录 ──
EXCLUDE_DIRS = {
    ".git", ".github", "__pycache__", ".mypy_cache", ".pytest_cache",
    "node_modules", "forward_tests", "freertos-skill-lite",
    ".skill_metrics", ".skill_evidence", ".codex",
    "out",  # 测试输出
}

# ── 安装时排除的文件名 ──
EXCLUDE_FILES = {
    ".gitignore", ".gitattributes",
    "CLAUDE.md", "INSTALL.md",
}

# ── 安装时排除的文件模式 ──
EXCLUDE_PATTERNS = [
    "*.pyc", "*.pyo", "__pycache__",
    ".DS_Store", "Thumbs.db",
    "*.log", "*.tmp",
    "test_evidence*", "tmp_*",
    "release_manifest.json",  # 安装产物，不参与 payload hash
]

# ── 安装后禁止出现的路径 ──
FORBIDDEN_PATTERNS = [
    ".git", ".github", "__pycache__", ".mypy_cache", ".pytest_cache",
    "node_modules", "forward_tests",
    ".skill_metrics", ".skill_evidence",
    "*.pyc", "*.pyo", "*.tmp", "*.log",
    "test_evidence*", "tmp_*",
]

# ── 必需文件（安装后必须存在） ──
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
    "tools/manifest_contract.py",
]


def should_exclude(path: Path) -> bool:
    """判断文件是否应排除。"""
    for part in path.parts:
        if part in EXCLUDE_DIRS:
            return True
    if path.name.startswith(".git"):
        return True
    if path.name in EXCLUDE_FILES:
        return True
    for pattern in EXCLUDE_PATTERNS:
        if path.match(pattern):
            return True
    return False


def is_forbidden(rel_path: str) -> bool:
    """判断安装后的路径是否禁止。"""
    p = Path(rel_path)
    for part in p.parts:
        if part in {".git", ".github", "__pycache__", ".mypy_cache", "node_modules",
                    "forward_tests", ".skill_metrics", ".skill_evidence"}:
            return True
    if p.name.startswith(".git"):
        return True
    for pattern in ["*.pyc", "*.pyo", "*.tmp", "*.log"]:
        if p.match(pattern):
            return True
    return False


def file_hash(path: Path) -> str:
    """计算文件完整 SHA256。"""
    h = hashlib.sha256()
    try:
        h.update(path.read_bytes())
    except Exception:
        return "error"
    return h.hexdigest()


def collect_payload(src_dir: Path) -> dict[str, str]:
    """收集仓库 payload 文件清单和 hash。"""
    payload = {}
    for f in sorted(src_dir.rglob("*")):
        if not f.is_file():
            continue
        if should_exclude(f.relative_to(src_dir)):
            continue
        rel = str(f.relative_to(src_dir)).replace("\\", "/")
        payload[rel] = file_hash(f)
    return payload


def payload_hash(payload: dict[str, str]) -> str:
    """计算 payload 整体 hash（基于 relative_path + file_hash）。"""
    h = hashlib.sha256()
    for rel in sorted(payload.keys()):
        h.update(rel.encode())
        h.update(payload[rel].encode())
    return h.hexdigest()


def generate_manifest(src_dir: Path) -> dict:
    """生成 release manifest。"""
    payload = collect_payload(src_dir)
    version = ""

    skill_md = src_dir / "SKILL.md"
    if skill_md.exists():
        text = skill_md.read_text(encoding="utf-8")
        m = re.search(r"version:\s*(\S+)", text)
        if m:
            version = m.group(1)

    return {
        "skill_name": "freertos-embedded-architect",
        "version": version,
        "file_count": len(payload),
        "hash_algorithm": "sha256",
        "payload_hash": payload_hash(payload),
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
    print(f"[PASS] {len(REQUIRED_FILES)} required files exist")
    passed += 1

    # 3. should_exclude 正确排除
    assert should_exclude(Path(".git/config"))
    assert should_exclude(Path("__pycache__/x.pyc"))
    assert should_exclude(Path("forward_tests/out/test.json"))
    assert not should_exclude(Path("tools/run_review.py"))
    print("[PASS] should_exclude logic")
    passed += 1

    # 4. is_forbidden 正确检测
    assert is_forbidden(".git/config")
    assert is_forbidden("forward_tests/out/test.json")
    assert not is_forbidden("tools/run_review.py")
    print("[PASS] is_forbidden logic")
    passed += 1

    # 5. payload_hash 稳定性
    p1 = {"a.py": "hash1", "b.py": "hash2"}
    p2 = {"b.py": "hash2", "a.py": "hash1"}
    assert payload_hash(p1) == payload_hash(p2)
    print("[PASS] payload_hash stable")
    passed += 1

    # 6. generate_manifest
    manifest = generate_manifest(ROOT)
    assert manifest["file_count"] > 0
    assert manifest["payload_hash"]
    assert manifest["version"]
    print(f"[PASS] manifest: {manifest['file_count']} files, version={manifest['version']}")
    passed += 1

    print(f"\nSelf-test: {passed} passed, {failed} failed")
    return 1 if failed > 0 else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Runtime Payload 规则")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--manifest", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    if args.list:
        payload = collect_payload(ROOT)
        for f in sorted(payload.keys()):
            print(f"  {f}")
        print(f"\nTotal: {len(payload)} files")
        return 0

    if args.manifest:
        manifest = generate_manifest(ROOT)
        if args.json:
            print(json.dumps(manifest, indent=2, ensure_ascii=False))
        else:
            for k, v in manifest.items():
                print(f"  {k}: {v}")
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
