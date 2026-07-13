#!/usr/bin/env python3
"""
Reproducible verification bundle v9.0.6 — Package logs, configs, commands, checker results for issue review and handoff.

Usage:
    python tools/repro_bundle.py --workflow debug_crash --dir ./src --output bundle.json
    python tools/repro_bundle.py --workflow project_review --dir ./src --platform esp32
    python tools/repro_bundle.py --self-test
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# Force UTF-8 output on Windows
if sys.platform == "win32":
    os.environ.setdefault("PYTHONUTF8", "1")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

TOOLS_DIR = Path(__file__).resolve().parent
SKILL_ROOT = TOOLS_DIR.parent


# ============================================================================
# Data structures
# ============================================================================

@dataclass
class ReproBundle:
    """Reproducible verification bundle."""
    version: str = "9.0.6"
    timestamp: str = ""
    workflow: str = ""              # debug_crash / bring_up / memory / project_review
    platform: str = ""
    platform_profile: dict = field(default_factory=dict)
    logs: list[dict] = field(default_factory=list)          # [{source, content}]
    config_snapshot: dict = field(default_factory=dict)      # build config / sdkconfig
    commands: list[dict] = field(default_factory=list)       # [{command, description, exit_code}]
    addr2line: list[dict] = field(default_factory=list)      # [{addr, file, line}]
    memory_baseline: dict = field(default_factory=dict)      # heap / stack stats
    checker_json: list[dict] = field(default_factory=list)   # checker outputs
    evidence: dict = field(default_factory=dict)             # link to delivery evidence
    environment: dict = field(default_factory=dict)          # OS, Python, etc.
    git_snapshot: dict = field(default_factory=dict)         # status/diff context

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)


# ============================================================================
# Collectors
# ============================================================================

def _collect_environment() -> dict:
    """Collect runtime environment information."""
    return {
        "os": platform.system(),
        "os_version": platform.version(),
        "python": platform.python_version(),
        "arch": platform.machine(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _collect_platform_profile(platform_name: str) -> dict:
    """Load platform profile."""
    profile_path = SKILL_ROOT / "product_profiles" / f"{platform_name}.json"
    if profile_path.exists():
        return json.loads(profile_path.read_text(encoding="utf-8"))
    return {"platform": platform_name}


def _collect_config_snapshot(dir_path: str) -> dict:
    """Collect build configuration snapshot."""
    config = {}
    root = Path(dir_path)

    # sdkconfig.defaults
    for name in ["sdkconfig.defaults", "sdkconfig", "prj.conf", "Kconfig"]:
        for p in root.rglob(name):
            try:
                config[str(p.relative_to(root))] = p.read_text(encoding="utf-8", errors="replace")[:4096]
            except Exception:
                pass

    # CMakeLists.txt
    for p in root.rglob("CMakeLists.txt"):
        try:
            rel = str(p.relative_to(root))
            if len(rel) < 100:  # skip deeply nested
                config[rel] = p.read_text(encoding="utf-8", errors="replace")[:2048]
        except Exception:
            pass

    return config


def _run_command(cmd: str | list[str], description: str = "") -> dict:
    """Run a command and capture output."""
    import shlex
    try:
        cmd_parts = shlex.split(cmd) if isinstance(cmd, str) else cmd
        proc = subprocess.run(
            cmd_parts, capture_output=True,
            encoding="utf-8", errors="replace", timeout=60,
        )
        cmd_str = cmd if isinstance(cmd, str) else " ".join(cmd)
        return {
            "command": cmd_str,
            "description": description,
            "exit_code": proc.returncode,
            "stdout": proc.stdout[:2048],
            "stderr": proc.stderr[:1024],
        }
    except subprocess.TimeoutExpired:
        cmd_str = cmd if isinstance(cmd, str) else " ".join(cmd)
        return {"command": cmd_str, "description": description, "exit_code": -1, "error": "timeout"}
    except Exception as e:
        return {"command": cmd, "description": description, "exit_code": -1, "error": str(e)}


def _run_git(args: list[str], repo: Path) -> dict:
    cmd = ["git", "-C", str(repo), *args]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        return {
            "command": " ".join(cmd),
            "exit_code": proc.returncode,
            "stdout": proc.stdout[:12000],
            "stderr": proc.stderr[:2000],
        }
    except Exception as exc:
        return {"command": " ".join(cmd), "exit_code": -1, "error": str(exc)}


def _collect_git_snapshot(dir_path: str) -> dict:
    root = Path(dir_path).resolve()
    try:
        probe = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
    except Exception as exc:
        return {"available": False, "reason": str(exc)}
    if probe.returncode != 0:
        return {"available": False, "reason": probe.stderr.strip()[:500]}

    repo = Path(probe.stdout.strip())
    return {
        "available": True,
        "repo_root": str(repo),
        "head": _run_git(["rev-parse", "--short", "HEAD"], repo),
        "status_short": _run_git(["status", "--short"], repo),
        "diff_stat": _run_git(["diff", "--stat"], repo),
        "diff": _run_git(["diff", "--", "."], repo),
    }


def _run_checkers(dir_path: str, platform_name: str = "freertos") -> list[dict]:
    """Run default checker suite and collect results."""
    results = []
    cmd_parts = [sys.executable, str(TOOLS_DIR / "run_review.py"), "--dir", dir_path, "--platform", platform_name, "--json"]
    try:
        proc = subprocess.run(
            cmd_parts, capture_output=True,
            encoding="utf-8", errors="replace", timeout=300,
            cwd=str(SKILL_ROOT),
        )
        if proc.returncode >= 0:
            try:
                data = json.loads(proc.stdout)
                results.append({
                    "checker": "run_review",
                    "exit_code": proc.returncode,
                    "total_issues": data.get("total_issues", 0),
                    "files_checked": data.get("files_checked", 0),
                })
            except json.JSONDecodeError:
                results.append({
                    "checker": "run_review",
                    "exit_code": proc.returncode,
                    "raw_output": proc.stdout[:1024],
                })
    except Exception as e:
        results.append({"checker": "run_review", "error": str(e)})

    return results


def _collect_logs(dir_path: str, extra_paths: list[str] | None = None) -> list[dict]:
    """Collect log files."""
    logs = []
    root = Path(dir_path)

    # Find common log files
    for pattern in ["*.log", "build_log*", "crash_log*", "coredump*"]:
        for p in sorted(root.rglob(pattern))[:10]:
            try:
                content = p.read_text(encoding="utf-8", errors="replace")[:8192]
                logs.append({"source": str(p.relative_to(root)), "content": content})
            except Exception:
                pass

    for raw in extra_paths or []:
        path = Path(raw)
        candidates = sorted(path.rglob("*")) if path.is_dir() else [path]
        for p in candidates:
            if not p.is_file() or p.suffix.lower() not in {".log", ".txt", ".out"}:
                continue
            try:
                logs.append({"source": str(p), "content": p.read_text(encoding="utf-8", errors="replace")[:8192]})
            except Exception:
                pass

    return logs


def _parse_addr2line(output: str) -> list[dict]:
    """Parse addr2line output."""
    results = []
    for line in output.splitlines():
        line = line.strip()
        if ":" in line and "(" in line:
            # Format: 0x400d1234 at function_name at file:line
            parts = line.split(" at ", 1)
            if len(parts) == 2:
                addr = parts[0].strip()
                loc = parts[1].strip()
                if ":" in loc:
                    file_line = loc.rsplit(":", 1)
                    results.append({
                        "addr": addr,
                        "file": file_line[0],
                        "line": int(file_line[1]) if file_line[1].isdigit() else 0,
                    })
    return results


# ============================================================================
# Workflow collectors
# ============================================================================

WORKFLOW_CONFIGS = {
    "debug_crash": {
        "description": "Crash debug reproduction bundle",
        "collect": ["env", "platform", "logs", "config", "checker"],
    },
    "bring_up": {
        "description": "Board bring-up reproduction bundle",
        "collect": ["env", "platform", "config", "checker"],
    },
    "memory": {
        "description": "Memory analysis reproduction bundle",
        "collect": ["env", "platform", "config", "checker"],
    },
    "project_review": {
        "description": "Project review reproduction bundle",
        "collect": ["env", "platform", "config", "checker"],
    },
}


def collect_bundle(
    workflow: str,
    dir_path: str,
    platform_name: str = "freertos",
    *,
    log_content: str = "",
    log_paths: list[str] | None = None,
    addr2line_output: str = "",
    extra_commands: list[str] | None = None,
) -> ReproBundle:
    """Collect reproduction bundle."""
    bundle = ReproBundle(
        timestamp=datetime.now(timezone.utc).isoformat(),
        workflow=workflow,
        platform=platform_name,
    )

    config = WORKFLOW_CONFIGS.get(workflow, WORKFLOW_CONFIGS["project_review"])

    # Environment
    if "env" in config["collect"]:
        bundle.environment = _collect_environment()

    # Platform profile
    if "platform" in config["collect"]:
        bundle.platform_profile = _collect_platform_profile(platform_name)

    # Logs
    if "logs" in config["collect"]:
        bundle.logs = _collect_logs(dir_path, log_paths)
        if log_content:
            bundle.logs.append({"source": "manual_input", "content": log_content[:8192]})

    # Config snapshot
    if "config" in config["collect"]:
        bundle.config_snapshot = _collect_config_snapshot(dir_path)

    # Checker results
    if "checker" in config["collect"]:
        bundle.checker_json = _run_checkers(dir_path, platform_name)

    bundle.git_snapshot = _collect_git_snapshot(dir_path)

    # addr2line
    if addr2line_output:
        bundle.addr2line = _parse_addr2line(addr2line_output)

    # Extra commands
    if extra_commands:
        for cmd in extra_commands:
            bundle.commands.append(_run_command(cmd))

    return bundle


# ============================================================================
# Persistence
# ============================================================================

def save_bundle(bundle: ReproBundle, path: str | Path) -> Path:
    """Save reproduction bundle."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(bundle.to_json(), encoding="utf-8")
    return p



