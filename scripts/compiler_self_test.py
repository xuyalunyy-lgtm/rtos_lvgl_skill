"""Compiler self-test for the bundled MinGW-w64 toolchain.

Verifies:
1. Toolchain manifest and SHA256 integrity
2. GCC --version output
3. Hello World compile + run
4. (Optional) LVGL TestKit compile + link + run

Usage:
    python scripts/compiler_self_test.py
    python scripts/compiler_self_test.py --verbose
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

# Add mcp/ to path
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "mcp"))

from toolchain_resolver import compiler_self_test, ensure_toolchain


def main() -> int:
    parser = argparse.ArgumentParser(description="Compiler self-test")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--toolchain-dir", help="verify an unpacked payload before installation")
    args = parser.parse_args()

    print("=" * 60)
    print("MinGW-w64 Toolchain Self-Test")
    print("=" * 60)

    # Step 1: Resolve toolchain
    print("\n[1/3] Resolving toolchain...")
    tc = ensure_toolchain(toolchain_dir=args.toolchain_dir)
    if not tc["ok"]:
        print(f"  FAIL: {tc['errors']}")
        return 1
    print(f"  Platform:  {tc['platform']}")
    print(f"  Version:   {tc['version']}")
    print(f"  Flavor:    {tc['flavor']}")
    print(f"  GCC:       {tc['gcc']}")
    print(f"  bin_dir:   {tc['bin_dir']}")
    print(f"  Status:    OK")

    # Step 2: GCC version
    print("\n[2/3] GCC version check...")
    try:
        result = subprocess.run(
            [tc["gcc"], "--version"],
            capture_output=True, text=True, timeout=15, env=tc["env"],
        )
        version_line = result.stdout.splitlines()[0] if result.stdout else "unknown"
        print(f"  {version_line}")
        if result.returncode != 0:
            print(f"  FAIL: gcc returned {result.returncode}")
            return 1
        print(f"  Status: OK")
    except Exception as exc:
        print(f"  FAIL: {exc}")
        return 1

    # Step 3: Hello World compile + run
    print("\n[3/3] Hello World compile + run...")
    test_result = compiler_self_test(toolchain_dir=args.toolchain_dir)
    if test_result["ok"]:
        print(f"  Compile: OK")
        print(f"  Run:     OK")
        print(f"  Status:  PASS")
    else:
        print(f"  Compile: {'OK' if test_result['compile_ok'] else 'FAIL'}")
        print(f"  Run:     {'OK' if test_result['run_ok'] else 'FAIL'}")
        for err in test_result["errors"]:
            print(f"  Error:   {err}")
        return 1

    print("\n" + "=" * 60)
    print("All self-tests PASSED")
    print("=" * 60)

    if args.verbose:
        print("\nManifest details:")
        from toolchain_resolver import _load_manifest
        manifest = _load_manifest()
        print(json.dumps(manifest, indent=2, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
