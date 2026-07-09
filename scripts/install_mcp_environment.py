#!/usr/bin/env python3
"""Install and check the local environment required by the MCP adapter."""
from __future__ import annotations

import argparse
import importlib
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


PYTHON_MIN = (3, 10)


@dataclass(frozen=True)
class PipDependency:
    package: str
    import_name: str
    min_version: str
    reason: str


@dataclass(frozen=True)
class ExternalTool:
    name: str
    reason: str


@dataclass(frozen=True)
class EnvironmentVariable:
    name: str
    reason: str
    alternatives: tuple[str, ...] = ()


PIP_DEPENDENCIES = (
    PipDependency(
        package="PyYAML>=6.0",
        import_name="yaml",
        min_version="6.0",
        reason="tools/sdk_lookup.py loads SDK abstraction YAML maps used by lookup_sdk.",
    ),
    PipDependency(
        package="Pillow>=10.0",
        import_name="PIL",
        min_version="10.0",
        reason="LVGL image conversion and initial-loading design analysis read PNG/JPEG assets.",
    ),
)

OPTIONAL_TOOLS = (
    ExternalTool("cmake", "Build the LVGL regression sandbox."),
    ExternalTool("ninja", "Use the preferred fast CMake generator for the LVGL sandbox."),
)

OPTIONAL_ENVIRONMENT = (
    EnvironmentVariable("LVGL_ROOT", "Path to a local LVGL source checkout for real simulator builds."),
    EnvironmentVariable("SDL2_DIR", "Path to the SDL2 CMake package directory.", alternatives=("SDL2_ROOT",)),
    EnvironmentVariable("SDL2_BIN", "Directory containing SDL2.dll on Windows runtime runs."),
    EnvironmentVariable("LV_FONT_CONV", "Optional lv_font_conv executable for generating compact LVGL fonts."),
)


def _version_tuple(value: str) -> tuple[int, ...]:
    parts = re.findall(r"\d+", value)
    return tuple(int(part) for part in parts[:3]) if parts else (0,)


def _version_ok(found: str | None, minimum: str) -> bool:
    if not found:
        return False
    return _version_tuple(found) >= _version_tuple(minimum)


def _in_virtualenv() -> bool:
    return bool(getattr(sys, "real_prefix", None)) or sys.prefix != getattr(sys, "base_prefix", sys.prefix)


def _python_status() -> dict[str, Any]:
    current = sys.version_info[:3]
    return {
        "ok": current >= PYTHON_MIN,
        "executable": sys.executable,
        "version": ".".join(str(part) for part in current),
        "minimum": ".".join(str(part) for part in PYTHON_MIN),
    }


def _dependency_status(dep: PipDependency) -> dict[str, Any]:
    status = asdict(dep)
    try:
        module = importlib.import_module(dep.import_name)
    except Exception as exc:
        status.update({"installed": False, "version": None, "ok": False, "error": str(exc)})
        return status
    version = str(getattr(module, "__version__", "") or "")
    status.update({"installed": True, "version": version or "unknown", "ok": _version_ok(version, dep.min_version)})
    return status


def _tool_status(tool: ExternalTool) -> dict[str, Any]:
    path = shutil.which(tool.name)
    return {"name": tool.name, "available": bool(path), "path": path or "", "reason": tool.reason}


def _environment_status(var: EnvironmentVariable) -> dict[str, Any]:
    names = (var.name,) + var.alternatives
    values = {name: os.environ.get(name, "") for name in names}
    return {
        "name": var.name,
        "alternatives": list(var.alternatives),
        "available": any(bool(value) for value in values.values()),
        "values": values,
        "reason": var.reason,
    }


def build_report() -> dict[str, Any]:
    python = _python_status()
    pip_deps = [_dependency_status(dep) for dep in PIP_DEPENDENCIES]
    missing = [dep for dep in pip_deps if not dep["ok"]]
    report = {
        "ok": bool(python["ok"]) and not missing,
        "python": python,
        "pip_dependencies": pip_deps,
        "missing_pip_packages": [dep["package"] for dep in missing],
        "optional_tools": [_tool_status(tool) for tool in OPTIONAL_TOOLS],
        "optional_environment": [_environment_status(var) for var in OPTIONAL_ENVIRONMENT],
    }
    return report


