"""Resolve and verify the private portable C toolchain used by the MCP.

The resolver is deliberately lazy: importing this module never scans or starts
the compiler.  The relatively expensive hash verification only happens when a
native build asks for the toolchain, and the result is cached for the process.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform as _platform
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
import zipfile
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
_TOOLCHAIN_ROOT = _ROOT / "runtime" / "toolchain"
_DISTRIBUTION_MANIFEST = _TOOLCHAIN_ROOT / "manifest.json"
_PAYLOAD_MANIFEST = "toolchain-manifest.json"


def detect_platform() -> str:
    machine = _platform.machine().lower()
    if sys.platform == "win32" and machine in ("x86_64", "amd64"):
        return "win-x64"
    if sys.platform == "linux" and machine in ("x86_64", "amd64"):
        return "linux-x64"
    if sys.platform == "linux" and machine in ("aarch64", "arm64"):
        return "linux-arm64"
    if sys.platform == "darwin":
        return "macos-arm64" if machine == "arm64" else "macos-x64"
    return f"unknown-{sys.platform}-{machine}"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _load_manifest() -> dict[str, Any]:
    """Compatibility helper used by diagnostics and existing tests."""
    return _load_json(_DISTRIBUTION_MANIFEST)


def _verify_files(toolchain_dir: Path, expected: dict[str, str]) -> list[str]:
    errors: list[str] = []
    if not expected:
        return ["payload manifest contains no files"]
    root = toolchain_dir.resolve()
    for rel_path, expected_hash in sorted(expected.items()):
        rel = Path(rel_path)
        if rel.is_absolute() or ".." in rel.parts:
            errors.append(f"unsafe manifest path: {rel_path}")
            continue
        full = (root / rel).resolve()
        try:
            full.relative_to(root)
        except ValueError:
            errors.append(f"unsafe manifest path: {rel_path}")
            continue
        if not full.is_file():
            errors.append(f"missing: {rel_path}")
        elif _sha256_file(full).lower() != str(expected_hash).lower():
            errors.append(f"hash mismatch: {rel_path}")
    return errors


def _result(platform: str, errors: list[str], **values: Any) -> dict[str, Any]:
    result = {
        "ok": not errors,
        "platform": platform,
        "toolchain_dir": None,
        "bin_dir": None,
        "gcc": None,
        "ar": None,
        "as_exe": None,
        "ld": None,
        "ninja": None,
        "env": None,
        "version": None,
        "flavor": None,
        "errors": errors,
    }
    result.update(values)
    return result


@lru_cache(maxsize=8)
def _resolve_cached(platform: str, directory_text: str) -> dict[str, Any]:
    toolchain_dir = Path(directory_text).resolve()
    distribution = _load_manifest()
    entry = distribution.get("platforms", {}).get(platform)
    if not isinstance(entry, dict):
        return _result(platform, [f"no toolchain manifest for platform '{platform}'"])
    if not toolchain_dir.is_dir():
        return _result(
            platform,
            [f"toolchain directory not found: {toolchain_dir}"],
            version=entry.get("version"),
            flavor=entry.get("flavor"),
        )

    payload_path = toolchain_dir / str(entry.get("payload_manifest", _PAYLOAD_MANIFEST))
    payload = _load_json(payload_path)
    errors: list[str] = []
    if payload.get("schema_version") != 1:
        errors.append(f"invalid or missing payload manifest: {payload_path}")
    if payload.get("platform") != platform:
        errors.append(f"payload platform mismatch: expected {platform!r}")
    if str(payload.get("version")) != str(entry.get("version")):
        errors.append("payload version does not match distribution manifest")

    expected = payload.get("files")
    if not isinstance(expected, dict):
        expected = {}
    errors.extend(_verify_files(toolchain_dir, expected))

    required = entry.get("required_files", [])
    for rel_path in required if isinstance(required, list) else []:
        if not (toolchain_dir / str(rel_path)).is_file():
            errors.append(f"required tool missing: {rel_path}")
    cc1_matches = list((toolchain_dir / "lib" / "gcc").glob("**/cc1.exe"))
    cc1_matches.extend((toolchain_dir / "libexec" / "gcc").glob("**/cc1.exe"))
    if platform == "win-x64" and not cc1_matches:
        errors.append("required compiler frontend missing: lib/gcc/**/cc1.exe")
    if errors:
        return _result(
            platform,
            sorted(set(errors)),
            toolchain_dir=str(toolchain_dir),
            version=entry.get("version"),
            flavor=entry.get("flavor"),
        )

    suffix = ".exe" if platform.startswith("win-") else ""
    bin_dir = toolchain_dir / "bin"
    env = dict(os.environ)
    env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")
    return _result(
        platform,
        [],
        toolchain_dir=str(toolchain_dir),
        bin_dir=str(bin_dir),
        gcc=str(bin_dir / f"gcc{suffix}"),
        ar=str(bin_dir / f"ar{suffix}"),
        as_exe=str(bin_dir / f"as{suffix}"),
        ld=str(bin_dir / f"ld{suffix}"),
        ninja=str(bin_dir / f"ninja{suffix}"),
        env=env,
        version=entry.get("version"),
        flavor=entry.get("flavor"),
    )


def resolve_toolchain(
    platform: str | None = None,
    toolchain_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Resolve a verified toolchain without changing the global environment."""
    selected = platform or detect_platform()
    directory = Path(toolchain_dir) if toolchain_dir else _TOOLCHAIN_ROOT / selected
    return _resolve_cached(selected, str(directory.resolve()))


