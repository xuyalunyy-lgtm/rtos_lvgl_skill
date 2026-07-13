"""Build a relocatable, C-only MinGW-w64 UCRT64 toolchain payload.

The output contains its own hash manifest and can optionally be emitted as a
ZIP archive that Windows can extract without 7-Zip or zstd.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

PLATFORM = "win-x64"
TARGET = "x86_64-w64-mingw32"
BINARIES = (
    "gcc.exe", "as.exe", "ld.exe", "ar.exe", "ninja.exe",
)
LICENSE_PACKAGES = (
    "gcc", "binutils", "mingw-w64", "mingw-w64-crt", "mingw-w64-headers",
    "winpthreads", "gmp", "mpfr", "mpc", "isl", "zlib", "zstd", "ninja",
)
MSYS2_PACKAGES = (
    "mingw-w64-ucrt-x86_64-binutils",
    "mingw-w64-ucrt-x86_64-crt",
    "mingw-w64-ucrt-x86_64-gcc",
    "mingw-w64-ucrt-x86_64-gcc-libs",
    "mingw-w64-ucrt-x86_64-gettext-runtime",
    "mingw-w64-ucrt-x86_64-gmp",
    "mingw-w64-ucrt-x86_64-headers",
    "mingw-w64-ucrt-x86_64-isl",
    "mingw-w64-ucrt-x86_64-libiconv",
    "mingw-w64-ucrt-x86_64-libwinpthread",
    "mingw-w64-ucrt-x86_64-mpc",
    "mingw-w64-ucrt-x86_64-mpfr",
    "mingw-w64-ucrt-x86_64-ninja",
    "mingw-w64-ucrt-x86_64-tzdata",
    "mingw-w64-ucrt-x86_64-windows-default-manifest",
    "mingw-w64-ucrt-x86_64-winpthreads",
    "mingw-w64-ucrt-x86_64-zlib",
    "mingw-w64-ucrt-x86_64-zstd",
)
GCC_C_FILES = {
    "cc1.exe", "collect2.exe", "crtbegin.o", "crtend.o", "crtfastmath.o",
    "libgcc.a", "libgcc_eh.a", "libgcov.a", "liblto_plugin.dll",
    "liblto_plugin.dll.a", "lto-wrapper.exe",
}
MINGW_C_LIBS = {
    "libadvapi32.a", "libcomdlg32.a", "libgdi32.a", "libimm32.a",
    "libkernel32.a", "libmingw32.a", "libmingwex.a", "libmingwthrd.a",
    "libmoldname.a", "libmsvcrt-os.a", "libmsvcrt.a", "libntdll.a",
    "libole32.a", "liboleaut32.a", "liboldnames.a", "libpthread.a", "libshell32.a",
    "libshlwapi.a", "libsetupapi.a", "libucrt.a", "libucrtbase.a",
    "libuser32.a", "libuuid.a", "libversion.a", "libwinmm.a",
    "libwinpthread.a", "libwinpthread.dll.a", "libwinspool.a", "libws2_32.a",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def gcc_version_dir(prefix: Path) -> Path:
    base = prefix / "lib" / "gcc" / TARGET
    candidates = sorted((item for item in base.iterdir() if item.is_dir()), reverse=True) if base.is_dir() else []
    if not candidates:
        raise FileNotFoundError(f"GCC library directory not found below {base}")
    return candidates[0]


def collect_files(root: Path, flavor: str) -> list[tuple[str, Path]]:
    prefix = root / flavor
    files: dict[str, Path] = {}

    def add(rel: str, source: Path, *, required: bool = False) -> None:
        if source.is_file():
            files[Path(rel).as_posix()] = source
        elif required:
            raise FileNotFoundError(f"required toolchain file missing: {source}")

    for name in BINARIES:
        add(f"bin/{name}", prefix / "bin" / name, required=name in {"gcc.exe", "as.exe", "ld.exe", "ar.exe", "ninja.exe"})
    # The exact dependency DLL names vary between MSYS2 package revisions
    # (for example zlib1.dll and libzstd.dll). Copying the small DLL set from a
    # C-only installation is safer than maintaining a brittle name list.
    for source in (prefix / "bin").glob("*.dll"):
        add(f"bin/{source.name}", source)

    version_dir = gcc_version_dir(prefix)
    version = version_dir.name
    # Keep the C driver support, startup objects and internal C headers.  GCC's
    # plugin SDK and language-specific trees account for a large part of the
    # full package and are not needed to compile LVGL C sources.
    for source in version_dir.iterdir():
        if source.is_file() and source.name in GCC_C_FILES:
            add(f"lib/gcc/{TARGET}/{version}/{source.name}", source)
    for directory_name in ("include", "include-fixed"):
        directory = version_dir / directory_name
        if directory.is_dir():
            for source in directory.rglob("*"):
                if source.is_file():
                    add(f"lib/gcc/{TARGET}/{version}/{source.relative_to(version_dir)}", source)

    # Some GCC distributions use libexec; current MSYS2 keeps cc1 beside the
    # GCC support objects.  The version-root copy above handles the latter.
    libexec = prefix / "libexec" / "gcc" / TARGET / version
    if libexec.is_dir():
        for source in libexec.iterdir():
            if source.is_file():
                add(f"libexec/gcc/{TARGET}/{version}/{source.name}", source)
    if not any(relative.endswith("/cc1.exe") for relative in files):
        raise FileNotFoundError("required GCC C frontend cc1.exe was not found")

    # MSYS2 UCRT64 installs Windows headers and import libraries directly under
    # <prefix>/include and <prefix>/lib; target/lib contains binutils support.
    for subtree in (Path("include"), Path("lib"), Path(TARGET) / "lib"):
        source_root = prefix / subtree
        if not source_root.is_dir():
            raise FileNotFoundError(f"required toolchain directory missing: {source_root}")
        for source in source_root.rglob("*"):
            if source.is_file():
                # The curated GCC version tree was already copied above.
                if subtree == Path("lib") and source.is_relative_to(prefix / "lib" / "gcc"):
                    continue
                if subtree == Path("include"):
                    relative = source.relative_to(source_root)
                    if relative.parts[0] in {"c++", "isl", "libiberty"}:
                        continue
                    if relative.parent == Path(".") and relative.name.startswith(("gmp", "mpc", "mpfr")):
                        continue
                if subtree == Path("lib"):
                    relative = source.relative_to(source_root)
                    if relative.parent == Path("."):
                        is_crt_object = relative.suffix == ".o"
                        if relative.name not in MINGW_C_LIBS and not is_crt_object:
                            continue
                    elif relative.parts[0] not in {"bfd-plugins"}:
                        continue
                add((subtree / source.relative_to(source_root)).as_posix(), source)

    return sorted(files.items())


def copy_licenses(root: Path, flavor: str, output: Path) -> None:
    destination = output / "licenses"
    destination.mkdir(parents=True, exist_ok=True)
    copied = 0
    license_root = root / flavor / "share" / "licenses"
    for package in LICENSE_PACKAGES:
        source_dir = license_root / package
        if not source_dir.is_dir():
            continue
        for source in source_dir.rglob("*"):
            if source.is_file():
                target = destination / package / source.relative_to(source_dir)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
                copied += 1
    if not copied:
        # MSYS2 MinGW packages do not consistently install license texts.  Keep
        # an explicit notice and immutable source locations in every payload;
        # the release workflow may additionally publish corresponding sources.
        (destination / "THIRD_PARTY_NOTICES.txt").write_text(
            "Portable toolchain components and license references\n\n"
            "GCC: GPL-3.0-or-later with GCC Runtime Library Exception\n"
            "https://gcc.gnu.org/onlinedocs/libstdc++/manual/license.html\n\n"
            "GNU binutils: GPL-3.0-or-later\n"
            "https://sourceware.org/git/?p=binutils-gdb.git;a=blob;f=COPYING3\n\n"
            "MinGW-w64: component-specific permissive licenses\n"
            "https://github.com/mingw-w64/mingw-w64/blob/master/COPYING\n\n"
            "Dependency versions and source repository are recorded in sources.json.\n",
            encoding="utf-8",
        )


def write_payload(
    root: Path, flavor: str, output: Path, version: str, revision: int,
    package_lock: Path | None,
) -> Path:
    output.mkdir(parents=True, exist_ok=True)
    hashes: dict[str, str] = {}
    files = collect_files(root, flavor)
    for index, (relative, source) in enumerate(files, start=1):
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        hashes[relative] = sha256_file(target)
        if index % 250 == 0 or index == len(files):
            print(f"[{index}/{len(files)}] {relative}")

    copy_licenses(root, flavor, output)
    for source in sorted((output / "licenses").rglob("*")):
        if source.is_file():
            hashes[source.relative_to(output).as_posix()] = sha256_file(source)

    locked_packages = []
    if package_lock and package_lock.is_file():
        locked_packages = [line.strip() for line in package_lock.read_text(encoding="utf-8").splitlines() if line.strip()]
    elif (root / "usr" / "bin" / "pacman.exe").is_file():
        query = subprocess.run(
            [str(root / "usr" / "bin" / "pacman.exe"), "-Q"],
            capture_output=True, text=True, timeout=30, check=False,
        )
        if query.returncode == 0:
            locked_packages = [line.strip() for line in query.stdout.splitlines() if line.strip()]
    locked_packages = sorted(
        line for line in locked_packages
        if line.split(maxsplit=1)[0] in MSYS2_PACKAGES
    )
    sources = {
        "distribution": "MSYS2",
        "environment": flavor,
        "packages": list(MSYS2_PACKAGES),
        "locked_packages": locked_packages,
        "source_repository": "https://repo.msys2.org/mingw/sources/",
    }
    sources_path = output / "sources.json"
    sources_path.write_text(json.dumps(sources, indent=2) + "\n", encoding="utf-8")
    hashes["sources.json"] = sha256_file(sources_path)

    payload = {
        "schema_version": 1,
        "platform": PLATFORM,
        "version": version,
        "package_revision": revision,
        "flavor": flavor,
        "target": TARGET,
        "total_size_bytes": sum((output / rel).stat().st_size for rel in hashes),
        "files": dict(sorted(hashes.items())),
    }
    manifest = output / "toolchain-manifest.json"
    manifest.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return manifest


def archive_payload(output: Path, archive: Path) -> str:
    archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
        for source in sorted(output.rglob("*")):
            if source.is_file():
                name = (Path(PLATFORM) / source.relative_to(output)).as_posix()
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                bundle.writestr(info, source.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    checksum = sha256_file(archive)
    archive.with_name(archive.name + ".sha256").write_text(f"{checksum} {archive.name}\n", encoding="ascii")
    return checksum


def smoke_test(output: Path) -> None:
    gcc = output / "bin" / "gcc.exe"
    environment = dict(__import__("os").environ)
    environment["PATH"] = str(output / "bin") + __import__("os").pathsep + environment.get("PATH", "")
    with tempfile.TemporaryDirectory(prefix="package_toolchain_") as temporary:
        temp = Path(temporary)
        source = temp / "hello.c"
        executable = temp / "hello.exe"
        source.write_text("int main(void){return 0;}\n", encoding="ascii")
        subprocess.run([str(gcc), str(source), "-o", str(executable)], cwd=temp, env=environment, check=True, timeout=60)
        subprocess.run([str(executable)], cwd=temp, env=environment, check=True, timeout=15)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--msys2-root", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--archive")
    parser.add_argument("--flavor", default="ucrt64")
    parser.add_argument("--gcc-version", default="16.1.0")
    parser.add_argument("--revision", type=int, default=1)
    parser.add_argument("--package-lock")
    parser.add_argument("--skip-smoke-test", action="store_true")
    args = parser.parse_args()

    root = Path(args.msys2_root).resolve()
    output = Path(args.output).resolve()
    if not root.is_dir():
        print(f"MSYS2 root not found: {root}", file=sys.stderr)
        return 2
    if output.exists() and any(output.iterdir()):
        print(f"output must be empty: {output}", file=sys.stderr)
        return 2
    try:
        lock = Path(args.package_lock).resolve() if args.package_lock else None
        manifest = write_payload(root, args.flavor, output, args.gcc_version, args.revision, lock)
        if not args.skip_smoke_test:
            smoke_test(output)
        print(f"payload manifest: {manifest}")
        if args.archive:
            archive = Path(args.archive).resolve()
            checksum = archive_payload(output, archive)
            print(f"archive: {archive}\nsha256: {checksum}")
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"packaging failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