def _pip_install_command(packages: list[str], *, use_user: bool, upgrade: bool, quiet: bool) -> list[str]:
    cmd = [sys.executable, "-m", "pip", "install"]
    if quiet:
        cmd.append("-q")
    if use_user:
        cmd.append("--user")
    if upgrade:
        cmd.append("--upgrade")
    cmd.extend(packages)
    return cmd


def install_missing(packages: list[str], *, use_user: bool, upgrade: bool, quiet: bool, timeout: int) -> dict[str, Any]:
    if not packages:
        return {"ran": False, "ok": True, "command": [], "stdout": "", "stderr": "", "exit_code": 0}
    cmd = _pip_install_command(packages, use_user=use_user, upgrade=upgrade, quiet=quiet)
    proc = subprocess.run(
        cmd,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    return {
        "ran": True,
        "ok": proc.returncode == 0,
        "command": cmd,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "exit_code": proc.returncode,
    }


def _print_human(report: dict[str, Any]) -> None:
    py = report["python"]
    print(f"Python: {py['version']} ({py['executable']})")
    for dep in report["pip_dependencies"]:
        state = "OK" if dep["ok"] else "MISSING"
        version = dep.get("version") or "-"
        print(f"{state}: {dep['package']} import={dep['import_name']} version={version}")
    for tool in report["optional_tools"]:
        state = "OK" if tool["available"] else "optional-missing"
        path = f" -> {tool['path']}" if tool["path"] else ""
        print(f"{state}: {tool['name']}{path}")
    for var in report["optional_environment"]:
        state = "OK" if var["available"] else "optional-unset"
        names = ", ".join([var["name"], *var["alternatives"]])
        print(f"{state}: {names}")


def run_self_test() -> int:
    report = build_report()
    packages = {dep["package"] for dep in report["pip_dependencies"]}
    assert "PyYAML>=6.0" in packages
    assert "Pillow>=10.0" in packages
    assert report["python"]["minimum"] == "3.10"
    print("install_mcp_environment self-test passed")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Install/check MCP Python environment")
    parser.add_argument("--check", action="store_true", help="only check dependencies; do not install")
    parser.add_argument("--dry-run", action="store_true", help="show what would be installed")
    parser.add_argument("--json", action="store_true", help="print a JSON report")
    parser.add_argument("--quiet", action="store_true", help="suppress normal human-readable output")
    parser.add_argument("--upgrade", action="store_true", help="ask pip to upgrade dependencies")
    parser.add_argument("--timeout", type=int, default=300, help="pip install timeout in seconds")
    parser.add_argument("--self-test", action="store_true", help="run script self-test")
    user_group = parser.add_mutually_exclusive_group()
    user_group.add_argument("--user", dest="user", action="store_true", default=None, help="force pip --user")
    user_group.add_argument("--no-user", dest="user", action="store_false", help="disable pip --user")
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    report = build_report()
    use_user = (not _in_virtualenv()) if args.user is None else bool(args.user)
    report["pip_user_install"] = use_user
    report["pip_install"] = {"ran": False, "ok": True, "command": [], "stdout": "", "stderr": "", "exit_code": 0}

    if args.dry_run:
        report["dry_run"] = True
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        elif not args.quiet:
            _print_human(report)
            if report["missing_pip_packages"]:
                print("Would install: " + ", ".join(report["missing_pip_packages"]))
        return 0

    if not args.check and report["missing_pip_packages"] and report["python"]["ok"]:
        install = install_missing(
            list(report["missing_pip_packages"]),
            use_user=use_user,
            upgrade=args.upgrade,
            quiet=args.quiet,
            timeout=args.timeout,
        )
        report["pip_install"] = install
        report = {**build_report(), "pip_user_install": use_user, "pip_install": install}

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    elif not args.quiet:
        _print_human(report)

    if not report["ok"] and report.get("pip_install", {}).get("ran"):
        install = report["pip_install"]
        if install.get("stderr"):
            print(install["stderr"].strip()[-2000:], file=sys.stderr)
        elif install.get("stdout"):
            print(install["stdout"].strip()[-2000:], file=sys.stderr)

    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
