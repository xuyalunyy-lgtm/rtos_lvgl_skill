#!/usr/bin/env python3
"""
C22 OTA 安全启发式检查器。

检查项:
  C22.1 — OTA 固件镜像必须有签名验证
  C22.2 — OTA 升级必须支持回滚（mark_valid_cancel_rollback）
  C22.5 — OTA 下载必须有超时和重试上限

用法:
    python tools/ota_safety_checker.py <file.c> [file2.c ...]
    python tools/ota_safety_checker.py --dir src/
"""

from __future__ import annotations

import re
from pathlib import Path

from checker_io import make_issue, read_file, run_checker, strip_comments_lines
from sdk_lookup import SdkLookup

lookup = SdkLookup("esp32")

OTA_WRITE_APIS = lookup.get_all_apis("OTA_WRITE", "OTA_BEGIN")
OTA_FINISH_APIS = lookup.get_all_apis("OTA_END")
OTA_MARK_VALID = lookup.get_all_apis("OTA_MARK_VALID", "OTA_ROLLBACK")
OTA_VERIFY = []  # TODO: add OTA_VERIFY to sdk_abstraction.yaml when verification ops are registered


def check_file(path: Path) -> list[dict]:
    result = read_file(path)
    if result is None:
        return []

    lines, text = result
    lower = text.lower()
    if "ota" not in lower and "esp_ota" not in lower:
        return []

    clean = strip_comments_lines(text)
    issues = []

    # C22.1: Signature verification
    has_ota_write = any(api + "(" in l for l in clean for api in OTA_WRITE_APIS)
    has_verify = any(api + "(" in l for l in clean for api in OTA_VERIFY)
    has_secure_boot = any("CONFIG_SECURE_BOOT" in l and ("y" in l or "enabled" in l.lower()) for l in clean)

    if has_ota_write and not has_verify and not has_secure_boot:
        issues.append(make_issue(path, 1, "C22.1", "P0",
            "OTA write without signature verification"))

    # C22.2: Rollback support
    has_set_boot = any(api + "(" in l for l in clean for api in OTA_FINISH_APIS)
    has_mark_valid = any(api + "(" in l for l in clean for api in OTA_MARK_VALID)

    if has_set_boot and not has_mark_valid:
        issues.append(make_issue(path, 1, "C22.2", "P0",
            "OTA set_boot_partition without mark_valid_cancel_rollback"))

    # C22.5: Timeout
    for i, line in enumerate(clean, 1):
        stripped = line.strip()
        if "esp_http_client_open" in stripped:
            has_timeout = any(
                kw in lines[j]
                for j in range(max(0, i - 20), min(len(lines), i + 5))
                for kw in ["timeout_ms", "timeout_sec", "TIMEOUT", "connect_timeout"]
            )
            if not has_timeout:
                issues.append(make_issue(path, i, "C22.5", "P1",
                    "esp_http_client_open without timeout config"))

    # C22.5: Retry limit
    has_retry_loop = any("retry" in l.lower() and ("while" in l or "for" in l) for l in clean)
    has_retry_limit = any(kw in l for l in clean for kw in ["max_retry", "MAX_RETRY", "retry_count <="])

    if has_retry_loop and not has_retry_limit:
        issues.append(make_issue(path, 1, "C22.5", "P1",
            "OTA retry loop without upper bound"))

    return issues


if __name__ == "__main__":
    raise SystemExit(run_checker(check_file, "C22 OTA 安全检查器", ("C22",)))