def clear_toolchain_cache() -> None:
    _resolve_cached.cache_clear()


def _bundled_archive(platform: str) -> tuple[Path | None, str | None, list[str]]:
    entry = _load_manifest().get("platforms", {}).get(platform)
    if not isinstance(entry, dict):
        return None, None, [f"no toolchain manifest for platform '{platform}'"]
    relative = entry.get("bundled_archive")
    expected_hash = entry.get("archive_sha256")
    if not relative or not expected_hash:
        return None, None, [f"no bundled toolchain archive for platform '{platform}'"]
    archive = (_ROOT / str(relative)).resolve()
    try:
        archive.relative_to(_ROOT.resolve())
    except ValueError:
        return None, None, ["bundled archive path escapes the skill root"]
    if not archive.is_file():
        return None, None, [f"bundled toolchain archive missing: {archive}"]
    if _sha256_file(archive).lower() != str(expected_hash).lower():
        return None, None, [f"bundled toolchain archive hash mismatch: {archive.name}"]
    return archive, str(expected_hash).lower(), []


@contextmanager
def _exclusive_install_lock(lock_path: Path, timeout_seconds: float = 60.0):
    deadline = time.monotonic() + timeout_seconds
    descriptor: int | None = None
    while descriptor is None:
        try:
            descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(descriptor, str(os.getpid()).encode("ascii"))
        except FileExistsError:
            try:
                stale = time.time() - lock_path.stat().st_mtime > 300
                if stale:
                    lock_path.unlink()
                    continue
            except FileNotFoundError:
                continue
            if time.monotonic() >= deadline:
                raise TimeoutError(f"timed out waiting for toolchain install lock: {lock_path}")
            time.sleep(0.1)
    try:
        yield
    finally:
        if descriptor is not None:
            os.close(descriptor)
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass


def _extract_bundled_archive(archive: Path, platform: str, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{platform}-staging-", dir=target.parent))
    backup = target.parent / f".{platform}-previous-{uuid.uuid4().hex}"
    try:
        with zipfile.ZipFile(archive) as bundle:
            for info in bundle.infolist():
                relative = Path(info.filename.replace("\\", "/"))
                if relative.is_absolute() or ".." in relative.parts:
                    raise ValueError(f"unsafe toolchain archive member: {info.filename}")
                if not relative.parts or relative.parts[0] != platform:
                    raise ValueError(f"unexpected toolchain archive root: {info.filename}")
                file_type = (info.external_attr >> 16) & 0o170000
                if file_type == 0o120000:
                    raise ValueError(f"toolchain archive contains a symlink: {info.filename}")
            bundle.extractall(staging)

        candidate = staging / platform
        clear_toolchain_cache()
        verified = resolve_toolchain(platform, candidate)
        if not verified["ok"]:
            raise ValueError("extracted toolchain failed verification: " + "; ".join(verified["errors"][:5]))

        if target.exists():
            target.replace(backup)
        try:
            candidate.replace(target)
        except Exception:
            if backup.exists() and not target.exists():
                backup.replace(target)
            raise
        if backup.exists():
            shutil.rmtree(backup)
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def ensure_toolchain(
    platform: str | None = None,
    toolchain_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Resolve the toolchain, installing the bundled ZIP locally if needed."""
    selected = platform or detect_platform()
    current = resolve_toolchain(selected, toolchain_dir)
    if current["ok"] or toolchain_dir is not None:
        return current
    archive, _archive_hash, archive_errors = _bundled_archive(selected)
    if archive is None:
        return _result(
            selected,
            sorted(set(current["errors"] + archive_errors)),
            version=current.get("version"),
            flavor=current.get("flavor"),
        )
    target = _TOOLCHAIN_ROOT / selected
    lock_path = _TOOLCHAIN_ROOT / f".{selected}.install.lock"
    try:
        with _exclusive_install_lock(lock_path):
            clear_toolchain_cache()
            concurrent = resolve_toolchain(selected)
            if not concurrent["ok"]:
                _extract_bundled_archive(archive, selected, target)
        clear_toolchain_cache()
        return resolve_toolchain(selected)
    except (OSError, TimeoutError, ValueError, zipfile.BadZipFile) as exc:
        clear_toolchain_cache()
        return _result(
            selected,
            [f"bundled toolchain install failed: {exc}"],
            version=current.get("version"),
            flavor=current.get("flavor"),
        )


def toolchain_available(platform: str | None = None) -> bool:
    return bool(resolve_toolchain(platform)["ok"])


def compiler_self_test(
    platform: str | None = None,
    toolchain_dir: str | Path | None = None,
) -> dict[str, Any]:
    tc = ensure_toolchain(platform, toolchain_dir)
    if not tc["ok"]:
        return {"ok": False, "gcc_version": None, "compile_ok": False, "run_ok": False, "errors": tc["errors"]}

    try:
        version_run = subprocess.run(
            [tc["gcc"], "--version"], capture_output=True, text=True,
            timeout=15, env=tc["env"], check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {"ok": False, "gcc_version": None, "compile_ok": False, "run_ok": False, "errors": [str(exc)]}
    version = version_run.stdout.splitlines()[0] if version_run.stdout else "unknown"
    if version_run.returncode != 0:
        return {"ok": False, "gcc_version": version, "compile_ok": False, "run_ok": False, "errors": [version_run.stderr[:500]]}

    with tempfile.TemporaryDirectory(prefix="lvgl_ui_toolchain_") as temporary:
        temp = Path(temporary)
        source = temp / "hello.c"
        executable = temp / ("hello.exe" if tc["platform"].startswith("win-") else "hello")
        source.write_text('#include <stdio.h>\nint main(void){puts("toolchain-ok");return 0;}\n', encoding="utf-8")
        compile_run = subprocess.run(
            [tc["gcc"], "-O2", "-o", str(executable), str(source)],
            capture_output=True, text=True, timeout=60, env=tc["env"], cwd=temp, check=False,
        )
        if compile_run.returncode != 0:
            return {"ok": False, "gcc_version": version, "compile_ok": False, "run_ok": False, "errors": [f"compile failed: {compile_run.stderr[:1000]}"]}
        program_run = subprocess.run(
            [str(executable)], capture_output=True, text=True, timeout=15,
            env=tc["env"], cwd=temp, check=False,
        )
        run_ok = program_run.returncode == 0 and program_run.stdout.strip() == "toolchain-ok"
        errors = [] if run_ok else [f"run failed: rc={program_run.returncode} stderr={program_run.stderr[:500]}"]
        return {"ok": run_ok, "gcc_version": version, "compile_ok": True, "run_ok": run_ok, "errors": errors}


__all__ = [
    "clear_toolchain_cache", "compiler_self_test", "detect_platform", "ensure_toolchain",
    "resolve_toolchain", "toolchain_available",
]
