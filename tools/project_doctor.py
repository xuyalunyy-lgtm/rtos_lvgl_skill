#!/usr/bin/env python3
"""Inspect an embedded project and generate a local project manifest.

The default inspection is offline and read-only.  Writing a manifest and
running a build both require explicit command-line flags.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {".git", ".github", ".vscode", "build", "out", "dist", "node_modules", "__pycache__", ".pytest_cache"}
TEXT_SUFFIXES = {".c", ".h", ".cpp", ".hpp", ".py", ".txt", ".conf", ".ini", ".cmake", ".md", ".yml", ".yaml"}
PLATFORM_MARKERS = {
    "esp32": ("idf_component_register", "esp-idf", "idf.py", "sdkconfig", "esp_log"),
    "zephyr": ("zephyr", "west.yml", "prj.conf", "zephyr_library", "k_thread_"),
    "stm32": ("stm32cube", ".ioc", "stm32_hal", "hal_gpio"),
    "jl": ("jieli", "ac79", "ac792", "thread_fork"),
    "bk": ("bk_idk", "bk725", "bk_"),
}
FRAMEWORK_MARKERS = {
    "freertos": ("freertos.h", "freertosconfig.h", "xtaskcreate", "xqueuesend"),
    "zephyr": ("zephyr", "k_thread_", "kconfig"),
    "lvgl": ("lvgl.h", "lv_obj_", "lv_init("),
    "lwip": ("lwip/", "tcpip_init", "lwip_"),
    "mbedtls": ("mbedtls/", "mbedtls_ssl_"),
    "littlefs": ("littlefs.h", "lfs_mount"),
}
ARTIFACT_SUFFIXES = {".elf", ".map", ".bin", ".hex", ".uf2"}


def _relative(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _files(root: Path) -> list[Path]:
    return [path for path in root.rglob("*") if path.is_file() and not any(part in SKIP_DIRS for part in path.relative_to(root).parts)]


def _text(path: Path) -> str:
    if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in {"CMakeLists.txt", "Makefile", "Kconfig", "sdkconfig", "sdkconfig.defaults", "prj.conf", "west.yml", ".config"}:
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="ignore")[:250_000].lower()
    except OSError:
        return ""


def _marker_hits(files: list[Path], root: Path, markers: tuple[str, ...]) -> list[str]:
    hits: list[str] = []
    lowered = tuple(marker.lower() for marker in markers)
    for path in files:
        relative = _relative(root, path).lower()
        body = _text(path)
        if any(marker in relative or marker in body for marker in lowered):
            hits.append(_relative(root, path))
    return sorted(set(hits))[:8]


def _parse_config(path: Path) -> dict[str, str]:
    """Parse the simple KEY=VALUE syntax used by Kconfig/sdkconfig files."""
    values: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return values
    for line in lines:
        line = line.strip()
        if not line:
            continue
        disabled = re.fullmatch(r"#\s*(CONFIG_[A-Za-z0-9_]+)\s+is\s+not\s+set", line)
        if disabled:
            values[disabled.group(1)] = "n"
            continue
        if line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"')
    return values


def _enabled_configs(config: dict[str, str]) -> list[str]:
    """Return the enabled CONFIG_* symbols in deterministic manifest order."""
    return sorted(
        key for key, value in config.items()
        if key.startswith("CONFIG_") and value.lower() in {"y", "1", "true", "yes", "on"}
    )


def _find_artifacts(root: Path) -> dict[str, list[str]]:
    build = root / "build"
    artifacts = {"elf": [], "map": [], "firmware": []}
    if not build.is_dir():
        return artifacts
    for path in build.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in ARTIFACT_SUFFIXES:
            continue
        relative = _relative(root, path)
        suffix = path.suffix.lower()
        if suffix == ".elf":
            artifacts["elf"].append(relative)
        elif suffix == ".map":
            artifacts["map"].append(relative)
        else:
            artifacts["firmware"].append(relative)
    return {name: sorted(paths) for name, paths in artifacts.items()}


def _parse_esp_idf(root: Path) -> dict[str, Any]:
    config_paths = [path for path in (root / "sdkconfig.defaults", root / "sdkconfig") if path.is_file()]
    config: dict[str, str] = {}
    for path in config_paths:
        config.update(_parse_config(path))
    target = config.get("CONFIG_IDF_TARGET")
    if not target:
        for key, value in config.items():
            if key.startswith("CONFIG_IDF_TARGET_") and value.lower() in {"y", "1", "true"}:
                target = key.removeprefix("CONFIG_IDF_TARGET_").lower()
                break
    version: str | None = None
    version_evidence: list[str] = []
    for path in (root / "CMakeLists.txt", root / "build" / "project_description.json"):
        if not path.is_file():
            continue
        try:
            body = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        match = re.search(r"(?:IDF_VERSION|idf_version|idf_ver)\s*[\"':=()\s]+v?(\d+(?:\.\d+){1,3})", body, re.IGNORECASE)
        if match:
            version = match.group(1)
            version_evidence.append(_relative(root, path))
            break
    config_files = [_relative(root, path) for path in config_paths]
    return {
        "family": "esp32",
        "chip": target.lower() if target else None,
        "board": None,
        "sdk": {"name": "esp-idf", "version": version, "evidence": version_evidence},
        "configuration": {
            "files": config_files,
            "selected": {key: config[key] for key in sorted(config) if key in {"CONFIG_IDF_TARGET", "CONFIG_FREERTOS_HZ"}},
            "enabled": _enabled_configs(config),
        },
        "build": {
            "system": "esp-idf",
            "command": ["idf.py", "build"],
            "working_directory": ".",
            "artifacts": _find_artifacts(root),
            "verification": {"status": "not_run", "level": "project_inspected"},
        },
    }


def _parse_zephyr(root: Path) -> dict[str, Any]:
    config_paths = [path for path in (root / "prj.conf", root / "build" / "zephyr" / ".config") if path.is_file()]
    config: dict[str, str] = {}
    for path in config_paths:
        config.update(_parse_config(path))
    board = config.get("CONFIG_BOARD")
    cmake = root / "CMakeLists.txt"
    if not board and cmake.is_file():
        body = cmake.read_text(encoding="utf-8", errors="ignore")
        match = re.search(r"\bset\s*\(\s*BOARD\s+([^\s)]+)", body, re.IGNORECASE)
        if match:
            board = match.group(1).strip('"')
    overlays = sorted(_relative(root, path) for path in root.rglob("*") if path.is_file() and path.suffix.lower() in {".overlay", ".dts"} and "build" not in path.relative_to(root).parts)
    config_files = [_relative(root, path) for path in config_paths] + overlays[:12]
    command = ["west", "build", "-b", board, "."] if board else None
    return {
        "family": "zephyr",
        "chip": None,
        "board": board,
        "sdk": {"name": "zephyr", "version": None, "evidence": ["west.yml"] if (root / "west.yml").is_file() else []},
        "configuration": {
            "files": config_files,
            "selected": {key: config[key] for key in sorted(config) if key in {"CONFIG_BOARD", "CONFIG_MAIN_STACK_SIZE", "CONFIG_HEAP_MEM_POOL_SIZE"}},
            "enabled": _enabled_configs(config),
        },
        "build": {
            "system": "west",
            "command": command,
            "working_directory": ".",
            "artifacts": _find_artifacts(root),
            "verification": {"status": "not_run", "level": "project_inspected"},
        },
    }


def _generic_manifest(root: Path, primary: str | None, build_systems: list[str]) -> dict[str, Any]:
    cached_build = (root / "build" / "CMakeCache.txt").is_file()
    return {
        "family": primary or "unknown",
        "chip": None,
        "board": None,
        "sdk": {"name": None, "version": None, "evidence": []},
        "configuration": {"files": [], "selected": {}, "enabled": []},
        "build": {
            "system": build_systems[0] if build_systems else None,
            "command": ["cmake", "--build", "build"] if cached_build else None,
            "working_directory": ".",
            "artifacts": _find_artifacts(root),
            "verification": {"status": "not_run", "level": "project_inspected"},
        },
    }


def _project_manifest(root: Path, primary: str | None, build_systems: list[str], source_count: int, frameworks: list[dict[str, Any]]) -> dict[str, Any]:
    if primary == "esp32":
        detected = _parse_esp_idf(root)
    elif primary == "zephyr":
        detected = _parse_zephyr(root)
    else:
        detected = _generic_manifest(root, primary, build_systems)
    return {
        "schema_version": "2.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project": {"root": str(root), "source_files": source_count},
        "platform": {"family": detected["family"], "chip": detected["chip"], "board": detected["board"]},
        "sdk": detected["sdk"],
        "frameworks": [item["name"] for item in frameworks],
        "configuration": detected["configuration"],
        "build": detected["build"],
    }


def inspect_project(root: Path) -> dict[str, Any]:
    root = root.resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Project directory not found: {root}")
    files = _files(root)
    suffixes = Counter(path.suffix.lower() or path.name for path in files)
    platform_hits = {name: _marker_hits(files, root, markers) for name, markers in PLATFORM_MARKERS.items()}
    platforms = [{"name": name, "evidence": evidence, "score": len(evidence)} for name, evidence in platform_hits.items() if evidence]
    platforms.sort(key=lambda item: (-item["score"], item["name"]))
    primary = platforms[0]["name"] if platforms and (len(platforms) == 1 or platforms[0]["score"] > platforms[1]["score"]) else None
    frameworks = [{"name": name, "evidence": _marker_hits(files, root, markers)} for name, markers in FRAMEWORK_MARKERS.items()]
    frameworks = [item for item in frameworks if item["evidence"]]
    build_systems: list[str] = []
    names = {path.name.lower() for path in files}
    if "platformio.ini" in names:
        build_systems.append("platformio")
    if "cmakelists.txt" in names:
        build_systems.append("cmake")
    if "makefile" in names:
        build_systems.append("make")
    if "west.yml" in names or "prj.conf" in names:
        build_systems.append("west")
    source_count = sum(1 for path in files if path.suffix.lower() in {".c", ".h", ".cpp", ".hpp"})
    manifest = _project_manifest(root, primary, build_systems, source_count, frameworks)

    findings: list[dict[str, str]] = []
    if not source_count:
        findings.append({"severity": "warning", "code": "NO_EMBEDDED_SOURCE", "message": "No C/C++ source files were found."})
    if not primary:
        findings.append({"severity": "warning", "code": "PLATFORM_UNCERTAIN", "message": "Could not identify one primary platform from local project markers."})
    elif len(platforms) > 1:
        findings.append({"severity": "info", "code": "MULTI_PLATFORM_MARKERS", "message": "Multiple platform markers found; primary platform was selected by evidence score."})
    if not build_systems:
        findings.append({"severity": "warning", "code": "BUILD_SYSTEM_UNDETECTED", "message": "No CMake, Make, PlatformIO, or West build marker was found."})
    if primary == "zephyr" and not manifest["platform"]["board"]:
        findings.append({"severity": "warning", "code": "ZEPHYR_BOARD_UNDETECTED", "message": "No Zephyr board was found in local configuration; set CONFIG_BOARD or supply a board before building."})

    recommendations = [{"command": f'python tools/project_doctor.py "{root}" --run-review', "reason": "Run the registered static review pipeline after confirming the detected platform."}]
    if primary:
        recommendations.insert(0, {"command": f'python tools/run_review.py --dir "{root}" --platform {primary}', "reason": f"Review using detected {primary} platform rules."})
    command = manifest["build"]["command"]
    if command:
        recommendations.append({"command": " ".join(command), "reason": "Build command inferred from local project configuration; run it only when build tools are installed."})
    elif primary == "zephyr":
        recommendations.append({"command": "west build -b <board> .", "reason": "Select a Zephyr board explicitly, then build."})

    return {
        "schema_version": "2.0",
        "project_root": str(root),
        "source_files": source_count,
        "file_types": dict(sorted(suffixes.items())),
        "platforms": platforms,
        "primary_platform": primary,
        "frameworks": frameworks,
        "build_systems": build_systems,
        "findings": findings,
        "recommendations": recommendations,
        "project_manifest": manifest,
    }


def write_manifest(report: dict[str, Any], path: Path) -> Path:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report["project_manifest"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def verify_build(report: dict[str, Any], timeout: int) -> int:
    build = report["project_manifest"]["build"]
    command = build["command"]
    verification = build["verification"]
    if not command:
        verification.update({"status": "not_available", "level": "build_not_started", "message": "No safe build command could be inferred from local configuration."})
        return 2
    root = Path(report["project_root"])
    try:
        proc = subprocess.run(command, cwd=root, capture_output=True, encoding="utf-8", errors="replace", timeout=timeout)
        verification.update({"status": "passed" if proc.returncode == 0 else "failed", "level": "build_executed", "command": command, "exit_code": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr})
        build["artifacts"] = _find_artifacts(root)
        return 0 if proc.returncode == 0 else 1
    except FileNotFoundError:
        verification.update({"status": "tool_not_found", "level": "build_not_started", "command": command, "message": f"Build tool not found: {command[0]}"})
        return 2
    except subprocess.TimeoutExpired:
        verification.update({"status": "timed_out", "level": "build_executed", "command": command, "message": f"Build exceeded {timeout} seconds."})
        return 1


def _run_review(
    root: Path,
    platform: str | None,
    configuration_files: list[str],
    build_system: str | None,
) -> dict[str, Any]:
    command = [sys.executable, str(ROOT / "tools" / "run_review.py"), "--dir", str(root), "--json"]
    if platform:
        command.extend(["--platform", platform])
    if build_system:
        command.extend(["--build-system", build_system])
    for relative_path in configuration_files:
        config_path = root / relative_path
        if config_path.is_file():
            command.extend(["--config", str(config_path)])
    history_dir = root / "artifacts" / "review_history"
    command.extend(["--history-dir", str(history_dir)])
    proc = subprocess.run(command, cwd=ROOT, capture_output=True, encoding="utf-8", errors="replace")
    return {
        "command": command,
        "context": {
            "platform": platform,
            "build_system": build_system,
            "configuration_files": configuration_files,
        },
        "exit_code": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }


def _print_human(report: dict[str, Any]) -> None:
    manifest = report["project_manifest"]
    print(f"Project: {report['project_root']}")
    print(f"Source files: {report['source_files']}")
    print(f"Primary platform: {report['primary_platform'] or 'undetermined'}")
    print(f"Detected target: {manifest['platform']['chip'] or manifest['platform']['board'] or 'undetermined'}")
    print(f"SDK: {manifest['sdk']['name'] or 'undetected'} {manifest['sdk']['version'] or ''}".rstrip())
    print(f"Build systems: {', '.join(report['build_systems']) or 'undetected'}")
    print(f"Frameworks: {', '.join(item['name'] for item in report['frameworks']) or 'undetected'}")
    if report["findings"]:
        print("Findings:")
        for finding in report["findings"]:
            print(f"  [{finding['severity']}] {finding['code']}: {finding['message']}")
    print("Recommended next commands:")
    for item in report["recommendations"]:
        print(f"  {item['command']}\n    {item['reason']}")


def run_self_test() -> int:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "main").mkdir()
        (root / "build").mkdir()
        (root / "sdkconfig").write_text('CONFIG_IDF_TARGET="esp32s3"\nCONFIG_FREERTOS_HZ=1000\n', encoding="utf-8")
        (root / "CMakeLists.txt").write_text('set(IDF_VERSION "5.2.1")\nidf_component_register(SRCS main.c)\n', encoding="utf-8")
        (root / "main" / "main.c").write_text('#include "freertos/FreeRTOS.h"\n#include "lvgl.h"\n', encoding="utf-8")
        (root / "build" / "app.elf").write_bytes(b"ELF")
        report = inspect_project(root)
        assert report["primary_platform"] == "esp32"
        assert report["project_manifest"]["platform"]["chip"] == "esp32s3"
        assert report["project_manifest"]["build"]["command"] == ["idf.py", "build"]
        assert report["project_manifest"]["build"]["artifacts"]["elf"] == ["build/app.elf"]
        destination = write_manifest(report, root / "project_manifest.json")
        assert json.loads(destination.read_text(encoding="utf-8"))["platform"]["chip"] == "esp32s3"
    print("[project-doctor] self-test passed")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", nargs="?", default=".", type=Path)
    parser.add_argument("--json", action="store_true", help="Emit a machine-readable report")
    parser.add_argument("--run-review", action="store_true", help="Run tools/run_review.py after inspection")
    parser.add_argument("--write-manifest", action="store_true", help="Write project_manifest.json in the inspected project")
    parser.add_argument("--manifest", type=Path, help="Write the generated manifest to this path")
    parser.add_argument("--verify-build", action="store_true", help="Execute the inferred build command (explicit opt-in)")
    parser.add_argument("--build-timeout", type=int, default=600, help="Maximum seconds for --verify-build (default: 600)")
    parser.add_argument("--strict", action="store_true", help="Return non-zero when warnings are present")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return run_self_test()
    if args.build_timeout <= 0:
        parser.error("--build-timeout must be positive")
    try:
        report = inspect_project(args.project)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    build_exit = 0
    if args.run_review:
        report["review"] = _run_review(
            Path(report["project_root"]),
            report["primary_platform"],
            report["project_manifest"]["configuration"]["files"],
            report["project_manifest"]["build"]["system"],
        )
    if args.verify_build:
        build_exit = verify_build(report, args.build_timeout)
    if args.write_manifest or args.manifest:
        destination = args.manifest or (Path(report["project_root"]) / "project_manifest.json")
        report["manifest_path"] = str(write_manifest(report, destination))
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        _print_human(report)
        if report.get("manifest_path"):
            print(f"Manifest written: {report['manifest_path']}")
        if args.run_review:
            print(f"Review exit code: {report['review']['exit_code']}")
            if report["review"]["stdout"].strip():
                print(report["review"]["stdout"].rstrip())
            if report["review"]["stderr"].strip():
                print(report["review"]["stderr"].rstrip(), file=sys.stderr)
        if args.verify_build:
            verification = report["project_manifest"]["build"]["verification"]
            print(f"Build verification: {verification['status']}")
            if verification.get("stdout", "").strip():
                print(verification["stdout"].rstrip())
            if verification.get("stderr", "").strip():
                print(verification["stderr"].rstrip(), file=sys.stderr)
    has_warning = any(item["severity"] == "warning" for item in report["findings"])
    review_failed = args.run_review and report["review"]["exit_code"] != 0
    return 1 if review_failed or build_exit == 1 or (args.strict and has_warning) else (2 if build_exit == 2 else 0)


if __name__ == "__main__":
    raise SystemExit(main())
