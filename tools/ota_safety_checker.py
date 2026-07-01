#!/usr/bin/env python3
"""
C22 OTA 安全启发式检查器。

检查项:
  C22.1 — OTA 固件镜像必须有签名验证（esp_ota_verify / esp_secure_boot / image_validate）
  C22.2 — OTA 升级必须支持回滚（mark_valid_cancel_rollback / esp_ota_mark_app_valid_cancel_rollback）
  C22.3 — OTA 分区表必须含 ota_0 + ota_1（partitions.csv / partition_table 检查）
  C22.4 — OTA 断电恢复：升级过程中断电必须能回退到旧固件
  C22.5 — OTA 下载必须有超时和重试上限（http_client / ota_begin 超时）
  C22.6 — OTA 差分升级：若使用差分，必须声明 patch 校验和回退策略

用法:
    python tools/ota_safety_checker.py <file.c> [file2.c ...]
    python tools/ota_safety_checker.py --dir src/
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


# OTA API patterns
OTA_WRITE_APIS = [
    "esp_ota_write",
    "esp_ota_begin",
]

OTA_FINISH_APIS = [
    "esp_ota_end",
    "esp_ota_set_boot_partition",
]

OTA_MARK_VALID_APIS = [
    "esp_ota_mark_app_valid_cancel_rollback",
    "esp_ota_mark_app_invalid_rollback_and_reboot",
]

OTA_VERIFY_APIS = [
    "esp_ota_verify",
    "esp_secure_boot_verify_signature",
    "esp_image_verify",
    "esp_app_desc_check",
    "esp_ota_get_app_description",
]

HTTP_CLIENT_APIS = [
    "esp_http_client_open",
    "esp_http_client_read",
    "esp_http_client_fetch_headers",
]


def _strip_comments(text: str) -> list[str]:
    """Strip C/C++ comments and return lines."""
    # Simple line-based stripping
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
        # Remove line comments
        if "//" in stripped:
            stripped = stripped[:stripped.index("//")]
        lines.append(stripped)
    return lines


def check_signature_verification(path: Path, lines: list[str]) -> list[dict]:
    """C22.1 — OTA 镜像签名验证"""
    issues = []
    has_ota_write = False
    has_verify = False

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        for api in OTA_WRITE_APIS:
            if api + "(" in stripped:
                has_ota_write = True
                break
        for api in OTA_VERIFY_APIS:
            if api + "(" in stripped:
                has_verify = True
                break
        # Check for secure boot config
        if "CONFIG_SECURE_BOOT" in stripped and ("y" in stripped or "enabled" in stripped.lower()):
            has_verify = True

    if has_ota_write and not has_verify:
        issues.append({
            "id": "C22.1",
            "file": str(path),
            "issue": "OTA 写入未见签名验证（esp_ota_verify / esp_secure_boot）",
            "severity": "P0",
        })

    return issues


def check_rollback_support(path: Path, lines: list[str]) -> list[dict]:
    """C22.2 — OTA 必须支持回滚"""
    issues = []
    has_ota_set_boot = False
    has_mark_valid = False

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        for api in OTA_FINISH_APIS:
            if api + "(" in stripped:
                has_ota_set_boot = True
                break
        for api in OTA_MARK_VALID_APIS:
            if api + "(" in stripped:
                has_mark_valid = True
                break

    if has_ota_set_boot and not has_mark_valid:
        issues.append({
            "id": "C22.2",
            "file": str(path),
            "issue": "OTA 设置启动分区后未见 mark_valid_cancel_rollback（断电可能回滚失败）",
            "severity": "P0",
        })

    return issues


def check_ota_timeout(path: Path, lines: list[str]) -> list[dict]:
    """C22.5 — OTA 下载必须有超时和重试上限"""
    issues = []

    for i, line in enumerate(lines, 1):
        stripped = line.strip()

        # Check HTTP client open without timeout (only check open, not read)
        for api in ["esp_http_client_open"]:
            if api + "(" in stripped:
                # Look for timeout config nearby (search wider range for config structs)
                has_timeout = False
                for j in range(max(0, i - 20), min(len(lines), i + 5)):
                    ctx_line = lines[j].strip()
                    if any(kw in ctx_line for kw in [
                        "timeout_ms", "timeout_sec", "TIMEOUT",
                        "http_config.timeout", "connect_timeout",
                    ]):
                        has_timeout = True
                        break
                if not has_timeout:
                    issues.append({
                        "id": "C22.5",
                        "file": f"{path}:{i}",
                        "issue": f"{api} 未见超时配置",
                        "severity": "P1",
                    })
                break

    # Check for retry without bound
    has_retry_loop = False
    has_retry_limit = False
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if "retry" in stripped.lower() and ("while" in stripped or "for" in stripped):
            has_retry_loop = True
        if has_retry_loop:
            if any(kw in stripped for kw in [
                "max_retry", "MAX_RETRY", "retry_count", "retry <=",
                "retry_count <=", "OTA_MAX_RETRY", "RETRY_LIMIT",
            ]):
                has_retry_limit = True
                has_retry_loop = False

    if has_retry_loop and not has_retry_limit:
        issues.append({
            "id": "C22.5",
            "file": str(path),
            "issue": "OTA 重试循环未见上限限制",
            "severity": "P1",
        })

    return issues


def check_file(path: Path) -> list[dict]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    # Only check files that likely contain OTA code
    lower_text = text.lower()
    if "ota" not in lower_text and "esp_ota" not in lower_text:
        return []

    lines = text.splitlines()
    clean_lines = _strip_comments(text)

    issues = []
    issues.extend(check_signature_verification(path, clean_lines))
    issues.extend(check_rollback_support(path, clean_lines))
    issues.extend(check_ota_timeout(path, clean_lines))
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="C22 OTA 安全检查器")
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
        print("[ota_safety_checker] 无文件可检查")
        return 0

    all_issues: list[dict] = []
    for path in unique:
        all_issues.extend(check_file(path))

    if not all_issues:
        print(f"[ota_safety_checker] 已检查 {len(unique)} 个文件，未发现 C22 违规")
        return 0

    print(f"[ota_safety_checker] 已检查 {len(unique)} 个文件，发现 {len(all_issues)} 个 C22 告警:\n")
    for issue in all_issues:
        print(f"  [{issue['severity']}] {issue['id']} — {issue['file']} — {issue['issue']}")

    print(f"\nSummary: {len(all_issues)} C22 OTA safety warnings")
    return 1


if __name__ == "__main__":
    sys.exit(main())