def render_repro_markdown(bundle: ReproBundle) -> str:
    lines = [
        "# Reproduction Bundle",
        "",
        f"- Workflow: `{bundle.workflow}`",
        f"- Platform: `{bundle.platform}`",
        f"- Created: `{bundle.timestamp}`",
        f"- Logs: {len(bundle.logs)}",
        f"- Config files: {len(bundle.config_snapshot)}",
        f"- Checker result groups: {len(bundle.checker_json)}",
        "",
        "## Environment",
        "",
    ]
    for key, value in bundle.environment.items():
        lines.append(f"- {key}: `{value}`")

    lines.extend(["", "## Git Snapshot", ""])
    git = bundle.git_snapshot or {}
    if git.get("available"):
        head = (git.get("head") or {}).get("stdout", "").strip()
        status = (git.get("status_short") or {}).get("stdout", "").strip()
        diff_stat = (git.get("diff_stat") or {}).get("stdout", "").strip()
        lines.append(f"- Repo: `{git.get('repo_root', '')}`")
        lines.append(f"- HEAD: `{head or 'unknown'}`")
        lines.extend(["", "### Status", "```text", status or "clean", "```"])
        lines.extend(["", "### Diff Stat", "```text", diff_stat or "no diff", "```"])
    else:
        lines.append(f"- Git unavailable: {git.get('reason', 'not a git repository')}")

    lines.extend(["", "## Logs", ""])
    if bundle.logs:
        for log in bundle.logs:
            lines.append(f"- `{log.get('source', 'unknown')}` ({len(log.get('content', ''))} chars captured)")
    else:
        lines.append("- No logs captured.")

    lines.extend(["", "## Config Snapshot", ""])
    if bundle.config_snapshot:
        for name in bundle.config_snapshot:
            lines.append(f"- `{name}`")
    else:
        lines.append("- No config files captured.")

    lines.extend(["", "## Checker Summary", ""])
    if bundle.checker_json:
        for item in bundle.checker_json:
            checker = item.get("checker", "unknown")
            exit_code = item.get("exit_code", "?")
            issues = item.get("total_issues", item.get("issues", "?"))
            lines.append(f"- `{checker}` exit={exit_code}, issues={issues}")
    else:
        lines.append("- No checker output captured.")

    lines.extend(["", "## Reproduce", "", "```powershell"])
    lines.append(
        f"python tools/repro_bundle.py --workflow {bundle.workflow} "
        f"--dir <project-dir> --platform {bundle.platform} --output-dir repro"
    )
    lines.extend(["```", ""])
    return "\n".join(lines)

