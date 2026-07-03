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

import re
from pathlib import Path

from checker_io import make_issue, read_file, run_checker
from sdk_lookup import SdkLookup

lookup = SdkLookup("esp32")

# Permanent wait constants
PERMANENT_WAIT_CONSTANTS = [
    lookup.get_timeout_infinite(),
    "0xFFFFFFFF",
    "0xffffffff",
]

# RTOS blocking APIs that normally carry an explicit timeout argument.
SYNC_API_PATTERNS = [lookup.build_regex("SEM_TAKE", "MUTEX_LOCK", "QUEUE_RECV", "QUEUE_SEND")]

# Network/TLS APIs whose timeout/deadline is usually configured outside the call.
NETWORK_API_PATTERNS = [lookup.build_regex("TLS_READ", "TLS_WRITE", "TLS_HANDSHAKE",
                                           "SOCKET_RECV", "SOCKET_SEND", "SOCKET_CONNECT")]

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

                msg = stripped[:80]
                if func_context:
                    msg += f" (in {func_context[:60]})"
                issues.append(make_issue(path, i, "C31.1", "P0", msg))

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

                msg = stripped[:80]
                if func_context:
                    msg += f" (in {func_context[:60]})"
                issues.append(make_issue(path, i, "C31.3", "P1", msg))

        for api_pattern in NETWORK_API_PATTERNS:
            if not api_pattern.search(stripped):
                continue

            if not has_network_timeout_hint(lines, i):
                func_context = ""
                for j in range(max(0, i - 10), i):
                    if re.search(r"(?:static\s+)?(?:void|int|esp_err_t|bool|ssize_t)\s+\w+\s*\(", lines[j]):
                        func_context = lines[j].strip()
                        break

                msg = stripped[:80]
                if func_context:
                    msg += f" (in {func_context[:60]})"
                issues.append(make_issue(path, i, "C31.2", "P0", msg))

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
    result = read_file(path)
    if result is None:
        return []

    lines, text = result
    issues = []
    issues.extend(check_permanent_wait(path, lines))
    issues.extend(check_blocking_api_without_timeout(path, lines))
    return issues


if __name__ == "__main__":
    raise SystemExit(run_checker(check_file, "永久等待扫描器", ("C31",)))
