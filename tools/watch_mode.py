#!/usr/bin/env python3
"""
实时检查模式 — 文件变更时自动运行增量 checker。

功能：
  1. 监控 .c/.h 文件变更
  2. 自动运行相关 checker
  3. 输出到终端（可集成到 IDE）

用法:
    python tools/watch_mode.py --dir src/
    python tools/watch_mode.py --dir src/ --checker cjson_leak
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

# Force UTF-8 output on Windows
if sys.platform == "win32":
    os.environ.setdefault("PYTHONUTF8", "1")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")


def get_file_mtimes(directory: Path) -> dict[Path, float]:
    """获取目录下所有 .c/.h 文件的修改时间"""
    mtimes = {}
    for ext in ("*.c", "*.h"):
        for f in directory.rglob(ext):
            try:
                mtimes[f] = f.stat().st_mtime
            except OSError:
                pass
    return mtimes


def run_checker_on_file(checker: str, filepath: Path) -> str:
    """对单个文件运行 checker"""
    tools_dir = Path(__file__).parent
    checker_path = tools_dir / f"{checker}.py"

    if not checker_path.exists():
        return ""

    try:
        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        result = subprocess.run(
            [sys.executable, str(checker_path), str(filepath)],
            capture_output=True, text=True, timeout=30, env=env,
            encoding="utf-8", errors="replace"
        )
        return result.stdout + result.stderr
    except Exception:
        return ""


def watch_directory(directory: Path, checkers: list[str], interval: float = 2.0):
    """监控目录，文件变更时运行 checker"""
    print(f"[watch_mode] Watching {directory} for changes...")
    print(f"[watch_mode] Checkers: {', '.join(checkers)}")
    print(f"[watch_mode] Polling interval: {interval}s")
    print(f"[watch_mode] Press Ctrl+C to stop\n")

    last_mtimes = get_file_mtimes(directory)

    try:
        while True:
            time.sleep(interval)
            current_mtimes = get_file_mtimes(directory)

            # Find changed files
            changed = []
            for filepath, mtime in current_mtimes.items():
                if filepath not in last_mtimes or last_mtimes[filepath] != mtime:
                    changed.append(filepath)

            if not changed:
                continue

            print(f"[watch_mode] {len(changed)} file(s) changed")

            for filepath in changed:
                print(f"\n--- {filepath} ---")
                for checker in checkers:
                    output = run_checker_on_file(checker, filepath)
                    if output and "no " not in output.lower() and "未发现" not in output:
                        print(output)

            last_mtimes = current_mtimes

    except KeyboardInterrupt:
        print("\n[watch_mode] Stopped")


def _checkers_from_registry(suite: str) -> list[str]:
    """从 checker_registry 获取 checker name 列表。"""
    from checker_registry import get_suite
    return [spec.name for spec in get_suite(suite)]


def _checkers_for_domain(domain: str) -> list[str]:
    """从 checker_registry 获取指定域的 checker。"""
    from checker_registry import ALL_CHECKERS
    return [spec.name for spec in ALL_CHECKERS if domain in spec.domains]


def main() -> int:
    parser = argparse.ArgumentParser(description="实时检查模式")
    parser.add_argument("--dir", "-d", required=True, help="监控目录")
    parser.add_argument("--checker", "-c", action="append", help="指定 checker name（可多次）")
    parser.add_argument("--suite", default="default",
                        choices=["default", "all", "security", "media", "platform", "realtime"],
                        help="checker suite (default: default)")
    parser.add_argument("--domain", help="按约束域筛选 checker（如 C3, C22）")
    parser.add_argument("--interval", type=float, default=2.0, help="轮询间隔（秒）")
    args = parser.parse_args()

    directory = Path(args.dir)
    if not directory.is_dir():
        print(f"Error: {directory} is not a directory")
        return 1

    if args.checker:
        checkers = args.checker
    elif args.domain:
        checkers = _checkers_for_domain(args.domain)
    else:
        checkers = _checkers_from_registry(args.suite)

    watch_directory(directory, checkers, args.interval)
    return 0


if __name__ == "__main__":
    sys.exit(main())