def save_bundle_dir(bundle: ReproBundle, dir_path: str | Path) -> Path:
    """Save reproduction bundle as directory."""
    d = Path(dir_path)
    d.mkdir(parents=True, exist_ok=True)

    # Main JSON
    (d / "repro_bundle.json").write_text(bundle.to_json(), encoding="utf-8")
    (d / "REPRO.md").write_text(render_repro_markdown(bundle), encoding="utf-8")

    # Log files
    if bundle.logs:
        logs_dir = d / "logs"
        logs_dir.mkdir(exist_ok=True)
        for log in bundle.logs:
            source = log.get("source", "unknown").replace("/", "_").replace("\\", "_")
            (logs_dir / f"{source}.txt").write_text(log.get("content", ""), encoding="utf-8")

    # Config files
    if bundle.config_snapshot:
        config_dir = d / "config"
        config_dir.mkdir(exist_ok=True)
        for name, content in bundle.config_snapshot.items():
            safe_name = name.replace("/", "_").replace("\\", "_")
            (config_dir / safe_name).write_text(content, encoding="utf-8")

    if bundle.git_snapshot:
        git_dir = d / "git"
        git_dir.mkdir(exist_ok=True)
        for key in ["status_short", "diff_stat", "diff"]:
            item = bundle.git_snapshot.get(key, {})
            if item.get("stdout"):
                (git_dir / f"{key}.txt").write_text(item["stdout"], encoding="utf-8")

    return d


