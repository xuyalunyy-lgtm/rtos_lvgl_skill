#!/usr/bin/env python3
"""
Installed Runtime audit — full payload drift check.

Compare repo payload against install directory: missing, extra, hash mismatch, forbidden path.

Usage:
    python scripts/check_installed_runtime.py --strict
    python scripts/check_installed_runtime.py --self-test
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from runtime_payload import (
    REQUIRED_FILES,
    collect_payload,
    file_hash,
    is_forbidden,
    payload_hash,
)

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INSTALL_DIR = Path(os.environ.get("USERPROFILE", "")) / ".codex" / "skills" / "freertos-embedded-architect"


def check_installed(install_dir: Path, src_dir: Path, strict: bool = False) -> dict:
    """Check install directory against repo payload consistency."""
    result = {
        "install_dir": str(install_dir),
        "install_exists": install_dir.exists(),
        "passed": True,
        "issues": [],
        "file_count": 0,
        "src_file_count": 0,
        "missing": [],
        "extra": [],
        "hash_mismatches": [],
        "forbidden_found": [],
    }

    if not install_dir.exists():
        msg = f"Install directory does not exist: {install_dir}"
        if strict:
            result["passed"] = False
            result["issues"].append(msg)
        else:
            result["issues"].append(f"[warning] {msg}")
        return result

    # Collect payload from both sides
    src_payload = collect_payload(src_dir)
    result["src_file_count"] = len(src_payload)

    installed_files = set()
    installed_hashes = {}
    for f in install_dir.rglob("*"):
        if f.is_file():
            rel = str(f.relative_to(install_dir)).replace("\\", "/")
            if rel == "release_manifest.json":
                continue  # manifest is excluded from payload comparison
            installed_files.add(rel)
            installed_hashes[rel] = file_hash(f)

    result["file_count"] = len(installed_files)

    # Check forbidden files
    for f in installed_files:
        if is_forbidden(f):
            result["forbidden_found"].append(f)

    if result["forbidden_found"]:
        result["passed"] = False
        result["issues"].append(f"Forbidden files found: {sorted(result['forbidden_found'])[:5]}")

    # Check required files
    for rf in REQUIRED_FILES:
        if rf not in installed_files:
            result["missing"].append(rf)

    if result["missing"]:
        result["passed"] = False
        result["issues"].append(f"Missing required files: {result['missing'][:5]}")

    # Full payload comparison: missing + extra + hash mismatch
    src_files = set(src_payload.keys())

    missing = src_files - installed_files
    extra = installed_files - src_files

    for m in sorted(missing):
        if m not in result["missing"]:
            result["missing"].append(m)
    for e in sorted(extra):
        result["extra"].append(e)

    if missing:
        result["passed"] = False
        result["issues"].append(f"Missing files: {len(missing)}")
    if extra:
        result["passed"] = False
        result["issues"].append(f"Extra files: {len(extra)}")

    # Hash comparison (all files, not just REQUIRED_FILES)
    for rel in sorted(src_files & installed_files):
        src_hash = src_payload[rel]
        dst_hash = installed_hashes.get(rel, "")
        if src_hash != dst_hash:
            result["hash_mismatches"].append({"file": rel, "src": src_hash[:16], "dst": dst_hash[:16]})

    if result["hash_mismatches"]:
        result["passed"] = False
        result["issues"].append(f"Hash mismatches: {len(result['hash_mismatches'])}")

    # Manifest comparison
    manifest_path = install_dir / "release_manifest.json"
    if manifest_path.exists():
        try:
            installed_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            src_manifest_payload_hash = payload_hash(src_payload)
            if installed_manifest.get("payload_hash") != src_manifest_payload_hash:
                result["passed"] = False
                result["issues"].append("manifest payload_hash mismatch")
        except Exception:
            pass

    return result


def run_self_test() -> int:
    passed = 0
    failed = 0

    # 1. Clean install → PASS
    with tempfile.TemporaryDirectory() as tmp:
        from install_release_skill import install
        dst = Path(tmp) / "clean"
        install(ROOT, dst, clean=True)
        r = check_installed(dst, ROOT, strict=True)
        if r["passed"]:
            print(f"[PASS] clean install → PASS ({r['file_count']} files)")
            passed += 1
        else:
            print(f"[FAIL] clean install → {r['issues']}")
            failed += 1

    # 2. Missing file → FAIL
    with tempfile.TemporaryDirectory() as tmp:
        from install_release_skill import install
        dst = Path(tmp) / "missing"
        install(ROOT, dst, clean=True)
        # Delete one file
        (dst / "SKILL.md").unlink(missing_ok=True)
        r = check_installed(dst, ROOT, strict=True)
        if not r["passed"] and r["missing"]:
            print(f"[PASS] missing file → FAIL ({r['missing'][:2]})")
            passed += 1
        else:
            print(f"[FAIL] missing file not detected")
            failed += 1

    # 3. Extra stale files → FAIL
    with tempfile.TemporaryDirectory() as tmp:
        from install_release_skill import install
        dst = Path(tmp) / "extra"
        install(ROOT, dst, clean=True)
        (dst / "old_stale.txt").write_text("stale")
        (dst / "__pycache__").mkdir()
        (dst / "__pycache__" / "x.pyc").write_text("pyc")
        r = check_installed(dst, ROOT, strict=True)
        if not r["passed"] and (r["extra"] or r["forbidden_found"]):
            print(f"[PASS] extra/forbidden → FAIL (extra={len(r['extra'])}, forbidden={len(r['forbidden_found'])})")
            passed += 1
        else:
            print(f"[FAIL] extra/forbidden not detected")
            failed += 1

    # 4. Hash change → FAIL
    with tempfile.TemporaryDirectory() as tmp:
        from install_release_skill import install
        dst = Path(tmp) / "hash"
        install(ROOT, dst, clean=True)
        # Modify one file
        skill_md = dst / "SKILL.md"
        if skill_md.exists():
            skill_md.write_text("MODIFIED", encoding="utf-8")
        r = check_installed(dst, ROOT, strict=True)
        if not r["passed"] and r["hash_mismatches"]:
            print(f"[PASS] hash mismatch → FAIL ({len(r['hash_mismatches'])} mismatches)")
            passed += 1
        else:
            print(f"[FAIL] hash mismatch not detected")
            failed += 1

    # 5. Non-existent directory (strict) → FAIL
    r = check_installed(Path("/nonexistent"), ROOT, strict=True)
    if not r["passed"]:
        print("[PASS] missing dir (strict) → FAIL")
        passed += 1
    else:
        print("[FAIL] missing dir should fail")
        failed += 1

    # 6. Non-existent directory (non-strict) → warning
    r = check_installed(Path("/nonexistent"), ROOT, strict=False)
    if r["passed"]:
        print("[PASS] missing dir (non-strict) → warning")
        passed += 1
    else:
        print("[FAIL] missing dir non-strict should pass")
        failed += 1

    print(f"\nSelf-test: {passed} passed, {failed} failed")
    return 1 if failed > 0 else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Installed Runtime audit")
    parser.add_argument("--install-dir", default=str(DEFAULT_INSTALL_DIR))
    parser.add_argument("--src", default=str(ROOT))
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    r = check_installed(Path(args.install_dir), Path(args.src), strict=args.strict)

    if args.json:
        print(json.dumps(r, indent=2, ensure_ascii=False))
    else:
        print(f"Installed: {r['install_exists']}")
        print(f"Files: {r['file_count']} (src: {r['src_file_count']})")
        print(f"Passed: {r['passed']}")
        for i in r["issues"]:
            print(f"  - {i}")

    return 0 if r["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
