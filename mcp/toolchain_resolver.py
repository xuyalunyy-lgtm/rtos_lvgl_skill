"""Portable MinGW-w64 UCRT64 toolchain resolver for LVGL compilation.

Mirrors the lvgl_sim_resolver.py pattern: platform detect → manifest verify
→ SHA256 check → absolute paths.  Never modifies global PATH; callers receive
an ``env`` dict suitable for ``subprocess.Popen(env=...)``.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
from functools import lru_cache
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
_TOOLCHAIN_DIR = _ROOT / "runtime" / "toolchain"
_MANIFEST_PATH = _TOOLCHAIN_DIR / "manifest.json"


def detect_platform() -> str:
    """Return a canonical ``os-arch`` string for the current host."""
    import sys
    import platform as _plat

    system = sys.platform
    machine = _plat.machine().lower()

    if system == "win32":
        return "win-x64"
    if system == "linux":
        if machine in ("x86_64", "amd64"):
            return "linux-x64"
        if machine in ("aarch64", "arm64"):
            return "linux-arm64"
    if system == "darwin":
        if machine == "arm64":
            return "macos-arm64"
        return "macos-x64"

    return f"unknown-{system}-{machine}"


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_manifest() -> dict[str, Any]:
    if not _MANIFEST_PATH.exists():
        return {"schema_version": 0, "platforms": {}}
    return json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))


def _verify_files(toolchain_dir: Path, expected: dict[str, str]) -> list[str]:
    """Verify SHA256 for each file in *expected*.  Return list of errors."""
    errors: list[str] = []
    for rel_path, expected_hash in expected.items():
        full = toolchain_dir / rel_path
        if not full.exists():
            errors.append(f"missing: {rel_path}")
            continue
        actual = _sha256_file(full)
        if actual != expected_hash:
            errors.append(f"hash mismatch: {rel_path}")
    return errors


@lru_cache(maxsize=1)
def resolve_toolchain(platform: str | None = None) -> dict[str, Any]:
    """Resolve the bundled toolchain for *platform* (default: current host).

    Returns::

        {
            "ok": bool,
            "platform": str,
            "toolchain_dir": str | None,
            "bin_dir": str | None,
            "gcc": str | None,
            "ar": str | None,
            "as_exe": str | None,
            "ld": str | None,
            "ninja": str | None,
            "env": dict | None,      # env vars for subprocess
            "version": str | None,
            "flavor": str | None,
            "errors": list[str],
        }
    """
    plat = platform or detect_platform()
    manifest = _load_manifest()
    platforms = manifest.get("platforms", {})

    if plat not in platforms:
        return {
            "ok": False,
            "platform": plat,
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
            "errors": [f"no toolchain manifest for platform '{plat}'"],
        }

    entry = platforms[plat]
    toolchain_dir = _TOOLCHAIN_DIR / plat

    if not toolchain_dir.is_dir():
        return {
            "ok": False,
            "platform": plat,
            "toolchain_dir": None,
            "bin_dir": None,
            "gcc": None,
            "ar": None,
            "as_exe": None,
            "ld": None,
            "ninja": None,
            "env": None,
            "version": entry.get("version"),
            "flavor": entry.get("flavor"),
            "errors": [f"toolchain directory not found: {toolchain_dir}"],
        }

    # Verify file hashes
    expected_files = entry.get("files", {})
    errors = _verify_files(toolchain_dir, expected_files)
    if errors:
        return {
            "ok": False,
            "platform": plat,
            "toolchain_dir": str(toolchain_dir),
            "bin_dir": None,
            "gcc": None,
            "ar": None,
            "as_exe": None,
            "ld": None,
            "ninja": None,
            "env": None,
            "version": entry.get("version"),
            "flavor": entry.get("flavor"),
            "errors": errors,
        }

    bin_dir = toolchain_dir / "bin"
    is_win = plat.startswith("win")
    exe = ".exe" if is_win else ""

    gcc = str(bin_dir / f"gcc{exe}")
    ar = str(bin_dir / f"ar{exe}")
    as_exe = str(bin_dir / f"as{exe}")
    ld = str(bin_dir / f"ld{exe}")
    ninja = str(bin_dir / f"ninja{exe}")

    # Build env: prepend toolchain bin_dir to PATH without touching global
    env = dict(os.environ)
    env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")

    return {
        "ok": True,
        "platform": plat,
        "toolchain_dir": str(toolchain_dir),
        "bin_dir": str(bin_dir),
        "gcc": gcc,
        "ar": ar,
        "as_exe": as_exe,
        "ld": ld,
        "ninja": ninja,
        "env": env,
        "version": entry.get("version"),
        "flavor": entry.get("flavor"),
        "errors": [],
    }


def toolchain_available(platform: str | None = None) -> bool:
    """Quick check: is the bundled toolchain usable?"""
    return resolve_toolchain(platform)["ok"]


def compiler_self_test(platform: str | None = None) -> dict[str, Any]:
    """Run a minimal self-test: compile and run a hello-world C program.

    Returns::

        {"ok": bool, "gcc_version": str, "compile_ok": bool, "run_ok": bool, "errors": list}
    """
    import subprocess
    import tempfile

    tc = resolve_toolchain(platform)
    if not tc["ok"]:
        return {"ok": False, "gcc_version": None, "compile_ok": False, "run_ok": False, "errors": tc["errors"]}

    errors: list[str] = []
    gcc = tc["gcc"]
    env = tc["env"]
    is_win = tc["platform"].startswith("win")

    # Get GCC version
    try:
        ver_out = subprocess.run(
            [gcc, "--version"],
            capture_output=True, text=True, timeout=15, env=env,
        )
        gcc_version = ver_out.stdout.splitlines()[0] if ver_out.stdout else "unknown"
    except Exception as exc:
        return {"ok": False, "gcc_version": None, "compile_ok": False, "run_ok": False, "errors": [str(exc)]}

    # Compile hello world
    with tempfile.TemporaryDirectory(prefix="mcp_tc_test_") as tmp:
        src = Path(tmp) / "hello.c"
        exe = Path(tmp) / ("hello.exe" if is_win else "hello")
        src.write_text(
            '#include <stdio.h>\nint main(void) { printf("ok\\n"); return 0; }\n',
            encoding="utf-8",
        )
        try:
            comp = subprocess.run(
                [gcc, "-O2", "-o", str(exe), str(src)],
                capture_output=True, text=True, timeout=30, env=env, cwd=tmp,
            )
            compile_ok = comp.returncode == 0
            if not compile_ok:
                errors.append(f"compile failed: {comp.stderr[:500]}")
        except Exception as exc:
            return {"ok": False, "gcc_version": gcc_version, "compile_ok": False, "run_ok": False, "errors": [str(exc)]}

        if not compile_ok:
            return {"ok": False, "gcc_version": gcc_version, "compile_ok": False, "run_ok": False, "errors": errors}

        # Run
        try:
            run = subprocess.run(
                [str(exe)],
                capture_output=True, text=True, timeout=15, env=env, cwd=tmp,
            )
            run_ok = run.returncode == 0 and "ok" in run.stdout
            if not run_ok:
                errors.append(f"run failed: rc={run.returncode} stdout={run.stdout!r} stderr={run.stderr[:300]}")
        except Exception as exc:
            return {"ok": False, "gcc_version": gcc_version, "compile_ok": True, "run_ok": False, "errors": [str(exc)]}

    return {
        "ok": compile_ok and run_ok,
        "gcc_version": gcc_version,
        "compile_ok": compile_ok,
        "run_ok": run_ok,
        "errors": errors,
    }