# ============================================================================
# Self-test
# ============================================================================

def run_self_test() -> int:
    passed = 0
    failed = 0

    # Test 1: Environment collection
    env = _collect_environment()
    assert "os" in env
    assert "python" in env
    print(f"[PASS] environment collection: {env['os']}")
    passed += 1

    # Test 2: Platform profile loading
    for plat in ["esp32", "stm32"]:
        profile = _collect_platform_profile(plat)
        assert "platform" in profile
        print(f"[PASS] platform profile: {plat}")
        passed += 1

    # Test 3: Bundle construction
    bundle = ReproBundle(
        timestamp=datetime.now(timezone.utc).isoformat(),
        workflow="test",
        platform="esp32",
        environment=env,
        logs=[{"source": "test.log", "content": "test log content"}],
        commands=[{"command": "echo hello", "exit_code": 0}],
    )
    assert bundle.workflow == "test"
    assert len(bundle.logs) == 1
    print("[PASS] bundle construction")
    passed += 1

    # Test 4: JSON serialization
    j = bundle.to_json()
    data = json.loads(j)
    assert data["workflow"] == "test"
    assert len(data["logs"]) == 1
    print("[PASS] bundle JSON serialization")
    passed += 1

    # Test 5: Save/load
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        tmp = f.name
    try:
        save_bundle(bundle, tmp)
        loaded = json.loads(Path(tmp).read_text(encoding="utf-8"))
        assert loaded["workflow"] == "test"
        print("[PASS] bundle save/load")
        passed += 1
    finally:
        os.unlink(tmp)

    # Test 6: collect_bundle (lightweight)
    bundle2 = collect_bundle("project_review", str(SKILL_ROOT / "examples"), "freertos")
    assert bundle2.workflow == "project_review"
    assert bundle2.platform == "freertos"
    assert "os" in bundle2.environment
    print(f"[PASS] collect_bundle: {len(bundle2.checker_json)} checker results")
    passed += 1

    # Test 7: directory output includes human-readable handoff.
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        out_dir = save_bundle_dir(bundle, Path(tmpdir) / "repro")
        assert (out_dir / "repro_bundle.json").exists()
        assert (out_dir / "REPRO.md").exists()
        print("[PASS] bundle directory output with REPRO.md")
        passed += 1

    print(f"\nSelf-test: {passed} passed, {failed} failed")
    return 1 if failed > 0 else 0


