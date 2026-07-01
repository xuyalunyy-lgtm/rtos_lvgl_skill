#!/usr/bin/env python3
"""
永久等待 / 超时预算启发式扫描器。

检查项:
  C31.1 — WAIT_FOREVER / BEKEN_WAIT_FOREVER / portMAX_DELAY 使用
  C31.2 — 无 timeout 的网络/TLS/IO 阻塞 API
  C31.3 — 无 timeout 的 mutex/semaphore/queue API
  C31.4 — 永久等待例外须人工确认

用法:
    python tools/blocking_wait_checker.py <file.c> [file2.c ...]
    python tools/blocking_wait_checker.py --dir src/
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Permanent wait constants
PERMANENT_WAIT_CONSTANTS = [
    "WAIT_FOREVER",
    "BEKEN_WAIT_FOREVER",
    "portMAX_DELAY",
    "OS_WAIT_FOREVER",
    "RTOS_WAIT_FOREVER",
    "0xFFFFFFFF",
    "0xffffffff",
]

# RTOS blocking APIs that normally carry an explicit timeout argument.
SYNC_API_PATTERNS = [
    re.compile(r"\brtos_get_semaphore\s*\("),
    re.compile(r"\brtos_lock_mutex\s*\("),
    re.compile(r"\brtos_get_queue\s*\("),
    re.compile(r"\bxSemaphoreTake\s*\("),
    re.compile(r"\bxQueueReceive\s*\("),
    re.compile(r"\bxQueueSend\s*\("),
]

# Network/TLS APIs whose timeout/deadline is usually configured outside the call.
NETWORK_API_PATTERNS = [
    re.compile(r"\bmbedtls_ssl_read\s*\("),
    re.compile(r"\bmbedtls_ssl_write\s*\("),
    re.compile(r"\bmbedtls_ssl_handshake\s*\("),
    re.compile(r"\brecv\s*\("),
    re.compile(r"\bsend\s*\("),
    re.compile(r"\bconnect\s*\("),
]

TIMEOUT_ARGUMENT_RE = re.compile(
    r",\s*(?:pdMS_TO_TICKS\s*\([^)]*\)|[A-Z][A-Z0-9_]*|\d+)\s*\)"
)

NETWORK_TIMEOUT_HINTS = (
    "timeout_ms",
    "deadline_ms",
    "recv_timeout",
    "send_timeout",
    "read_timeout",
    "select(",
    "poll(",
    "SO_RCVTIMEO",
    "SO_SNDTIMEO",
    "setsockopt",
    "O_NONBLOCK",
    "FIONBIO",
    "nonblock",
    "mbedtls_ssl_conf_read_timeout",
    "mbedtls_net_set_nonblock",
)


def check_permanent_wait(path: Path, lines: list[str]) -> list[dict]:
    """扫描永久等待常量使用"""
    issues = []

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("/*"):
            continue

        for constant in PERMANENT_WAIT_CONSTANTS:
            if constant in stripped:
                # Find the function context
                func_context = ""
                for j in range(max(0, i - 10), i):
                    if re.search(r"static\s+\w+\s+\w+\s*\(|void\s+\w+\s*\(", lines[j]):
                        func_context = lines[j].strip()
                        break

                issues.append({
                    "id": "C31.1",
                    "severity": "P0",
                    "file": f"{path}:{i}",
                    "line": stripped[:80],
                    "context": func_context[:60] if func_context else "",
                    "type": "permanent_wait_constant",
                })

    return issues


def check_blocking_api_without_timeout(path: Path, lines: list[str]) -> list[dict]:
    """扫描无 timeout 的阻塞 API"""
    issues = []

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("/*"):
            continue

        for api_pattern in SYNC_API_PATTERNS:
            if not api_pattern.search(stripped):
                continue

            if not has_sync_timeout(stripped):
                # Find function context
                func_context = ""
                for j in range(max(0, i - 10), i):
                    if re.search(r"(?:static\s+)?(?:void|int|esp_err_t|bool)\s+\w+\s*\(", lines[j]):
                        func_context = lines[j].strip()
                        break

                issues.append({
                    "id": "C31.3",
                    "severity": "P1",
                    "file": f"{path}:{i}",
                    "line": stripped[:80],
                    "context": func_context[:60] if func_context else "",
                    "type": "blocking_api_no_timeout",
                })

        for api_pattern in NETWORK_API_PATTERNS:
            if not api_pattern.search(stripped):
                continue

            if not has_network_timeout_hint(lines, i):
                func_context = ""
                for j in range(max(0, i - 10), i):
                    if re.search(r"(?:static\s+)?(?:void|int|esp_err_t|bool|ssize_t)\s+\w+\s*\(", lines[j]):
                        func_context = lines[j].strip()
                        break

                issues.append({
                    "id": "C31.2",
                    "severity": "P0",
                    "file": f"{path}:{i}",
                    "line": stripped[:80],
                    "context": func_context[:60] if func_context else "",
                    "type": "blocking_api_no_timeout",
                })

    return issues


def has_sync_timeout(line: str) -> bool:
    """Return True when an RTOS wait call has an explicit final timeout argument."""
    if any(c in line for c in PERMANENT_WAIT_CONSTANTS):
        return True
    if "pdMS_TO_TICKS" in line:
        return True
    return bool(TIMEOUT_ARGUMENT_RE.search(line))


def has_network_timeout_hint(lines: list[str], line_no: int) -> bool:
    """Network calls need nearby deadline/nonblocking/socket-timeout evidence."""
    start = max(0, line_no - 8)
    end = min(len(lines), line_no + 3)
    window = "\n".join(lines[start:end])
    return any(hint in window for hint in NETWORK_TIMEOUT_HINTS)


def check_file(path: Path) -> list[dict]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    lines = text.splitlines()
    issues = []
    issues.extend(check_permanent_wait(path, lines))
    issues.extend(check_blocking_api_without_timeout(path, lines))
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="永久等待扫描器")
    parser.add_argument("files", nargs="*", help="待检查 .c 文件")
    parser.add_argument("--dir", "-d", help="递归检查目录")
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式")
    args = parser.parse_args()

    targets: list[Path] = []
    for f in args.files:
        p = Path(f)
        if p.is_file():
            targets.append(p)
        elif p.is_dir():
            targets.extend(sorted(p.rglob("*.c")))

    if args.dir:
        d = Path(args.dir)
        if d.is_dir():
            targets.extend(sorted(d.rglob("*.c")))

    seen: set[Path] = set()
    unique: list[Path] = []
    for t in targets:
        r = t.resolve()
        if r not in seen:
            seen.add(r)
            unique.append(r)

    if not unique:
        print("[blocking_wait_checker] 无文件可检查")
        return 0

    all_issues: list[dict] = []
    for path in unique:
        all_issues.extend(check_file(path))

    if args.json:
        import json
        print(json.dumps(all_issues, indent=2, ensure_ascii=False))
        return 0

    if not all_issues:
        print(f"[blocking_wait_checker] 已检查 {len(unique)} 个文件，未发现 C31 超时预算违规")
        return 0

    # Group by type
    permanent_waits = [i for i in all_issues if i["type"] == "permanent_wait_constant"]
    no_timeout = [i for i in all_issues if i["type"] == "blocking_api_no_timeout"]

    print(f"[blocking_wait_checker] 已检查 {len(unique)} 个文件，发现 {len(all_issues)} 个阻塞等待:\n")

    if permanent_waits:
        print(f"=== 永久等待常量 ({len(permanent_waits)} 处) ===")
        print("请确认这些位置是否允许永久等待：\n")
        for issue in permanent_waits:
            print(f"  [{issue['severity']}] {issue['id']} — {issue['file']}")
            if issue['context']:
                print(f"    函数: {issue['context']}")
            print(f"    代码: {issue['line']}")
            print()

    if no_timeout:
        print(f"=== 阻塞 API 无显式超时 ({len(no_timeout)} 处) ===")
        print("请确认这些 API 调用是否有隐式超时或允许永久等待：\n")
        for issue in no_timeout:
            print(f"  [{issue['severity']}] {issue['id']} — {issue['file']}")
            if issue['context']:
                print(f"    函数: {issue['context']}")
            print(f"    代码: {issue['line']}")
            print()

    print(f"Summary: {len(permanent_waits)} permanent waits, {len(no_timeout)} blocking APIs without explicit timeout")
    return 1


if __name__ == "__main__":
    sys.exit(main())
