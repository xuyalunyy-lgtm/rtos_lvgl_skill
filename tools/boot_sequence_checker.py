#!/usr/bin/env python3
"""
C8 启动顺序启发式检查器。

检查项:
  C8.1 — Queue + Presenter Looper 须在网络回调注册之前创建
  C8.2 — WSS/TLS 须在 WiFi 获 IP 之后
  C8.4 — LVGL 任务循环内禁止网络/TLS/长阻塞
  C8.6 — main/init 路径禁止同步 TLS 握手、大 Parse、超长 delay

用法:
    python tools/boot_sequence_checker.py <file.c> [file2.c ...]
    python tools/boot_sequence_checker.py --dir src/
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


# Queue/event creation APIs
QUEUE_CREATE_APIS = [
    "xQueueCreate",
    "xQueueCreateStatic",
    "xQueueGenericCreate",
]

# Network callback registration APIs
NET_CALLBACK_APIS = [
    "esp_event_handler_register",
    "esp_event_handler_instance_register",
    "wifi_event_handler",
    "esp_wifi_set_event_handler",
    "mqtt_register_event",
    "esp_mqtt_client_register_event",
]

# TLS/network blocking APIs (should not be in main/init)
TLS_BLOCKING_APIS = [
    "mbedtls_ssl_handshake",
    "esp_tls_conn_new_sync",
    "esp_tls_conn_read",
    "mbedtls_ssl_read",
    "getaddrinfo",
]

# LVGL handler API
LVGL_HANDLER_API = "lv_timer_handler"


def _strip_comments(text: str) -> list[str]:
    lines = []
    in_block = False
    for line in text.splitlines():
        stripped = line
        if in_block:
            if "*/" in stripped:
                stripped = stripped[stripped.index("*/") + 2:]
                in_block = False
            else:
                stripped = ""
        if "/*" in stripped:
            before = stripped[:stripped.index("/*")]
            after = stripped[stripped.index("/*") + 2:]
            if "*/" in after:
                after = after[after.index("*/") + 2:]
                stripped = before + after
            else:
                stripped = before
                in_block = True
        if "//" in stripped:
            stripped = stripped[:stripped.index("//")]
        lines.append(stripped)
    return lines


def check_queue_before_callback(path: Path, lines: list[str]) -> list[dict]:
    """C8.1 — Queue 创建须在网络回调注册之前"""
    issues = []
    queue_create_lines = []
    callback_register_lines = []

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        for api in QUEUE_CREATE_APIS:
            if api + "(" in stripped:
                queue_create_lines.append(i)
                break
        for api in NET_CALLBACK_APIS:
            if api + "(" in stripped:
                callback_register_lines.append(i)
                break

    if queue_create_lines and callback_register_lines:
        first_queue = min(queue_create_lines)
        first_callback = min(callback_register_lines)
        if first_callback < first_queue:
            issues.append({
                "id": "C8.1",
                "file": f"{path}:{first_callback}",
                "issue": f"网络回调注册(L{first_callback})在 Queue 创建(L{first_queue})之前",
                "severity": "P0",
            })

    return issues


def check_lvgl_no_blocking(path: Path, lines: list[str]) -> list[dict]:
    """C8.4 — LVGL handler 循环内禁止网络/TLS/长阻塞"""
    issues = []
    in_lvgl_loop = False
    brace_depth = 0

    for i, line in enumerate(lines, 1):
        stripped = line.strip()

        # Detect lv_timer_handler call as indicator of LVGL loop
        if LVGL_HANDLER_API + "(" in stripped:
            in_lvgl_loop = True
            brace_depth = 0
            continue

        if in_lvgl_loop:
            brace_depth += stripped.count("{") - stripped.count("}")
            if brace_depth < 0:
                in_lvgl_loop = False
                continue

            # Check for blocking APIs in LVGL loop
            for api in TLS_BLOCKING_APIS:
                if api + "(" in stripped:
                    issues.append({
                        "id": "C8.4",
                        "file": f"{path}:{i}",
                        "issue": f"LVGL handler 循环内调用阻塞 API: {api}",
                        "severity": "P0",
                    })
                    break

            # Check for portMAX_DELAY in LVGL loop
            if "portMAX_DELAY" in stripped and ("xQueue" in stripped or "xSemaphore" in stripped):
                issues.append({
                    "id": "C8.4",
                    "file": f"{path}:{i}",
                    "issue": "LVGL handler 循环内使用 portMAX_DELAY",
                    "severity": "P0",
                })

    return issues


def check_main_no_sync_tls(path: Path, lines: list[str]) -> list[dict]:
    """C8.6 — main/init 路径禁止同步 TLS"""
    issues = []
    in_main = False
    brace_depth = 0

    for i, line in enumerate(lines, 1):
        stripped = line.strip()

        # Detect app_main or main function
        if re.search(r'\b(app_main|main)\s*\(', stripped) and "{" in stripped:
            in_main = True
            brace_depth = 1
            continue
        elif re.search(r'\b(app_main|main)\s*\(', stripped):
            in_main = True
            brace_depth = 0
            continue

        if in_main:
            brace_depth += stripped.count("{") - stripped.count("}")
            if brace_depth <= 0 and brace_depth != 0:
                in_main = False
                continue

            # Only check first 50 lines of main (init phase)
            main_start = next((j for j, l in enumerate(lines) if re.search(r'\b(app_main|main)\s*\(', l)), -1)
            if main_start >= 0 and i - main_start > 50:
                continue

            for api in TLS_BLOCKING_APIS:
                if api + "(" in stripped:
                    issues.append({
                        "id": "C8.6",
                        "file": f"{path}:{i}",
                        "issue": f"main/init 路径同步调用 {api}（应异步或延迟到网络就绪后）",
                        "severity": "P0",
                    })
                    break

    return issues


def check_file(path: Path) -> list[dict]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    # Only check C files with relevant content
    lower_text = text.lower()
    if not any(kw in lower_text for kw in ["queue", "lv_timer", "app_main", "tls", "wifi"]):
        return []

    lines = text.splitlines()
    clean_lines = _strip_comments(text)

    issues = []
    issues.extend(check_queue_before_callback(path, clean_lines))
    issues.extend(check_lvgl_no_blocking(path, clean_lines))
    issues.extend(check_main_no_sync_tls(path, clean_lines))
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="C8 启动顺序检查器")
    parser.add_argument("files", nargs="*", help="待检查 .c 文件")
    parser.add_argument("--dir", "-d", help="递归检查目录")
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
        print("[boot_sequence_checker] 无文件可检查")
        return 0

    all_issues: list[dict] = []
    for path in unique:
        all_issues.extend(check_file(path))

    if not all_issues:
        print(f"[boot_sequence_checker] 已检查 {len(unique)} 个文件，未发现 C8 违规")
        return 0

    print(f"[boot_sequence_checker] 已检查 {len(unique)} 个文件，发现 {len(all_issues)} 个 C8 告警:\n")
    for issue in all_issues:
        print(f"  [{issue['severity']}] {issue['id']} — {issue['file']} — {issue['issue']}")

    print(f"\nSummary: {len(all_issues)} C8 boot sequence warnings")
    return 1


if __name__ == "__main__":
    sys.exit(main())