# ============================================================================
# CLI
# ============================================================================

def main() -> int:
    parser = argparse.ArgumentParser(description="Reproducible verification bundle v9.0.6")
    parser.add_argument("--workflow", choices=list(WORKFLOW_CONFIGS.keys()),
                        default="project_review", help="Workflow type")
    parser.add_argument("--dir", "-d", help="Project directory")
    parser.add_argument("--platform", "-p", default="freertos", help="Platform")
    parser.add_argument("--output", "-o", help="Output file path (JSON)")
    parser.add_argument("--output-dir", help="Output directory path")
    parser.add_argument("--log", help="Manually provided log content")
    parser.add_argument("--log-file", action="append", default=[], help="extra log file")
    parser.add_argument("--log-dir", action="append", default=[], help="extra log directory")
    parser.add_argument("--addr2line", help="addr2line 输出")
    parser.add_argument("--evidence", metavar="FILE", help="Output delivery evidence to specified file")
    parser.add_argument("--self-test", action="store_true", help="Run self-test")
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    if not args.dir:
        parser.print_help()
        return 1

    if not Path(args.dir).is_dir():
        print(f"Error: directory not found: {args.dir}", file=sys.stderr)
        return 1

    bundle = collect_bundle(
        args.workflow,
        args.dir,
        args.platform,
        log_content=args.log or "",
        log_paths=[*args.log_file, *args.log_dir],
        addr2line_output=args.addr2line or "",
    )

    # Output
    if args.output:
        save_bundle(bundle, args.output)
        print(f"[OK] Reproduction bundle saved: {args.output}")
    elif args.output_dir:
        save_bundle_dir(bundle, args.output_dir)
        print(f"[OK] Reproduction bundle directory saved: {args.output_dir}")
    else:
        print(bundle.to_json())

    # Evidence
    if args.evidence:
        try:
            from evidence_schema import make_evidence, repro_command, save_evidence
        except ImportError:
            print("[warn] evidence_schema module not available (archived), skipping evidence output", file=sys.stderr)
            return 0

        ev = make_evidence(
            source_tool="repro_bundle",
            platform=args.platform,
            reproduce_commands=[
                repro_command(
                    f"python tools/repro_bundle.py --workflow {args.workflow} --dir {args.dir} --platform {args.platform}",
                    "Reproduce verification bundle",
                ),
            ],
            assumptions=[
                f"Workflow: {args.workflow}",
                f"Platform: {args.platform}",
                f"Checker results: {len(bundle.checker_json)}",
            ],
            metadata={
                "tool_version": "9.0.6",
                "workflow": args.workflow,
                "log_count": len(bundle.logs),
                "config_keys": list(bundle.config_snapshot.keys()),
            },
        )
        save_evidence(ev, args.evidence)
        print(f"[evidence] Delivery evidence saved: {args.evidence}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
