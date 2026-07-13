"""Package a minimal MinGW-w64 UCRT64 toolchain from MSYS2 installation.

Usage:
    python scripts/package_toolchain.py --msys2-root C:/msys64 --output runtime/toolchain/win-x64

Extracts only the files needed for LVGL C compilation:
- gcc, cc1, as, ld, ar, ninja + required DLLs
- MinGW-w64 headers and CRT
- libgcc and startup objects
- No C++, Fortran, GDB, MSYS shell, or unused static libraries
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# Patterns to include from bin/
BIN_INCLUDES = [
    "gcc.exe",
    "cc1.exe",       # may not exist standalone in newer GCC
    "as.exe",
    "ld.exe",
    "ar.exe",
    "ninja.exe",
    "libgcc_s_seh-1.dll",
    "libwinpthread-1.dll",
    "libstdc++-6.dll",  # needed by some gcc internals
    "libgmp-10.dll",
    "libmpc-3.dll",
    "libmpfr-6.dll",
    "libisl-23.dll",
    "libzstd-1.dll",
    "libz-1.dll",
    "libiconv-2.dll",
]

# Directories to copy entirely
DIR_INCLUDES = [
    "x86_64-w64-mingw32/include",
    "x86_64-w64-mingw32/lib",
]


def find_gcc_lib_dir(msys2_root: Path, flavor: str = "ucrt64") -> Path | None:
    """Find the gcc lib directory containing crtbegin.o etc."""
    gcc_lib_base = msys2_root / flavor / "lib" / "gcc" / "x86_64-w64-mingw32"
    if not gcc_lib_base.exists():
        return None
    versions = sorted(gcc_lib_base.iterdir(), reverse=True)
    return versions[0] if versions else None


def collect_bin_files(msys2_root: Path, flavor: str = "ucrt64") -> list[tuple[str, Path]]:
    """Collect bin/ files to include. Returns [(relative_path, source_path)]."""
    bin_dir = msys2_root / flavor / "bin"
    result = []
    for name in BIN_INCLUDES:
        src = bin_dir / name
        if src.exists():
            result.append((f"bin/{name}", src))

    # Also find cc1.exe if it's inside libexec (GCC 14+)
    libexec_cc1 = msys2_root / flavor / "libexec" / "gcc" / "x86_64-w64-mingw32"
    if libexec_cc1.exists():
        for ver_dir in sorted(libexec_cc1.iterdir(), reverse=True):
            cc1 = ver_dir / "cc1.exe"
            if cc1.exists():
                result.append(("bin/cc1.exe", cc1))
                break

    return result


def collect_dir_files(msys2_root: Path, flavor: str = "ucrt64") -> list[tuple[str, Path]]:
    """Collect directory trees to include."""
    result = []
    for rel_dir in DIR_INCLUDES:
        src = msys2_root / flavor / rel_dir
        if not src.exists():
            print(f"  warning: missing {rel_dir}", file=sys.stderr)
            continue
        for f in src.rglob("*"):
            if f.is_file():
                result.append((f"{rel_dir}/{f.relative_to(src)}", f))
    return result


def collect_gcc_lib_files(msys2_root: Path, flavor: str = "ucrt64") -> list[tuple[str, Path]]:
    """Collect gcc lib/ files (crt objects, libgcc)."""
    gcc_lib = find_gcc_lib_dir(msys2_root, flavor)
    if not gcc_lib:
        print("  warning: gcc lib dir not found", file=sys.stderr)
        return []
    result = []
    for f in gcc_lib.rglob("*"):
        if f.is_file():
            result.append((f"lib/gcc/{f.relative_to(msys2_root / flavor / 'lib' / 'gcc')}", f))
    return result


def copy_and_hash(files: list[tuple[str, Path]], output_dir: Path) -> dict[str, str]:
    """Copy files and return {relative_path: sha256}."""
    hashes: dict[str, str] = {}
    total = len(files)
    for i, (rel, src) in enumerate(files):
        dst = output_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        hashes[rel] = _sha256_file(dst)
        if (i + 1) % 50 == 0 or i + 1 == total:
            print(f"  [{i+1}/{total}] copied {rel}")
    return hashes


def copy_licenses(msys2_root: Path, output_dir: Path) -> None:
    """Copy GCC and MinGW-w64 license files."""
    lic_dir = output_dir / "licenses"
    lic_dir.mkdir(parents=True, exist_ok=True)

    # GCC license
    gcc_lic = msys2_root / "ucrt64" / "share" / "licenses" / "gcc" / "COPYING3"
    if gcc_lic.exists():
        shutil.copy2(gcc_lic, lic_dir / "gcc.LICENSE")
    else:
        (lic_dir / "gcc.LICENSE").write_text(
            "GCC is licensed under GPLv3 with Runtime Library Exception.\n"
            "See https://www.gnu.org/licenses/gcc-exception.html\n",
            encoding="utf-8",
        )

    # MinGW-w64 license
    mingw_lic = msys2_root / "ucrt64" / "share" / "licenses" / "mingw-w64"
    if mingw_lic.exists():
        for f in mingw_lic.iterdir():
            if f.is_file():
                shutil.copy2(f, lic_dir / f"mingw-w64.{f.name}")
    else:
        (lic_dir / "mingw-w64.LICENSE").write_text(
            "MinGW-w64 runtime headers are Public Domain.\n"
            "CRT libraries are under various permissive licenses.\n"
            "See https://github.com/mingw-w64/mingw-w64/blob/master/COPYING\n",
            encoding="utf-8",
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Package minimal MinGW-w64 toolchain")
    parser.add_argument("--msys2-root", required=True, help="MSYS2 installation root")
    parser.add_argument("--output", required=True, help="Output directory")
    parser.add_argument("--flavor", default="ucrt64", help="MSYS2 flavor (default: ucrt64)")
    parser.add_argument("--gcc-version", default="14.2.0", help="GCC version string for manifest")
    args = parser.parse_args()

    msys2 = Path(args.msys2_root).resolve()
    output = Path(args.output).resolve()

    if not msys2.exists():
        print(f"error: MSYS2 root not found: {msys2}", file=sys.stderr)
        return 1

    output.mkdir(parents=True, exist_ok=True)
    print(f"Packaging toolchain from {msys2} to {output}")

    all_files: list[tuple[str, Path]] = []

    print("\n[1/4] Collecting bin/ files...")
    all_files.extend(collect_bin_files(msys2, args.flavor))

    print("[2/4] Collecting include/ and lib/ directories...")
    all_files.extend(collect_dir_files(msys2, args.flavor))

    print("[3/4] Collecting GCC lib/ (crt objects)...")
    all_files.extend(collect_gcc_lib_files(msys2, args.flavor))

    print(f"\nTotal files to copy: {len(all_files)}")
    print("[4/4] Copying and hashing...")
    hashes = copy_and_hash(all_files, output)

    # Copy licenses
    copy_licenses(msys2, output)

    # Calculate total size
    total_size = sum(f.stat().st_size for f in output.rglob("*") if f.is_file())

    # Write manifest fragment
    manifest_fragment = {
        "version": args.gcc_version,
        "flavor": args.flavor,
        "source": f"MSYS2 {args.flavor}-x86_64-toolchain",
        "total_size_bytes": total_size,
        "licenses": ["licenses/gcc.LICENSE", "licenses/mingw-w64.LICENSE"],
        "files": hashes,
    }

    manifest_path = output / "manifest_fragment.json"
    manifest_path.write_text(json.dumps(manifest_fragment, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\nDone! {len(hashes)} files, {total_size / 1024 / 1024:.1f} MB")
    print(f"Manifest fragment: {manifest_path}")
    print(f"\nNext steps:")
    print(f"  1. Copy manifest_fragment.json entries into runtime/toolchain/manifest.json")
    print(f"  2. Run: python scripts/compiler_self_test.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
