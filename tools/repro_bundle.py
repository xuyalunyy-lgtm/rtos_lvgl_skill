#!/usr/bin/env python3
"""
可复现验证包 v9.0.6 — 打包日志、配置、命令、checker 结果，方便问题复盘和交接。

用法:
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
# 数据结构
# ============================================================================

@dataclass
class ReproBundle:
    """可复现验证包。"""
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

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)


# ============================================================================
# 收集器
# ============================================================================

def _collect_environment() -> dict:
    """收集运行环境信息。"""
    return {
        "os": platform.system(),
        "os_version": platform.version(),
        "python": platform.python_version(),
        "arch": platform.machine(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _collect_platform_profile(platform_name: str) -> dict:
    """加载平台 profile。"""
    profile_path = SKILL_ROOT / "product_profiles" / f"{platform_name}.json"
    if profile_path.exists():
        return json.loads(profile_path.read_text(encoding="utf-8"))
    return {"platform": platform_name}


def _collect_config_snapshot(dir_path: str) -> dict:
    """收集构建配置快照。"""
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


def _run_command(cmd: str, description: str = "") -> dict:
    """运行命令并捕获输出。"""
    try:
        proc = subprocess.run(
            cmd, shell=True, capture_output=True,
            encoding="utf-8", errors="replace", timeout=60,
        )
        return {
            "command": cmd,
            "description": description,
            "exit_code": proc.returncode,
            "stdout": proc.stdout[:2048],
            "stderr": proc.stderr[:1024],
        }
    except subprocess.TimeoutExpired:
        return {"command": cmd, "description": description, "exit_code": -1, "error": "timeout"}
    except Exception as e:
        return {"command": cmd, "description": description, "exit_code": -1, "error": str(e)}


def _run_checkers(dir_path: str, platform_name: str = "freertos") -> list[dict]:
    """运行默认 checker suite 并收集结果。"""
    results = []
    cmd = f'{sys.executable} "{TOOLS_DIR / "run_review.py"}" --dir "{dir_path}" --platform {platform_name} --json'
    try:
        proc = subprocess.run(
            cmd, shell=True, capture_output=True,
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


def _collect_logs(dir_path: str) -> list[dict]:
    """收集日志文件。"""
    logs = []
    root = Path(dir_path)

    # 查找常见日志文件
    for pattern in ["*.log", "build_log*", "crash_log*", "coredump*"]:
        for p in sorted(root.glob(pattern))[:5]:
            try:
                content = p.read_text(encoding="utf-8", errors="replace")[:8192]
                logs.append({"source": str(p.relative_to(root)), "content": content})
            except Exception:
                pass

    return logs


def _parse_addr2line(output: str) -> list[dict]:
    """解析 addr2line 输出。"""
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
# 工作流收集器
# ============================================================================

WORKFLOW_CONFIGS = {
    "debug_crash": {
        "description": "Crash 调试复现包",
        "collect": ["env", "platform", "logs", "config", "checker"],
    },
    "bring_up": {
        "description": "板级 bring-up 复现包",
        "collect": ["env", "platform", "config", "checker"],
    },
    "memory": {
        "description": "内存分析复现包",
        "collect": ["env", "platform", "config", "checker"],
    },
    "project_review": {
        "description": "项目审查复现包",
        "collect": ["env", "platform", "config", "checker"],
    },
}


def collect_bundle(
    workflow: str,
    dir_path: str,
    platform_name: str = "freertos",
    *,
    log_content: str = "",
    addr2line_output: str = "",
    extra_commands: list[str] | None = None,
) -> ReproBundle:
    """收集复现包。"""
    bundle = ReproBundle(
        timestamp=datetime.now(timezone.utc).isoformat(),
        workflow=workflow,
        platform=platform_name,
    )

    config = WORKFLOW_CONFIGS.get(workflow, WORKFLOW_CONFIGS["project_review"])

    # 环境
    if "env" in config["collect"]:
        bundle.environment = _collect_environment()

    # 平台 profile
    if "platform" in config["collect"]:
        bundle.platform_profile = _collect_platform_profile(platform_name)

    # 日志
    if "logs" in config["collect"]:
        bundle.logs = _collect_logs(dir_path)
        if log_content:
            bundle.logs.append({"source": "manual_input", "content": log_content[:8192]})

    # 配置快照
    if "config" in config["collect"]:
        bundle.config_snapshot = _collect_config_snapshot(dir_path)

    # Checker 结果
    if "checker" in config["collect"]:
        bundle.checker_json = _run_checkers(dir_path, platform_name)

    # addr2line
    if addr2line_output:
        bundle.addr2line = _parse_addr2line(addr2line_output)

    # 额外命令
    if extra_commands:
        for cmd in extra_commands:
            bundle.commands.append(_run_command(cmd))

    return bundle


# ============================================================================
# 持久化
# ============================================================================

def save_bundle(bundle: ReproBundle, path: str | Path) -> Path:
    """保存复现包。"""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(bundle.to_json(), encoding="utf-8")
    return p


def save_bundle_dir(bundle: ReproBundle, dir_path: str | Path) -> Path:
    """保存复现包为目录形式。"""
    d = Path(dir_path)
    d.mkdir(parents=True, exist_ok=True)

    # 主 JSON
    (d / "repro_bundle.json").write_text(bundle.to_json(), encoding="utf-8")

    # 日志文件
    if bundle.logs:
        logs_dir = d / "logs"
        logs_dir.mkdir(exist_ok=True)
        for log in bundle.logs:
            source = log.get("source", "unknown").replace("/", "_").replace("\\", "_")
            (logs_dir / f"{source}.txt").write_text(log.get("content", ""), encoding="utf-8")

    # 配置文件
    if bundle.config_snapshot:
        config_dir = d / "config"
        config_dir.mkdir(exist_ok=True)
        for name, content in bundle.config_snapshot.items():
            safe_name = name.replace("/", "_").replace("\\", "_")
            (config_dir / safe_name).write_text(content, encoding="utf-8")

    return d


# ============================================================================
# 自测
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

    print(f"\nSelf-test: {passed} passed, {failed} failed")
    return 1 if failed > 0 else 0


# ============================================================================
# CLI
# ============================================================================

def main() -> int:
    parser = argparse.ArgumentParser(description="可复现验证包 v9.0.6")
    parser.add_argument("--workflow", choices=list(WORKFLOW_CONFIGS.keys()),
                        default="project_review", help="工作流类型")
    parser.add_argument("--dir", "-d", help="项目目录")
    parser.add_argument("--platform", "-p", default="freertos", help="平台")
    parser.add_argument("--output", "-o", help="输出文件路径（JSON）")
    parser.add_argument("--output-dir", help="输出目录路径")
    parser.add_argument("--log", help="手动提供的日志内容")
    parser.add_argument("--addr2line", help="addr2line 输出")
    parser.add_argument("--evidence", metavar="FILE", help="输出交付证据包到指定文件")
    parser.add_argument("--self-test", action="store_true", help="运行自测")
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    if not args.dir:
        parser.print_help()
        return 1

    if not Path(args.dir).is_dir():
        print(f"错误: 目录不存在: {args.dir}", file=sys.stderr)
        return 1

    bundle = collect_bundle(
        args.workflow,
        args.dir,
        args.platform,
        log_content=args.log or "",
        addr2line_output=args.addr2line or "",
    )

    # 输出
    if args.output:
        save_bundle(bundle, args.output)
        print(f"[OK] 复现包已保存: {args.output}")
    elif args.output_dir:
        save_bundle_dir(bundle, args.output_dir)
        print(f"[OK] 复现包目录已保存: {args.output_dir}")
    else:
        print(bundle.to_json())

    # 证据包
    if args.evidence:
        try:
            from evidence_schema import make_evidence, repro_command, save_evidence
        except ImportError:
            print("[warn] evidence_schema 模块不可用（已归档），跳过证据包输出", file=sys.stderr)
            return 0

        ev = make_evidence(
            source_tool="repro_bundle",
            platform=args.platform,
            reproduce_commands=[
                repro_command(
                    f"python tools/repro_bundle.py --workflow {args.workflow} --dir {args.dir} --platform {args.platform}",
                    "复现验证包",
                ),
            ],
            assumptions=[
                f"工作流: {args.workflow}",
                f"平台: {args.platform}",
                f"Checker 结果: {len(bundle.checker_json)} 个",
            ],
            metadata={
                "tool_version": "9.0.6",
                "workflow": args.workflow,
                "log_count": len(bundle.logs),
                "config_keys": list(bundle.config_snapshot.keys()),
            },
        )
        save_evidence(ev, args.evidence)
        print(f"[evidence] 已保存交付证据包: {args.evidence}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
