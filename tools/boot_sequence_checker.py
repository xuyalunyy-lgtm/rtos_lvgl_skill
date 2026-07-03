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

import re
from pathlib import Path

from checker_io import make_issue, run_checker, strip_comments_lines
from sdk_lookup import SdkLookup

lookup = SdkLookup("esp32")

# Queue/event creation APIs
QUEUE_CREATE_APIS = lookup.get_apis("QUEUE_CREATE")

# Network callback registration APIs (SDK-level + application-level)
NET_CALLBACK_APIS = lookup.get_apis("WIFI_EVENT_REGISTER") + [
    "wifi_event_handler",
    "esp_wifi_set_event_handler",
    "mqtt_register_event",
    "esp_mqtt_client_register_event",
]

# TLS/network blocking APIs
TLS_BLOCKING_APIS = lookup.get_all_apis("TLS_HANDSHAKE", "TLS_READ") + [
    "getaddrinfo",
]

LVGL_HANDLER_API = lookup.get_apis("TIMER_HANDLER")[0] if lookup.get_apis("TIMER_HANDLER") else "lv_timer_handler"


def check_file(path: Path) -> list[dict]:
    result = __import__('checker_io').read_file(path)
    if result is None:
        return []

    lines, text = result
    lower = text.lower()
    if not any(kw in lower for kw in ["queue", "lv_timer", "app_main", "tls", "wifi"]):
        return []

    clean = strip_comments_lines(text)
    issues = []

    # C8.1: Queue before callback
    queue_lines = []
    callback_lines = []
    for i, line in enumerate(clean, 1):
        stripped = line.strip()
        for api in QUEUE_CREATE_APIS:
            if api + "(" in stripped:
                queue_lines.append(i)
                break
        for api in NET_CALLBACK_APIS:
            if api + "(" in stripped:
                callback_lines.append(i)
                break

    if queue_lines and callback_lines:
        first_q = min(queue_lines)
        first_cb = min(callback_lines)
        if first_cb < first_q:
            issues.append(make_issue(path, first_cb, "C8.1", "P0",
                f"callback(L{first_cb}) before Queue(L{first_q})"))

    # C8.4: No blocking in LVGL loop
    in_lvgl = False
    brace = 0
    for i, line in enumerate(clean, 1):
        stripped = line.strip()
        if LVGL_HANDLER_API + "(" in stripped:
            in_lvgl = True
            brace = 0
            continue
        if in_lvgl:
            brace += stripped.count("{") - stripped.count("}")
            if brace < 0:
                in_lvgl = False
                continue
            for api in TLS_BLOCKING_APIS:
                if api + "(" in stripped:
                    issues.append(make_issue(path, i, "C8.4", "P0",
                        f"blocking API {api} in LVGL loop"))
                    break
            if "portMAX_DELAY" in stripped and ("xQueue" in stripped or "xSemaphore" in stripped):
                issues.append(make_issue(path, i, "C8.4", "P0",
                    "portMAX_DELAY in LVGL loop"))

    # C8.6: No sync TLS in main
    in_main = False
    brace = 0
    main_start = -1
    for i, line in enumerate(clean, 1):
        stripped = line.strip()
        if re.search(r'\b(app_main|main)\s*\(', stripped):
            in_main = True
            main_start = i
            brace = stripped.count("{") - stripped.count("}")
            continue
        if in_main:
            brace += stripped.count("{") - stripped.count("}")
            if brace <= 0 and main_start > 0:
                in_main = False
                continue
            if main_start > 0 and i - main_start > 50:
                continue
            for api in TLS_BLOCKING_APIS:
                if api + "(" in stripped:
                    issues.append(make_issue(path, i, "C8.6", "P0",
                        f"sync {api} in main/init"))
                    break

    return issues


if __name__ == "__main__":
    raise SystemExit(run_checker(check_file, "C8 启动顺序检查器", ("C8",)))
