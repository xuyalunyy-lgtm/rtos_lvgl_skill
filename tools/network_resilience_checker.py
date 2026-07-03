#!/usr/bin/env python3
"""
C20 网络韧性启发式检查器。

检查项:
  C20.1 — WiFi/WSS 断线重连必须有指数退避
  C20.2 — 所有阻塞网络操作必须有有限超时（禁 portMAX_DELAY）

用法:
    python tools/network_resilience_checker.py <file.c> [file2.c ...]
    python tools/network_resilience_checker.py --dir src/
"""

from __future__ import annotations

import re
from pathlib import Path

from checker_io import make_issue, read_file, run_checker
from sdk_lookup import SdkLookup

lookup = SdkLookup("esp32")

# Network APIs that MUST have timeout — use word boundary to avoid matching variable names
BLOCKING_NET_API_PATTERNS = [
    re.compile(r"\b" + re.escape(api) + r"\s*\(")
    for api in lookup.get_all_apis("SOCKET_RECV", "SOCKET_SEND", "SOCKET_CONNECT",
                                   "SOCKET_ACCEPT", "TLS_READ", "TLS_WRITE", "TLS_HANDSHAKE")
]

# Reconnect patterns (SDK-level WiFi connect + application-level reconnect APIs)
_wifi_connect_apis = lookup.get_apis("WIFI_CONNECT")
RECONNECT_PATTERNS = [
    re.compile(r"\b" + re.escape(api) + r"\s*\(\s*\)")
    for api in _wifi_connect_apis
] + [
    re.compile(r"\bwss_connect\s*\("),
    re.compile(r"\bwifi_connect\s*\("),
    re.compile(r"\bmqtt_reconnect\s*\("),
    re.compile(r"\breconnect\s*\("),
]

# Backoff indicators
BACKOFF_INDICATORS = [
    "backoff",
    "retry_delay",
    "retry_ms",
    "delay_ms",
    "vTaskDelay",
    "pdMS_TO_TICKS",
    "1 <<",
    "2 <<",
    "delay *",
    "* 2",
    "RECONNECT_MAX",
    "RECONNECT_BASE",
]


def check_reconnect_backoff(path: Path, lines: list[str]) -> list[dict]:
    """C20.1 — 重连必须有指数退避"""
    issues = []
    in_function = False
    brace_depth = 0
    func_start_line = 0
    func_name = ""
    has_reconnect = False
    has_backoff = False

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("/*"):
            continue

        # Detect function start
        func_match = re.search(r"(?:static\s+)?(?:void|int|esp_err_t)\s+(\w+)\s*\(", stripped)
        if func_match and "{" in stripped:
            in_function = True
            brace_depth = stripped.count("{") - stripped.count("}")
            func_start_line = i
            func_name = func_match.group(1)
            has_reconnect = False
            has_backoff = False
        elif in_function:
            brace_depth += stripped.count("{") - stripped.count("}")

            # Check for reconnect call
            if any(p.search(stripped) for p in RECONNECT_PATTERNS):
                has_reconnect = True

            # Check for backoff indicator
            if any(indicator in stripped.lower() for indicator in BACKOFF_INDICATORS):
                has_backoff = True

            # Function end
            if brace_depth <= 0:
                if has_reconnect and not has_backoff:
                    issues.append(make_issue(
                        path, func_start_line, "C20.1", "P0",
                        f"函数 {func_name} 有重连逻辑但未见指数退避（应有 1s→2s→…→60s cap）",
                    ))
                in_function = False

    return issues


def check_network_timeout(path: Path, lines: list[str]) -> list[dict]:
    """C20.2 — 阻塞网络操作必须有有限超时"""
    issues = []

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("/*"):
            continue

        # Check for blocking API calls
        for api_pattern in BLOCKING_NET_API_PATTERNS:
            if not api_pattern.search(stripped):
                continue

            # Check for portMAX_DELAY (explicit permanent wait)
            if "portMAX_DELAY" in stripped:
                issues.append(make_issue(
                    path, i, "C20.2", "P0",
                    "阻塞网络 API 使用 portMAX_DELAY 无超时",
                ))
                continue

            # Check for socket timeout set nearby (SO_RCVTIMEO / SO_SNDTIMEO)
            has_socket_timeout = False
            for j in range(max(0, i - 15), i):
                prev_line = lines[j]
                if "SO_RCVTIMEO" in prev_line or "SO_SNDTIMEO" in prev_line:
                    has_socket_timeout = True
                    break

            if has_socket_timeout:
                continue

            # Check if timeout is explicitly 0 (non-blocking is OK)
            if re.search(r",\s*0\s*\)", stripped):
                continue

            # Check for numeric timeout or constant timeout
            # Pattern: last arg before ) is a number or constant
            has_timeout = False
            # Check for numeric value as last arg
            if re.search(r",\s*\d+\s*\)", stripped):
                has_timeout = True
            # Check for constant as last arg (e.g., TIMEOUT_MS)
            elif re.search(r",\s*[A-Z_]{3,}\s*\)", stripped):
                has_timeout = True
            # Check for pdMS_TO_TICKS
            elif "pdMS_TO_TICKS" in stripped:
                has_timeout = True
            # Check for sizeof (non-blocking size check)
            elif "sizeof" in stripped:
                has_timeout = True

            if not has_timeout:
                issues.append(make_issue(
                    path, i, "C20.2", "P1",
                    "阻塞网络 API 未见显式超时参数",
                ))

    return issues


def check_file(path: Path) -> list[dict]:
    result = read_file(path)
    if result is None:
        return []

    lines, _text = result
    issues = []
    issues.extend(check_reconnect_backoff(path, lines))
    issues.extend(check_network_timeout(path, lines))
    return issues


if __name__ == "__main__":
    raise SystemExit(run_checker(check_file, "C20 网络韧性检查器", ("C20",)))
